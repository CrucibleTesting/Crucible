import math
from typing import Any, Dict, List

def _compute_sample_size(cluster_size: int) -> int:
    if cluster_size <= 0:
        return 0
    if cluster_size <= 10:
        return cluster_size
    calculated_sample = int(math.ceil(math.sqrt(cluster_size)))
    return min(200, max(10, calculated_sample))

def _sample_cases(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    n = len(cases)
    sample_size = _compute_sample_size(n)
    if sample_size == n:
        return list(cases)
    step = max(1, n // sample_size)
    indices = list(range(0, n, step))[:sample_size]
    return [cases[i] for i in indices]

def get_staging_clusters_with_samples(storage, sut) -> List[Dict[str, Any]]:
    staging = storage.load_staging()
    cases = staging.get("cases", [])
    
    by_sig: dict[str, list[dict]] = {}
    state_distribution: dict[str, dict[str, int]] = {}
    
    for case in cases:
        meta = case.get("meta", {})
        signature = meta.get("signature", "")
        if not signature:
            continue
            
        state = meta.get("state", "pending")
        by_sig.setdefault(signature, []).append(case)
        
        dist = state_distribution.setdefault(
            signature, 
            {"pending": 0, "accepted": 0, "rejected": 0, "error": 0}
        )
        if state in dist:
            dist[state] += 1
            
    clusters: List[Dict[str, Any]] = []
    for sig, members in by_sig.items():
        samples = _sample_cases(members)
        clusters.append({
            "signature": sig,
            "count": len(members),
            "state_distribution": state_distribution[sig],
            "samples": [
                {"id": c["id"], "input": c["input"], "state": c.get("meta", {}).get("state", "pending")}
                for c in samples
            ],
        })
        
    clusters.sort(key=lambda c: (-c["count"], c["signature"]))
    return clusters