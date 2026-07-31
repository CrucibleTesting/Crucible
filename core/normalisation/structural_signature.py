import hashlib
import json
from typing import Any

def structural_signature(obj: Any) -> str:
    """
    Key sets, shapes, types only.
    """

    def shape(x: Any):
        if isinstance(x, dict):
            return {k: shape(v) for k, v in x.items()}
        if isinstance(x, list):
            return [shape(v) for v in x]
        return type(x).__name__

    s = json.dumps(shape(obj), sort_keys=True)
    return hashlib.sha256(s.encode()).hexdigest()
