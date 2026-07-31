import os
import json
from pathlib import Path
from typing import Dict


def discover_config_components() -> Dict[str, str]:
    """
    Looks for a local config file in the user's project root (or CRUCIBLE_ROOT)
    and returns a dictionary of runnable command components.
    """
    env_root = os.getenv("CRUCIBLE_ROOT")
    if env_root:
        config_file = Path(env_root).resolve() / ".crucible.json"
    else:
        config_file = Path(os.getcwd()).resolve() / ".crucible.json"

    if not config_file.exists():
        return {}

    try:
        raw_data = config_file.read_text(encoding="utf-8")
        config_data = json.loads(raw_data)
        return config_data.get("components", {})
    except Exception:
        return {}