from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class NormalisedSnapshot:
    canonical: Dict[str, Any]       # Cleaned payload for storage and downstream evaluation
    identity: str                   # Fused structural behavior hash used strictly by Clustering
    meta: Dict[str, Any]            # Pure execution metadata (roots, truncation, candidates)            # Extra metadata (noise_version, truncated_fields, root_signatures, etc.)
