# --- V4 ENHANCEMENT NOTES ---
# Hybrid Similarity Mode (v4):
#   - Add optional similarity functions for arrays:
#       * Levenshtein thresholds for text-heavy arrays
#       * Numeric tolerance windows for float-heavy arrays
#       * Embedding-based cosine similarity for semantic arrays
#   - Add config flag in Normaliser to enable hybrid mode per SUT.
#   - Ensure deterministic behaviour when hybrid mode is enabled.
# --------------------------------

from typing import Any, Dict, List
import json
from crucible.core.normalisation.blocklist import remove_blocklisted_fields
from crucible.core.normalisation.meta_ignore import strip_meta

def _flatten(obj: Any, prefix: str = "") -> Dict[str, Any]:
    flat: Dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_prefix = f"{prefix}.{k}" if prefix else str(k)
            flat.update(_flatten(v, new_prefix))
    else:
        flat[prefix] = obj
    return flat

def canonicalise_array(arr: List[Any]) -> List[str]:
    """
    Canonicalise array elements for identity:
      - for dicts: strip blocklist + meta, flatten, sort keys, stringify
      - for scalars: stringify
      - sort resulting strings for order invariance
    """
    canon: List[str] = []

    for el in arr:
        if isinstance(el, dict):
            cleaned = strip_meta(remove_blocklisted_fields(el))
            flat = _flatten(cleaned)
            items = sorted(flat.items())
            canon.append(json.dumps(items, sort_keys=True))
        else:
            canon.append(json.dumps(el, sort_keys=True))

    canon.sort()
    return canon
