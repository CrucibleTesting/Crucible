from __future__ import annotations

import math
import re
from typing import Any, Dict, List

from crucible.core.semantic_root_engine.infra import is_infra_key

# Weights (can be tuned later)
W_D = 1.0
W_E = 1.0
W_K = 1.0
W_A = 1.0
W_L = 1.0


def _collect_field_types(value: Any) -> Dict[str, int]:
    counts = {"str": 0, "num": 0, "bool": 0, "obj": 0}
    if isinstance(value, dict):
        for v in value.values():
            if isinstance(v, str):
                counts["str"] += 1
            elif isinstance(v, (int, float)):
                counts["num"] += 1
            elif isinstance(v, bool):
                counts["bool"] += 1
            elif isinstance(v, dict):
                counts["obj"] += 1
    return counts


def object_diversity_score(value: Any) -> float:
    """
    D(c): log(1 + t_s + t_n + t_b + 2 * min(t_o, 5))
    """
    counts = _collect_field_types(value)
    t_s = counts["str"]
    t_n = counts["num"]
    t_b = counts["bool"]
    t_o = counts["obj"]
    return math.log(1 + t_s + t_n + t_b + 2 * min(t_o, 5))


def structural_entropy_score(value: Any) -> float:
    """
    E(c): entropy over key frequencies (very simple approximation).
    """
    if not isinstance(value, dict):
        return 0.0

    keys = list(value.keys())
    if not keys:
        return 0.0

    p = 1.0 / len(keys)
    return -len(keys) * p * math.log(p) if p > 0 else 0.0


def _tokenise_key(key: str) -> List[str]:
    return [t for t in re.split(r"[_\-.]", key) if t]


def _is_english_word(token: str) -> bool:
    return token.isalpha() and len(token) >= 3


def _avg_levenshtein(tokens: List[str]) -> float:
    if len(tokens) < 2:
        return 0.0

    def lev(a: str, b: str) -> int:
        dp = [[i + j if i * j == 0 else 0 for j in range(len(b) + 1)] for i in range(len(a) + 1)]
        for i in range(1, len(a) + 1):
            for j in range(1, len(b) + 1):
                cost = 0 if a[i - 1] == b[j - 1] else 1
                dp[i][j] = min(
                    dp[i - 1][j] + 1,
                    dp[i][j - 1] + 1,
                    dp[i - 1][j - 1] + cost,
                )
        return dp[-1][-1]

    total = 0
    count = 0
    for i in range(len(tokens)):
        for j in range(i + 1, len(tokens)):
            total += lev(tokens[i], tokens[j])
            count += 1
    return total / count if count else 0.0


def key_distinctiveness_score(value: Any) -> float:
    """
    Improved K(c):
      - Original token-based distinctiveness
      - + key-count bonus
      - + key-variety bonus
      - - tiny-dict penalty
      - - diagnostic-key penalty
    """
    if not isinstance(value, dict):
        return 0.0

    keys = list(value.keys())
    if not keys:
        return 0.0

    # Original token-based scoring
    alpha = 1.5
    beta  = 2.0
    gamma = 4.0
    eta   = 0.5

    scores: List[float] = []
    for k in keys:
        tokens = _tokenise_key(k)
        tau = len(tokens)
        sigma = sum(1 for t in tokens if t.isalpha())
        rho = sum(1 for t in tokens if _is_english_word(t))
        delta = _avg_levenshtein(tokens)
        scores.append(alpha * tau + beta * sigma + gamma * rho + eta * delta)

    base = sum(scores) / len(scores)

    # NEW: key-count bonus
    key_count_bonus = 0.8 * len(keys)

    # NEW: key-variety bonus
    variety_bonus = 1.2 * len({type(v).__name__ for v in value.values()})

    # NEW: tiny-dict penalty (score dicts, diagnostic dicts)
    tiny_penalty = -3.0 if len(keys) <= 2 else 0.0

    # NEW: diagnostic-key penalty
    diagnostic_penalty = -2.0 if any(
        re.search(r"(score|detected|token)$", k) for k in keys
    ) else 0.0

    return base + key_count_bonus + variety_bonus + tiny_penalty + diagnostic_penalty


def anti_repetitive_array_penalty(value: Any) -> float:
    """
    A(c): -a / (u + 1)
    """
    if not isinstance(value, list):
        return 0.0

    a = len(value)
    if a == 0:
        return 0.0

    shapes = []
    for el in value:
        if isinstance(el, dict):
            shapes.append(("dict", tuple(sorted(el.keys()))))
        else:
            shapes.append((type(el).__name__, None))

    u = len(set(shapes))
    if a > 10_000 and all(not isinstance(el, dict) for el in value):
        return float("-inf")

    return -float(a) / float(u + 1)


def infra_penalty(value: Any) -> float:
    """
    P_infra(c): -sum I(k)
    """
    if not isinstance(value, dict):
        return 0.0

    penalty = 0.0
    for k in value.keys():
        if is_infra_key(k):
            penalty -= 1.0
    return penalty
