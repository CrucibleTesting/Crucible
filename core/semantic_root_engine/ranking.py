from __future__ import annotations

from typing import Any, List, Tuple

from crucible.core.semantic_root_engine.scoring import (
    object_diversity_score,
    structural_entropy_score,
    key_distinctiveness_score,
    anti_repetitive_array_penalty,
    infra_penalty,
)
from crucible.core.semantic_root_engine.learning_loop import learning_boost

# Tunable depth penalty: deeper paths get penalised so parents outrank leaves.
DEPTH_PENALTY = 2.5


def _path_depth(path: str) -> int:
    """
    Approximate depth from JSONPath:
      $.meta                       -> 1
      $.meta.premises_signals      -> 2
      $.meta.premises_signals.foo  -> 3
      $.items[0].foo               -> 3 (counts '.' and '[')
    """
    if not path or path == "$":
        return 0
    # Count segments and indices
    dots = path.count(".")
    brackets = path.count("[")
    # '$' is the root, so depth is roughly segments + indices minus 1
    return max(0, dots + brackets)


def rank_candidates(
    candidates: List[Tuple[str, Any]],
    learned_root: str | None,
    failure_count: int,
) -> List[Tuple[str, Any, float]]:
    """
    Returns list of (path, value, score) sorted by descending score.

    Score components:
      - D(c): object diversity
      - E(c): structural entropy
      - K(c): key distinctiveness
      - A(c): anti-repetitive array penalty
      - P_infra(c): infra penalty
      - L(c): learning loop boost
      - depth penalty: -DEPTH_PENALTY * depth(path)
    """
    ranked: List[Tuple[str, Any, float]] = []

    for path, value in candidates:
        d = object_diversity_score(value)
        e = structural_entropy_score(value)
        k = key_distinctiveness_score(value)
        a = anti_repetitive_array_penalty(value)
        p = infra_penalty(value)
        l = learning_boost(path, learned_root, failure_count)

        depth = _path_depth(path)
        depth_term = -DEPTH_PENALTY * float(depth)

        score = d + e + k + a + p + l + depth_term
        ranked.append((path, value, score))

    ranked.sort(key=lambda x: x[2], reverse=True)
    return ranked
