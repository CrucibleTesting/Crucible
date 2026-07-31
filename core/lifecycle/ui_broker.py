import os
import sys
import platform
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Any, Dict, List, Callable, Optional

from crucible.core.adapters.adapter_discovery import discover_config_components
from crucible.core.storage.base import LocalStorage
from crucible.core.adapters.runner import create_sut_wrapper
from crucible.core.lifecycle.boot import is_workspace_hydrated, perform_system_hydration
from ui.broker_spec import AbstractSystemBroker

logger = logging.getLogger("crucible.broker")


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

    def open_candidate_pool_in_editor(self, component_id: str) -> Path:
        """
        Launches candidate_pool.txt using VS Code or the system default application,
        handling WSL, Linux, macOS, and Windows cleanly without blocking the TUI
        or desynchronizing Rich's live terminal line tracking.
        """
        storage = LocalStorage(component_name=component_id)
        pool_file = storage.candidate_pool_path

        if not pool_file.exists():
            storage.write_candidate_pool([])

        file_str = str(pool_file)
        launched = False

        # 1. Prefer VS Code CLI if available on system PATH
        code_bin = shutil.which("code") or shutil.which("code.cmd")
        if code_bin:
            try:
                subprocess.Popen(
                    [code_bin, file_str],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                launched = True
            except Exception as e:
                logger.warning(f"Failed to launch via 'code': {e}")

        # 2. Check WSL environment if 'code' was not directly on PATH
        if not launched and ("WSL_DISTRO_NAME" in os.environ or "wsl" in platform.release().lower()):
            wslview = shutil.which("wslview")
            if wslview:
                try:
                    subprocess.Popen(
                        [wslview, file_str],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    launched = True
                except Exception as e:
                    logger.warning(f"Failed to launch via 'wslview': {e}")

        # 3. Fallback to OS default handlers
        if not launched:
            try:
                if sys.platform == "darwin":  # macOS
                    subprocess.Popen(
                        ["open", file_str],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                elif os.name == "nt":        # Windows
                    os.startfile(file_str)
                else:                        # Standard Linux
                    subprocess.Popen(
                        ["xdg-open", file_str],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
            except Exception as e:
                logger.error(f"Failed to launch default OS file handler: {e}")

        return pool_file

    def sync_candidate_pool(self, component_id: str) -> Dict[str, int]:
        """Deduplicates and cleans candidate_pool.txt on demand."""
        storage = LocalStorage(component_name=component_id)
        return storage.sync_and_dedupe_candidate_pool()

    def run_pipeline(
        self,
        component_id: str,
        progress_callback: Callable[[int, int], None]
    ) -> Dict[str, Any]:
        """
        Deduplicates candidate inputs and triggers staging (Bronze -> Silver).
        """
        storage = LocalStorage(component_name=component_id)

        # Ensure clean inputs prior to running SUT staging execution
        storage.sync_and_dedupe_candidate_pool()
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