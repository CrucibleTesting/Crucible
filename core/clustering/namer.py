# crucible/core/clustering/namer.py

from __future__ import annotations
from typing import Dict, Any


class ClusterNamer:
    """
    Heuristic cluster naming.
    """

    def generate_label(self, snapshot_meta: Dict[str, Any]) -> str:
        roots = snapshot_meta.get("semantic_roots") or {}
        #roots = snapshot_meta.get("cluster_label") or {}
        print(snapshot_meta.get("cluster_label"))
        if not roots:
            return "Unlabelled behaviour"

        root_paths = list(roots.keys())
        base = root_paths[0]

        first_root = roots[base]
        if isinstance(first_root, dict):
            keys = list(first_root.keys())[:3]
            if keys:
                return f"{base} → {{{', '.join(keys)}}}"

        return base
