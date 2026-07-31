from __future__ import annotations

import re
from functools import lru_cache
from typing import Pattern

_INFRA_PATTERNS = [
    r"tokens|original_tokens",
    r"spans?|ranges?|positions?",
    r"scores?|confidences?|metrics?",
    r".*_id|.*Id",
    r"auth_.*|.*_token",
    r".*_version",
    r".*_timestamp",
    r".*_latency",
    r"logs?|trace|debug",
    r"request_id|req_id|rid",
]


@lru_cache(maxsize=1)
def compiled_infra_regex() -> Pattern[str]:
    """
    Compile infra patterns into a single regex.
    In a real Trie-based engine we'd build a DFA/Trie; for now this is
    a single optimised regex, which is sufficient for v1.3.
    """
    pattern = "(" + ")|(".join(_INFRA_PATTERNS) + ")"
    return re.compile(pattern)


def is_infra_key(key: str) -> bool:
    return bool(compiled_infra_regex().fullmatch(key)) or bool(
        compiled_infra_regex().search(key)
    )
