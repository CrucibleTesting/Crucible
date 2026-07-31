# ==========================================
# File: config.py
# ==========================================

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from crucible.core.semantic_root_engine.paths import get_global_config_path

DEFAULT_MAX_DEPTH = 3


def load_crucible_config() -> Dict[str, Any]:
    """
    Load the global crucible.yaml config file.
    Returns {} if missing or invalid.
    """
    path = get_global_config_path()

    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def get_max_depth(config: Optional[Dict[str, Any]] = None) -> int:
    """
    Returns the configured max depth for semantic root discovery.
    Falls back to DEFAULT_MAX_DEPTH if not set.
    """
    if config is None:
        config = load_crucible_config()

    return int(config.get("CRUCIBLE_MAX_DEPTH", DEFAULT_MAX_DEPTH))
