import os
import sys
import json
import shlex
import logging
import subprocess
from typing import Callable, Any

logger = logging.getLogger("crucible.runner")


def create_sut_wrapper(command_string: str, semantic_root: str = "") -> Callable[[Any], Any]:
    """
    Returns an executable SUT wrapper that runs payloads in an isolated 
    subprocess. Guarantees zero leakage of native stderr, warnings, or logging 
    into Crucible's main process and TUI.
    """
    parts = shlex.split(command_string)
    cwd = os.getcwd()

    def subprocess_sut_invoker(payload: Any) -> Any:
        env = os.environ.copy()
        env["PYTHONWARNINGS"] = "ignore"
        env["PYTHONPATH"] = f".:{env.get('PYTHONPATH', '')}"

        # If the command uses '-m <module_name>'
        if "-m" in parts:
            mod_idx = parts.index("-m") + 1
            if mod_idx < len(parts):
                module_name = parts[mod_idx]

                # Script executed inside the isolated child process
                runner_script = f"""
import sys, json, importlib
mod = importlib.import_module("{module_name}")
payload = json.loads(sys.argv[1])

if hasattr(mod, "parse"):
    res = mod.parse(payload)
elif hasattr(mod, "run"):
    res = mod.run(payload)
elif hasattr(mod, "main"):
    res = mod.main(payload)
elif callable(mod):
    res = mod(payload)
else:
    raise RuntimeError("No entrypoint found in module '{module_name}'")

print(json.dumps(res))
"""
                cmd = [sys.executable, "-c", runner_script, json.dumps(payload)]
        else:
            # Fallback for direct CLI executables
            cmd = parts + [json.dumps(payload)]

        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,  # Drops all native C/python stderr output
                text=True,
                cwd=cwd,
                env=env,
                check=True
            )
            stdout_clean = res.stdout.strip()
            try:
                return json.loads(stdout_clean)
            except json.JSONDecodeError:
                return stdout_clean
        except subprocess.CalledProcessError as e:
            logger.error(f"Isolated SUT execution failed for payload: {payload}")
            raise e

    return subprocess_sut_invoker