from __future__ import annotations
import copy
import hashlib
from crucible.core.clustering.types import NormalisedSnapshot, ClusterAssignment
from crucible.core.clustering.store import ClusterStore
from crucible.core.clustering.namer import ClusterNamer

class ClusteringEngine:
    def __init__(self, store: ClusterStore) -> None:
        self._store = store

    def assign_snapshot(
        self,
        snapshot: NormalisedSnapshot,
        adapter_id: str,
    ) -> ClusterAssignment:
        representative = copy.deepcopy(snapshot.canonical)
        identity_key = snapshot.identity
        
        cluster = self._store.get_by_identity(identity_key)
        if cluster is not None:
            stats = self._store.increment_cluster_stats(cluster.cluster_id)
            final_count = stats.count if stats else cluster.stats.count
            return ClusterAssignment(
                cluster_id=cluster.cluster_id,
                is_new_cluster=False,
                cluster_label=cluster.label,
                snapshot_count=final_count,
            )

        # Generate a deterministic cluster identity anchor using structural signature traits
        raw_id_seed = f"{identity_key}".encode("utf-8")
        deterministic_id = f"CLSTR_{hashlib.sha256(raw_id_seed).hexdigest()[:12].upper()}"

        namer = ClusterNamer()
        label = namer.generate_label(snapshot.meta)
        
        # Purged direct top-level contamination to keep clustering pure and value-blind
        meta = {**snapshot.meta}
        
        cluster = self._store.create_cluster(
            identity_key=identity_key,
            cluster_id=deterministic_id,
            label=label,
            representative=representative,
            meta=meta,
        )
        
        stats = self._store.increment_cluster_stats(cluster.cluster_id)
        final_count = stats.count if stats else cluster.stats.count
        return ClusterAssignment(
            cluster_id=cluster.cluster_id,
            is_new_cluster=True,
            cluster_label=cluster.label,
            snapshot_count=final_count,
        )