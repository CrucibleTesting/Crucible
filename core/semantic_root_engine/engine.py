from __future__ import annotations
from typing import Any, Dict, List, Tuple
from crucible.core.semantic_root_engine.paths import normalize_jsonpath
from crucible.core.semantic_root_engine.candidates import extract_candidates
from crucible.core.semantic_root_engine.ranking import rank_candidates

class SemanticRootEngine:
    """
    Stateless Semantic Root Resolver.
    Bypasses automated learning caches by reading directly from configuration,
    falling back to mathematical heuristics for UI evaluation when unconfigured.
    """
    def __init__(self, adapter_id: str):
        self.adapter_id = adapter_id

    def resolve_or_calculate(
        self,
        component_config: Dict[str, Any],
        raw_payload: Dict[str, Any]
    ) -> Tuple[str, List[Tuple[str, float]]]:
        """
        Processes a raw runtime payload for a component.
        
        Returns:
            Tuple[str, List[Tuple[str, float]]]: 
            - The active semantic root path (string).
            - A list of ranked alternative paths and scores for UI selection.
        """
        # 1. Check for explicit developer intent in .crucible.json
        declared = component_config.get("semantic_root")
        if declared:
            return normalize_jsonpath(declared), []

        # 2. Heuristics fallback: Compute candidate vectors using entropy and distinctiveness
        candidates = extract_candidates(raw_payload)
        
        # We pass None and 0 because the interactive UI replaces the historical decay file
        ranked_candidates = rank_candidates(candidates, learned_root=None, failure_count=0)
        
        if not ranked_candidates:
            # Sane baseline fallback if payload is flat or non-scorable
            fallback = "meta" if "meta" in raw_payload else ""
            return fallback, []
            
        # Extract the highest scoring path string as the default proposal
        top_calculated_path = normalize_jsonpath(ranked_candidates[0][0])
        
        # Return the top guess alongside all calculated options for your UI list
        ui_choices = [(normalize_jsonpath(c[0]), float(c[1])) for c in ranked_candidates]
        return top_calculated_path, ui_choices