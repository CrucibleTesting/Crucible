from typing import Any, Dict, List

def list_staging_clusters(storage) -> List[Dict[str, Any]]:
    """
    Group staging cases by strict behavioural signature.
    
    Rules:
    - Process all snapshot records to maintain structural blindness.
    - Expose structural totals alongside internal state distributions.
    - Cluster key = meta["signature"].
    """
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
        clusters.append(
            {
                "signature": sig,
                "count": len(members),
                "state_distribution": state_distribution[sig],
            }
        )
        
    clusters.sort(key=lambda c: (-c["count"], c["signature"]))
    return clusters