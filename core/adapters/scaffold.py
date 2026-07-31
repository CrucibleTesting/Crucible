import os
import sys
import io
import json
import shlex
import logging
import warnings
import subprocess
import contextlib
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional
from crucible.core.adapters.adapter_discovery import discover_config_components
from crucible.core.storage import LocalStorage
from crucible.core.adapters.runner import create_sut_wrapper

logger = logging.getLogger("crucible.scaffold")


@contextlib.contextmanager
def silence_sut_output():
    """
    Suppresses stdout, stderr, warnings, and logging within the active execution thread.
    Used as a fallback safety layer during storage operations.
    """
    buffer = io.StringIO()
    previous_log_level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
                yield
    finally:
        logging.disable(previous_log_level)


def extract_seeds_for_component(component_name: str, component_config: Dict[str, Any]) -> List[str]:
    """
    Subprocess-isolated seed discovery. Supports both Python modules and external binaries
    without importing anything into Crucible's main process memory space.
    """
    # 1. Direct seeds list in configuration
    if "seeds" in component_config and isinstance(component_config["seeds"], list):
        seeds = [str(s).strip() for s in component_config["seeds"] if str(s).strip()]
        if seeds:
            return seeds

    command_string = component_config.get("command", "")
    if not command_string:
        return []

    cwd = os.getcwd()
    parts = shlex.split(command_string)
    env = os.environ.copy()
    env["PYTHONWARNINGS"] = "ignore"
    env["PYTHONPATH"] = f".:{env.get('PYTHONPATH', '')}"

    # 2. Python Module seed discovery via isolated subprocess
    if "-m" in parts:
        try:
            mod_idx = parts.index("-m") + 1
            if mod_idx < len(parts):
                module_name = parts[mod_idx]
                runner_script = f"""
import sys, json, importlib
mod = importlib.import_module("{module_name}")
if hasattr(mod, "seed_inputs"):
    attr = getattr(mod, "seed_inputs")
    seeds = attr() if callable(attr) else attr
    print(json.dumps(list(seeds)))
"""
                res = subprocess.run(
                    [sys.executable, "-c", runner_script],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    cwd=cwd,
                    env=env,
                    timeout=5.0
                )
                if res.returncode == 0 and res.stdout.strip():
                    data = json.loads(res.stdout.strip())
                    if isinstance(data, list):
                        return [str(item).strip() for item in data if str(item).strip()]
        except Exception as e:
            logger.debug(f"Isolated seed extraction failed for '{component_name}': {e}")

    # 3. Non-Python / CLI Binary fallback (--seeds flag)
    try:
        cmd = parts + ["--seeds"]
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=cwd,
            env=env,
            timeout=5.0
        )
        if res.returncode == 0 and res.stdout.strip():
            try:
                data = json.loads(res.stdout.strip())
                if isinstance(data, list):
                    return [str(item).strip() for item in data if str(item).strip()]
            except json.JSONDecodeError:
                return [line.strip() for line in res.stdout.splitlines() if line.strip()]
    except Exception as e:
        logger.debug(f"CLI --seeds execution failed for '{component_name}': {e}")

    return []


def initialize_workspace_layers(
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> List[str]:
    """
    Synchronous workspace layer initialization using subprocess-isolated seed extraction.
    Scans .crucible.json for active adapters, bootstraps folder structures,
    populates candidate pools, and runs initial staging passes.
    """
    adapters = discover_config_components()
    warnings_list: List[str] = []

    if not adapters:
        msg = "No active adapters discovered in .crucible.json."
        logger.warning(msg)
        return [msg]

    total_adapters = len(adapters)
    env_root = os.getenv("CRUCIBLE_ROOT")
    root_dir = Path(env_root).resolve() if env_root else Path(os.getcwd()).resolve() / ".crucible"
    suites_dir = root_dir / "suites"

    for idx, (adapter_name, adapter_config) in enumerate(adapters.items(), start=1):
        if progress_callback:
            progress_callback(idx - 1, total_adapters)

        if not isinstance(adapter_config, dict):
            adapter_config = {"command": str(adapter_config)}

        command_string = adapter_config.get("command", "")
        semantic_root_path = adapter_config.get("semantic_root", "")

        base = suites_dir / adapter_name
        bronze = base / "Bronze"
        silver = base / "Silver"
        gold = base / "Gold"

        candidate_pool_file = bronze / "candidate_pool.txt"
        is_new_pool = not candidate_pool_file.exists() or candidate_pool_file.stat().st_size == 0

        seeds: List[str] = []
        if is_new_pool:
            seeds = extract_seeds_for_component(adapter_name, adapter_config)
            if not seeds:
                err_msg = f"Component '{adapter_name}': No seed_inputs() found or module unreachable."
                logger.warning(err_msg)
                warnings_list.append(err_msg)
                continue

        bronze.mkdir(parents=True, exist_ok=True)
        silver.mkdir(parents=True, exist_ok=True)
        gold.mkdir(parents=True, exist_ok=True)

        file_blueprints = {
            silver / "snapshots.json": b'{"meta": {}, "cases": []}\n',
            silver / "snapshot_cache.json": b'{"sut_version": null, "command_signature": null, "entries": {}}\n',
            gold / "fixtures.json": b'{"meta": {}, "cases": []}\n',
            gold / "classes.json": b'{"classes": {}}\n'
        }

        for path, default_bytes in file_blueprints.items():
            if not path.exists():
                path.write_bytes(default_bytes)

        if is_new_pool and seeds:
            cleaned_content = "\n".join(seeds) + "\n"
            candidate_pool_file.write_text(cleaned_content, encoding="utf-8")
            logger.info(f"Hydrated candidate_pool.txt for '{adapter_name}' with {len(seeds)} seeds.")

        storage = LocalStorage(adapter_name)
        snapshots = storage.load_staging()

        if not snapshots.get("cases"):
            try:
                sut_executable = create_sut_wrapper(
                    command_string=command_string,
                    semantic_root=semantic_root_path
                )
                
                with silence_sut_output():
                    storage.generate_snapshots(sut=sut_executable, component_config=adapter_config)
                
                logger.info(f"Auto-staging pass completed for '{adapter_name}'.")
            except Exception as e:
                err_msg = f"Component '{adapter_name}': Auto-staging failed ({str(e)})."
                logger.error(err_msg)
                warnings_list.append(err_msg)

        if progress_callback:
            progress_callback(idx, total_adapters)

    return warnings_list