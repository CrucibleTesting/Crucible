from __future__ import annotations
from typing import List
from crucible.core.clustering.store import ClusterStore

class MergeSplitEngine:
    def __init__(self, store: ClusterStore):
        self.store = store

    def merge(self, source_id: str, target_id: str) -> None:
        source = self.store.get_by_id(source_id)
        target = self.store.get_by_id(target_id)
        if not source or not target or source.cluster_id == target.cluster_id:
            return
            
        target.stats.count += source.stats.count
        target.stats.first_seen_ts_utc = min(target.stats.first_seen_ts_utc, source.stats.first_seen_ts_utc)
        target.stats.last_seen_ts_utc = max(target.stats.last_seen_ts_utc, source.stats.last_seen_ts_utc)
        
        target.lineage.setdefault("merged_from", []).append(source.cluster_id)
        source.lineage.setdefault("merged_into", target.cluster_id)
        
        self.store.add_identity_forwarding(
            old_identity=source.identity_key,
            target_cluster_id=target.cluster_id,
        )
        self.store._remove_cluster_internal(source)

    def split(self, cluster_id: str, new_identity_keys: List[str]) -> None:
        """
        Dynamically partitions an active cluster bucket when behavioral 
        drift manifests across execution runs. (v3.3 Pipeline Stub)
        """
        pass