from typing import Any, Dict, List

META_PREFIXES = (
    "signals", "tokens", "spans",
    "debug", "scores", "raw",
)

def _is_meta_key(key: str) -> bool:
    return any(key.startswith(p) for p in META_PREFIXES)

def strip_meta(value: Any) -> Any:
    """
    Recursively strip meta/debug fields:
      - keys starting with known prefixes
      - inside dicts
      - inside arrays
    """
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            if _is_meta_key(k):
                continue
            out[k] = strip_meta(v)
        return out
    if isinstance(value, list):
        return [strip_meta(v) for v in value]
    return value
