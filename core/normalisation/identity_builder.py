import hashlib
import json
from typing import Any, Dict

def build_root_identity(root_value: Any, struct_sig: str) -> Dict[str, Any]:
    """
    Build a domain‑agnostic behavioural identity from the semantic root.
    Behaviour is defined ONLY by:
      - presence/absence of fields
      - type of each field
      - cardinality of lists
      - nested structural patterns

    Literal values (e.g. "10", "4", "Downing", "Orchard") are ignored.
    """

    def behaviour_signature(value: Any):
        # Null-like
        if value is None:
            return "NONE"

        # Scalars → type only (ignore literal values)
        if isinstance(value, (str, int, float, bool)):
            return type(value).__name__

        # Lists → cardinality only
        if isinstance(value, list):
            return f"LIST(len={len(value)})"

        # Dicts → recurse on keys, preserving structure but not values
        if isinstance(value, dict):
            sig = {}
            for k, v in sorted(value.items()):
                sig[k] = behaviour_signature(v)
            return sig

        # Fallback
        return type(value).__name__

    behaviour = behaviour_signature(root_value)

    return {
        "behaviour": behaviour,
        "structural": struct_sig,
    }


def fuse_identities(per_root: Dict[str, Dict[str, Any]]) -> str:
    """
    Deterministically fuse per-root identities into a single signature.
    """
    payload = {
        "roots": per_root,
    }
    raw = json.dumps(payload, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()
