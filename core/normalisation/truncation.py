from __future__ import annotations

from typing import Any, Dict, List, Tuple

MAX_ARRAY_ITEMS = 200
MAX_STRING_CHARS = 2000
MAX_SNAPSHOT_BYTES = 2 * 1024 * 1024  # 2MB soft cap


def truncate_snapshot(snapshot: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Truncate large fields for diffing:
      - arrays > MAX_ARRAY_ITEMS
      - strings > MAX_STRING_CHARS
      - (optionally) blobs/embeddings/HTML by heuristic

    Returns:
      - truncated snapshot
      - list of truncated field paths
    """
    truncated_fields: List[str] = []

    def _truncate(value: Any, path: str) -> Any:
        nonlocal truncated_fields

        # Strings
        if isinstance(value, str):
            if len(value) > MAX_STRING_CHARS:
                truncated_fields.append(path)
                return value[:MAX_STRING_CHARS] + " <TRUNCATED>"
            return value

        # Arrays
        if isinstance(value, list):
            if len(value) > MAX_ARRAY_ITEMS:
                truncated_fields.append(path)
                return value[:MAX_ARRAY_ITEMS] + ["<TRUNCATED_ARRAY>"]
            return [_truncate(v, f"{path}[{i}]") for i, v in enumerate(value)]

        # Dicts
        if isinstance(value, dict):
            out: Dict[str, Any] = {}
            for k, v in value.items():
                child_path = f"{path}.{k}" if path else k
                out[k] = _truncate(v, child_path)
            return out

        return value

    truncated = _truncate(snapshot, "")
    return truncated, truncated_fields
