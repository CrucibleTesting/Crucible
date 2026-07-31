# crucible/core/clustering/lineage.py

from __future__ import annotations
from typing import Dict, Any


class LineageTracker:
    """
    Tracks behavioural lineage (merges, splits, evolution).
    """

    def record_merge(self, target, source) -> None:
        target.lineage.setdefault("merged_from", []).append(source.cluster_id)
        source.lineage.setdefault("merged_into", target.cluster_id)

    def record_split(self, parent, children) -> None:
        parent.lineage.setdefault("split_into", []).extend([c.cluster_id for c in children])
        for child in children:
            child.lineage.setdefault("split_from", parent.cluster_id)
