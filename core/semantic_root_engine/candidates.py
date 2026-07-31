from __future__ import annotations
from typing import Any, Dict, List, Tuple

from crucible.core.semantic_root_engine.depth_control import walk_structured


def extract_candidates(raw: Dict[str, Any]) -> List[Tuple[str, Any]]:
    """
    Extract candidate semantic roots as (jsonpath, value) pairs.
    Uses bounded-depth traversal.
    """
    if not isinstance(raw, dict):
        return []

    return walk_structured(raw, prefix="$", depth=0)
