import os
from pathlib import Path
from typing import Any, Dict, List, Callable, Optional
from crucible.core.adapters.adapter_discovery import discover_config_components
from crucible.core.storage.base import LocalStorage
from crucible.core.adapters.runner import create_sut_wrapper
from crucible.core.lifecycle.boot import is_workspace_hydrated, perform_system_hydration
from ui.broker_spec import AbstractSystemBroker


class CoreUIBroker(AbstractSystemBroker):
    """
    Concrete bridge connecting Core lifecycle routines to the TUI interface.
    """

    def has_active_workspaces(self) -> bool:
        """Returns True if at least one declared component has an initialized suite directory."""
        try:
            env_root = os.getenv("CRUCIBLE_ROOT")
            root_dir = Path(env_root).resolve() if env_root else Path(os.getcwd()).resolve() / ".crucible"
            suites_dir = root_dir / "suites"
            discovered = discover_config_components()
            return any((suites_dir / name).exists() for name in discovered.keys())
        except Exception:
            return False

    def has_registered_components(self) -> bool:
        """Returns True if there is at least one entry in .crucible.json."""
        try:
            return len(discover_config_components()) > 0
        except Exception:
            return False

    def is_system_hydrated(self) -> bool:
        return is_workspace_hydrated()

    def hydrate_system(
        self, 
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[str]:
        """
        Executes workspace hydration and reports incremental progress back via callback if provided.
        """
        return perform_system_hydration(progress_callback=progress_callback)

    def get_components(self) -> List[Dict[str, str]]:
        """
        Queries entries in .crucible.json and returns only valid, 
        initialized components with simplified status labels.
        """
        try:
            env_root = os.getenv("CRUCIBLE_ROOT")
            root_dir = Path(env_root).resolve() if env_root else Path(os.getcwd()).resolve() / ".crucible"
            suites_dir = root_dir / "suites"
            discovered = discover_config_components()
            valid_components = []

            for name in discovered.keys():
                adapter_dir = suites_dir / name
                snapshot_file = adapter_dir / "Silver" / "snapshots.json"

                if adapter_dir.exists() and snapshot_file.exists() and snapshot_file.stat().st_size > 30:
                    valid_components.append({"name": name, "status": "Active"})
                elif adapter_dir.exists():
                    valid_components.append({"name": name, "status": "Unstaged"})

            return valid_components
        except Exception:
            return []

    def run_pipeline(
        self,
        component_id: str,
        progress_callback: Callable[[int, int], None]
    ) -> Dict[str, Any]:
        storage = LocalStorage(component_name=component_id)
        candidates = storage.read_candidate_pool()
        if not candidates:
            return {"status": "empty", "message": "Bronze layer is empty."}

        progress_callback(20, 100)
        component_config = discover_config_components().get(component_id, {})
        if not isinstance(component_config, dict):
            component_config = {"command": str(component_config)}

        command_string = component_config.get("command", "")
        semantic_root = component_config.get("semantic_root", "")
        progress_callback(50, 100)

        sut_executable = create_sut_wrapper(command_string=command_string, semantic_root=semantic_root)
        storage.generate_snapshots(sut=sut_executable, component_config=component_config)
        progress_callback(100, 100)

        return {"status": "success", "cases_processed": len(candidates)}