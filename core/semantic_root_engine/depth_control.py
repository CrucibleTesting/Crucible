from __future__ import annotations

from typing import Any, Dict, List, Tuple

from crucible.core.semantic_root_engine.config import get_max_depth


def walk_structured(
    obj: Any,
    prefix: str = "$",
    depth: int = 0,
    max_depth: int | None = None,
) -> List[Tuple[str, Any]]:
    """
    Walk structured nodes up to max_depth and return (jsonpath, value) pairs
    where value is a dict or list.
    """
    if max_depth is None:
        max_depth = get_max_depth()

    results: List[Tuple[str, Any]] = []

    if depth > max_depth:
        return results

    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix != "$" else f"$.{k}"
            if isinstance(v, (dict, list)):
                results.append((path, v))
            results.extend(walk_structured(v, path, depth + 1, max_depth))

    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            path = f"{prefix}[{i}]"
            if isinstance(v, (dict, list)):
                results.append((path, v))
            results.extend(walk_structured(v, path, depth + 1, max_depth))

    return results
