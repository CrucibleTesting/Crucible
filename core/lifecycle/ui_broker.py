import os
import sys
import platform
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Any, Dict, List, Callable, Optional
from collections import defaultdict

from crucible.core.adapters.adapter_discovery import discover_config_components
from crucible.core.storage.base import LocalStorage
from crucible.core.adapters.runner import create_sut_wrapper
from crucible.core.lifecycle.boot import is_workspace_hydrated, perform_system_hydration
try:
    from crucible.ui.broker_spec import AbstractSystemBroker
except ImportError:
    from ui.broker_spec import AbstractSystemBroker

logger = logging.getLogger("crucible.broker")


class CoreUIBroker(AbstractSystemBroker):
    """
    Concrete bridge connecting Core lifecycle routines to the TUI interface.
    """

    def has_active_workspaces(self) -> bool:
        try:
            env_root = os.getenv("CRUCIBLE_ROOT")
            root_dir = Path(env_root).resolve() if env_root else Path(os.getcwd()).resolve() / ".crucible"
            suites_dir = root_dir / "suites"
            discovered = discover_config_components()
            return any((suites_dir / name).exists() for name in discovered.keys())
        except Exception:
            return False

    def has_registered_components(self) -> bool:
        try:
            return len(discover_config_components()) > 0
        except Exception:
            return False

    def is_system_hydrated(self) -> bool:
        return is_workspace_hydrated()

    def hydrate_system(
        self, progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[str]:
        return perform_system_hydration(progress_callback=progress_callback)

    def get_components(self) -> List[Dict[str, str]]:
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
        storage = LocalStorage(component_name=component_id)
        pool_file = storage.candidate_pool_path

        if not pool_file.exists():
            storage.write_candidate_pool([])

        file_str = str(pool_file)
        launched = False

        code_bin = shutil.which("code") or shutil.which("code.cmd")
        if code_bin:
            try:
                subprocess.Popen([code_bin, file_str], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                launched = True
            except Exception as e:
                logger.warning(f"Failed to launch via 'code': {e}")

        if not launched and ("WSL_DISTRO_NAME" in os.environ or "wsl" in platform.release().lower()):
            wslview = shutil.which("wslview")
            if wslview:
                try:
                    subprocess.Popen([wslview, file_str], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    launched = True
                except Exception as e:
                    logger.warning(f"Failed to launch via 'wslview': {e}")

        if not launched:
            try:
                if sys.platform == "darwin":
                    subprocess.Popen(["open", file_str], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif os.name == "nt":
                    os.startfile(file_str)
                else:
                    subprocess.Popen(["xdg-open", file_str], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                logger.error(f"Failed to launch default OS file handler: {e}")

        return pool_file

    def sync_candidate_pool(self, component_id: str) -> Dict[str, int]:
        storage = LocalStorage(component_name=component_id)
        return storage.sync_and_dedupe_candidate_pool()

    def run_pipeline(
        self, component_id: str, progress_callback: Callable[[int, int], None]
    ) -> Dict[str, Any]:
        """
        Deduplicates candidate inputs and triggers staging (Bronze -> Silver).
        Calculates and returns execution summary metrics.
        """
        storage = LocalStorage(component_name=component_id)
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

        # Parse staging outputs to produce table summary metrics
        staging_data = storage.load_staging()
        cases = staging_data.get("cases", [])

        total = len(cases)
        crashed = sum(1 for c in cases if c.get("meta", {}).get("state") == "error")
        successful = total - crashed

        return {
            "status": "completed",
            "total_cases": total,
            "successful": successful,
            "crashed_cases": crashed,
        }

    # def get_cluster_table(self, component_id: str) -> List[Dict[str, Any]]:
    #     """
    #     Loads staging data for a component and returns simple cluster case counts.
    #     """
    #     clean_id = component_id.lower().replace("_", "-")
    #     storage = LocalStorage(component_name=clean_id)
    #     staging = storage.load_staging()
    #     cases = staging.get("cases", [])
        
    #     clusters = defaultdict(int)
    #     for case in cases:
    #         cid = case.get("meta", {}).get("cluster_id", "Unassigned")
    #         clusters[cid] += 1
            
    #     return [
    #         {"cluster_id": cid, "count": count}
    #         for cid, count in clusters.items()
    #     ]

    def get_cluster_table(self, component_id: str) -> List[Dict[str, Any]]:
        """
        Loads staging data for a component and returns simple cluster case counts,
        excluding already promoted, accepted, or rejected cases.
        """
        clean_id = component_id.lower().replace("_", "-")
        storage = LocalStorage(component_name=clean_id)
        staging = storage.load_staging()
        cases = staging.get("cases", [])
        
        clusters = defaultdict(int)
        for case in cases:
            meta = case.get("meta", {})
            state = meta.get("state", "pending")
            
            # Skip cases that have already been resolved
            if state in ("accepted", "promoted", "gold", "rejected"):
                continue
                
            cid = meta.get("cluster_id", "Unassigned")
            clusters[cid] += 1
            
        return [
            {"cluster_id": cid, "count": count}
            for cid, count in clusters.items()
            if count > 0
        ]

    def get_cluster_samples(self, component_id: str, cluster_id: str) -> List[Dict[str, Any]]:
        """
        Loads staging data, filters cases by the specific cluster_id, 
        and returns the representative sub-sampled set using the review module.
        """
        clean_id = component_id.lower().replace("_", "-")
        storage = LocalStorage(component_name=clean_id)
        staging = storage.load_staging()
        cases = staging.get("cases", [])
        
        # 1. Filter cases belonging to this specific cluster ID
        cluster_cases = [
            case for case in cases 
            if case.get("meta", {}).get("cluster_id", "Unassigned") == cluster_id
        ]
        
        if not cluster_cases:
            return []
            
        # 2. Apply the representative sub-sampling algorithm
        from crucible.core.clustering.review import _sample_cases
        return _sample_cases(cluster_cases)

    # def promote_cluster(self, component_id: str, cluster_id: str) -> None:
    #     """
    #     Promotes a cluster representative to Golden and updates all staging records.
    #     """
    #     clean_id = component_id.lower().replace("_", "-")
    #     storage = LocalStorage(component_name=clean_id)
        
    #     # Get the component config to retrieve the SUT wrapper command/settings
    #     component_config = discover_config_components().get(clean_id, {})
    #     if not isinstance(component_config, dict):
    #         component_config = {"command": str(component_config)}
            
    #     command_string = component_config.get("command", "")
    #     semantic_root = component_config.get("semantic_root", "")
    #     sut_executable = create_sut_wrapper(command_string=command_string, semantic_root=semantic_root)
        
    #     # Import and invoke the verified core promotion routine
    #     from crucible.core.promotion.promotion import promote_cluster_representative
    #     promote_cluster_representative(storage, sut_executable, cluster_id)

    def promote_cluster(self, component_id: str, cluster_id: str) -> None:
        clean_id = component_id.lower().replace("_", "-")
        storage = LocalStorage(component_name=clean_id)
        
        component_config = discover_config_components().get(clean_id, {})
        if not isinstance(component_config, dict):
            component_config = {"command": str(component_config)}
            
        command_string = component_config.get("command", "")
        semantic_root = component_config.get("semantic_root", "")
        sut_executable = create_sut_wrapper(command_string=command_string, semantic_root=semantic_root)
        
        from crucible.core.promotion.promotion import promote_cluster_representative
        try:
            promote_cluster_representative(storage, sut_executable, cluster_id)
            logger.info(f"Successfully promoted cluster {cluster_id} for {clean_id}")
        except Exception as e:
            logger.exception(f"CRITICAL: Failed to promote cluster {cluster_id}: {e}")
            raise

    # def reject_cluster(self, component_id: str, cluster_id: str) -> None:
    #     """
    #     Rejects a cluster and updates the staging/rejection state.
    #     """
    #     clean_id = component_id.lower().replace("_", "-")
    #     storage = LocalStorage(component_name=clean_id)
        
    #     # Import and invoke the core cluster rejection routine
    #     from crucible.core.promotion.promotion import reject_cluster_representative
    #     reject_cluster_representative(storage, cluster_id)

    def reject_cluster(self, component_id: str, cluster_id: str) -> None:
        """
        Rejects an entire cluster and updates the staging/rejection state.
        """
        clean_id = component_id.lower().replace("_", "-")
        storage = LocalStorage(component_name=clean_id)
        from crucible.core.promotion.promotion import reject_cluster_representative
        try:
            reject_cluster_representative(storage, cluster_id)
            logger.info(f"Successfully rejected cluster {cluster_id} for {clean_id}")
        except Exception as e:
            logger.exception(f"CRITICAL: Failed to reject cluster {cluster_id}: {e}")
            raise

    def get_suppressed_cluster_count(self, component_id: str) -> int:
        clean_id = component_id.lower().replace("_", "-")
        storage = LocalStorage(component_name=clean_id)
        staging = storage.load_staging()
        cases = staging.get("cases", [])
        suppressed = set()
        for case in cases:
            meta = case.get("meta", {})
            if meta.get("state") == "rejected":
                cid = meta.get("cluster_id")
                if cid:
                    suppressed.add(cid)
        return len(suppressed)

    def get_suppressed_cluster_table(self, component_id: str) -> List[Dict[str, Any]]:
        clean_id = component_id.lower().replace("_", "-")
        storage = LocalStorage(component_name=clean_id)
        staging = storage.load_staging()
        cases = staging.get("cases", [])
        clusters = defaultdict(int)
        for case in cases:
            meta = case.get("meta", {})
            if meta.get("state") == "rejected":
                cid = meta.get("cluster_id", "Unassigned")
                clusters[cid] += 1
        return [{"cluster_id": cid, "count": count} for cid, count in clusters.items()]

    def unreject_cluster(self, component_id: str, cluster_id: str) -> None:
        clean_id = component_id.lower().replace("_", "-")
        storage = LocalStorage(component_name=clean_id)
        from crucible.core.promotion.promotion import unreject_cluster_representative
        try:
            unreject_cluster_representative(storage, cluster_id)
            logger.info(f"Successfully unsuppressed cluster {cluster_id} for {clean_id}")
        except Exception as e:
            logger.exception(f"CRITICAL: Failed to unsuppress cluster {cluster_id}: {e}")
            raise

    