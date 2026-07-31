from __future__ import annotations

from typing import Any, Optional


def get_declared_semantic_root(adapter: Any) -> Optional[str]:
    """
    If the adapter module exposes SEMANTIC_ROOT, return it.
    Otherwise return None.
    """
    return getattr(adapter, "SEMANTIC_ROOT", None)
