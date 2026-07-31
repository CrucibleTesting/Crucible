import os
from pathlib import Path
from typing import List, Callable, Optional
from crucible.core.adapters.scaffold import initialize_workspace_layers, extract_seeds_for_component
from crucible.core.adapters.adapter_discovery import discover_config_components


def is_workspace_hydrated() -> bool:
    """
    Evaluates whether all VALID components in .crucible.json have active,
    populated workspace directories and Silver snapshots.
    """
    try:
        adapters = discover_config_components()
        if not adapters:
            return True  # No components declared; nothing to hydrate

        env_root = os.getenv("CRUCIBLE_ROOT")
        root_dir = Path(env_root).resolve() if env_root else Path(os.getcwd()).resolve() / ".crucible"
        suites_dir = root_dir / "suites"

        if not suites_dir.exists():
            return False

        for name, config in adapters.items():
            if not isinstance(config, dict):
                config = {"command": str(config)}

            seeds = extract_seeds_for_component(name, config)
            if not seeds:
                continue

            adapter_dir = suites_dir / name
            snapshot_file = adapter_dir / "Silver" / "snapshots.json"

            if not adapter_dir.exists() or not snapshot_file.exists() or snapshot_file.stat().st_size <= 30:
                return False

        return True
    except Exception:
        return False


def perform_system_hydration(
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> List[str]:
    """Executes background scaffolding and returns any error/warning outputs."""
    return initialize_workspace_layers(progress_callback=progress_callback)