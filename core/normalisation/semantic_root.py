from __future__ import annotations
from typing import Any, Dict, List, Tuple
from crucible.core.semantic_root_engine import SemanticRootEngine

def resolve_semantic_roots(
    adapter_id: str,
    adapter_fn,
    raw: Dict[str, Any],
    declared_roots: List[str] | None = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Resolve semantic roots for a given snapshot using the stateless discovery core.
    
    Returns:
    - roots: mapping root_path -> subtree value
    - meta:  mapping with extra UI-ready candidate information
    """
    # The normalisation engine passing context config requires mock encapsulation if missing
    mock_component_config = {"semantic_root": declared_roots[0] if declared_roots else None}
    
    engine = SemanticRootEngine(adapter_id=adapter_id)
    raw_payload = raw if isinstance(raw, dict) else {}
    
    best_path_normalized, ui_choices = engine.resolve_or_calculate(mock_component_config, raw_payload)
    
    roots: Dict[str, Any] = {}
    if declared_roots:
        for path in declared_roots:
            roots[path] = _get_subtree(raw, path)
    else:
        if best_path_normalized:
            # Reconstruct prefix lookup bounds matching baseline schema expectations
            lookup_path = f"$.{best_path_normalized}" if not best_path_normalized.startswith("$") else best_path_normalized
            roots[lookup_path] = _get_subtree(raw, lookup_path)
        else:
            roots["meta"] = _get_subtree(raw, "meta")

    meta = {
        "ranked_candidates": ui_choices,
        "learned_root": best_path_normalized,
        "failures": 0,
    }
    return roots, meta

def _get_subtree(obj: Any, path: str | None) -> Any:
    if not path:
        return obj
    if path.startswith("$."):
        path = path[2:]
    elif path.startswith("$"):
        path = path[1:]
    parts = path.split(".")
    current = obj
    
    if parts and isinstance(current, dict) and parts[0] not in current:
        if len(parts) > 1 and parts[1] in current:
            parts = parts[1:]
            
    try:
        for part in parts:
            if isinstance(current, dict):
                current = current[part]
            elif isinstance(current, list) and part.isdigit():
                current = current[int(part)]
            else:
                return obj
        return current
    except Exception:
        return obj