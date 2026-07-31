from __future__ import annotations
from typing import Dict, Any

class ClusterSummariser:
    """
    Produces UI-friendly summaries of clusters.
    """
    def summarise(self, cluster) -> Dict[str, Any]:
        return {
            "cluster_id": cluster.cluster_id,
            "label": cluster.label,
            "count": cluster.stats.count,
            "representative": cluster.representative,
            "meta": cluster.meta,
        }