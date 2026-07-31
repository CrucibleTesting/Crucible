from __future__ import annotations
import copy
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from queue import Queue
from typing import Dict, Optional, Any, List
from crucible.core.clustering.types import Cluster, ClusterStats
from crucible.core.clustering.logging_worker import LoggingWorker

class ClusterStore:
    def __init__(
        self,
        log_path: Optional[str] = None,
        snapshot_path: Optional[str] = None,
    ) -> None:
        self._clusters_by_identity: Dict[str, Cluster] = {}
        self._clusters_by_id: Dict[str, Cluster] = {}
        self._identity_forwarding: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._is_shutdown = False
        self._log_path = Path(log_path) if log_path else Path("cluster_store.log.jsonl")
        self._snapshot_path = Path(snapshot_path) if snapshot_path else Path("cluster_store.snapshot.json")
        
        # ✅ Track transaction entries to trigger auto-compaction
        self._transaction_counter = 0 
        
        self._log_queue: Queue = Queue()
        self._log_file = self._log_path.open("a", encoding="utf-8")
        self._logging_worker = LoggingWorker(self._log_queue, self._log_file)
        self._replay_snapshot_and_log()

    def get_by_identity(self, identity_key: str) -> Optional[Cluster]:
        with self._lock:
            if identity_key in self._identity_forwarding:
                target_cluster_id = self._identity_forwarding[identity_key]
                return self._clusters_by_id.get(target_cluster_id)
            return self._clusters_by_identity.get(identity_key)

    def get_by_id(self, cluster_id: str) -> Optional[Cluster]:
        with self._lock:
            return self._clusters_by_id.get(cluster_id)

    def all_clusters(self) -> List[Cluster]:
        with self._lock:
            return list(self._clusters_by_id.values())

    def create_cluster(
        self,
        identity_key: str,
        cluster_id: str,
        label: str,
        representative: Any,
        meta: Dict[str, Any],
    ) -> Cluster:
        with self._lock:
            cluster = Cluster(
                identity_key=identity_key,
                cluster_id=cluster_id,
                label=label,
                representative=representative,
                meta=meta,
            )
            self._clusters_by_identity[identity_key] = cluster
            self._clusters_by_id[cluster.cluster_id] = cluster
            
            payload = {
                "label": label,
                "representative": representative,
                "meta": meta,
            }
            self._enqueue_event(
                op="create_cluster",
                cluster_id=cluster.cluster_id,
                identity_key=identity_key,
                payload=payload,
            )
            return cluster

    def increment_cluster_stats(self, cluster_id: str) -> Optional[ClusterStats]:
        with self._lock:
            cluster = self._clusters_by_id.get(cluster_id)
            if cluster:
                cluster.stats.update()
                self._enqueue_event(
                    op="update_cluster_stats",
                    cluster_id=cluster.cluster_id,
                    identity_key=cluster.identity_key,
                    payload={
                        "count": cluster.stats.count,
                        "last_seen_ts_utc": cluster.stats.last_seen_ts_utc
                    }
                )
                return cluster.stats
            return None

    def add_identity_forwarding(self, old_identity: str, target_cluster_id: str) -> None:
        with self._lock:
            self._identity_forwarding[old_identity] = target_cluster_id
            payload = {
                "old_identity": old_identity,
                "target_cluster_id": target_cluster_id,
            }
            self._enqueue_event(
                op="add_identity_forwarding",
                cluster_id=target_cluster_id,
                identity_key=old_identity,
                payload=payload,
            )

    def _remove_cluster_internal(self, cluster: Cluster) -> None:
        cid = cluster.cluster_id
        identity = cluster.identity_key
        if identity in self._clusters_by_identity:
            del self._clusters_by_identity[identity]
        if cid in self._clusters_by_id:
            del self._clusters_by_id[cid]
        to_delete = [k for k, v in self._identity_forwarding.items() if v == cid]
        for k in to_delete:
            del self._identity_forwarding[k]
        
        payload = {
            "cluster_id": cid,
            "identity_key": identity,
        }
        self._enqueue_event(
            op="remove_cluster",
            cluster_id=cid,
            identity_key=identity,
            payload=payload,
        )

    def _enqueue_event(self, op: str, cluster_id: str, identity_key: str, payload: Dict[str, Any]) -> None:
        if self._is_shutdown:
            return
        event = {
            "version": 1,
            "op": op,
            "ts_monotonic_ns": time.monotonic_ns(),
            "cluster_id": cluster_id,
            "identity_key": identity_key,
            "payload": payload,
        }
        self._log_queue.put(copy.deepcopy(event))

        # ✅ Check threshold and launch background compaction thread safely
        self._transaction_counter += 1
        if self._transaction_counter >= 5000:
            self._transaction_counter = 0
            threading.Thread(target=self.compact, daemon=True).start()

    def _replay_snapshot_and_log(self) -> None:
        if self._snapshot_path.exists():
            try:
                data = json.loads(self._snapshot_path.read_text(encoding="utf-8"))
                self._apply_snapshot(data)
            except Exception:
                pass
        if self._log_path.exists():
            with self._log_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    try:
                        self._apply_log_event(json.loads(line))
                    except Exception:
                        continue

    def _apply_snapshot(self, data: Dict[str, Any]) -> None:
        clusters_by_id = data.get("clusters_by_id", {})
        identity_forwarding = data.get("identity_forwarding", {})
        for cid, cdata in clusters_by_id.items():
            stats_data = cdata.get("stats", {})
            stats = ClusterStats(
                count=stats_data.get("count", 0),
                first_seen_ts_utc=stats_data.get("first_seen_ts_utc", time.time()),
                last_seen_ts_utc=stats_data.get("last_seen_ts_utc", time.time()),
            )
            cluster = Cluster(
                identity_key=cdata.get("identity_key", ""),
                cluster_id=cdata.get("cluster_id", cid),
                label=cdata.get("label", "Unlabelled behaviour"),
                stats=stats,
                representative=cdata.get("representative"),
                meta=cdata.get("meta", {}),
                lineage=cdata.get("lineage", {}),
            )
            self._clusters_by_id[cluster.cluster_id] = cluster
            self._clusters_by_identity[cluster.identity_key] = cluster
        self._identity_forwarding = dict(identity_forwarding)

    def _apply_log_event(self, event: Dict[str, Any]) -> None:
        op = event.get("op")
        cluster_id = event.get("cluster_id")
        identity_key = event.get("identity_key")
        payload = event.get("payload", {})
        if op == "create_cluster":
            cluster = Cluster(
                identity_key=identity_key,
                cluster_id=cluster_id,
                label=payload.get("label", "Unlabelled behaviour"),
                representative=payload.get("representative"),
                meta=payload.get("meta", {}),
            )
            self._clusters_by_identity[identity_key] = cluster
            self._clusters_by_id[cluster_id] = cluster
        elif op == "update_cluster_stats":
            cluster = self._clusters_by_id.get(cluster_id)
            if cluster:
                cluster.stats.count = payload.get("count", cluster.stats.count)
                cluster.stats.last_seen_ts_utc = payload.get("last_seen_ts_utc", cluster.stats.last_seen_ts_utc)
        elif op == "add_identity_forwarding":
            self._identity_forwarding[payload.get("old_identity", identity_key)] = payload.get("target_cluster_id", cluster_id)
        elif op == "remove_cluster":
            self._clusters_by_identity.pop(identity_key, None)
            self._clusters_by_id.pop(cluster_id, None)

    def compact(self) -> None:
        with self._lock:
            snapshot_data: Dict[str, Any] = {"version": 1, "clusters_by_id": {}, "identity_forwarding": dict(self._identity_forwarding)}
            for cid, cluster in self._clusters_by_id.items():
                snapshot_data["clusters_by_id"][cid] = {
                    "identity_key": cluster.identity_key,
                    "cluster_id": cluster.cluster_id,
                    "label": cluster.label,
                    "stats": {"count": cluster.stats.count, "first_seen_ts_utc": cluster.stats.first_seen_ts_utc, "last_seen_ts_utc": cluster.stats.last_seen_ts_utc},
                    "representative": cluster.representative,
                    "meta": cluster.meta,
                    "lineage": cluster.lineage,
                }
            dir_name = os.path.dirname(str(self._snapshot_path)) or "."
            with tempfile.NamedTemporaryFile("w", delete=False, dir=dir_name) as tf:
                json.dump(snapshot_data, tf)
            os.replace(tf.name, self._snapshot_path)

            # ✅ Clear the log file to reclaim space after snapshot generation
            try:
                self._log_file.close()
                self._log_path.write_text("", encoding="utf-8")
                self._log_file = self._log_path.open("a", encoding="utf-8")
            except Exception:
                pass

    def shutdown(self) -> None:
        with self._lock:
            if self._is_shutdown: return
            self._is_shutdown = True
            self._log_queue.put(None)
            self._logging_worker.join()
            self._log_file.close()
            self.compact()  # ✅ Always perform an final snapshot clean checkout on graceful exit