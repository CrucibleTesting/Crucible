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
    subprocess. Guarantees zero leakage of native stderr into Crucible's TUI while
    defensively capturing SUT crashes and non-JSON output into structured
    payloads.
    """
    parts = shlex.split(command_string)
    cwd = os.getcwd()

    def subprocess_sut_invoker(payload: Any) -> Any:
        env = os.environ.copy()
        env["PYTHONWARNINGS"] = "ignore"
        env["PYTHONPATH"] = f".:{env.get('PYTHONPATH', '')}"

        if "-m" in parts:
            mod_idx = parts.index("-m") + 1
            if mod_idx < len(parts):
                module_name = parts[mod_idx]
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
                cmd = parts + [json.dumps(payload)]
        else:
            cmd = parts + [json.dumps(payload)]

        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd,
                env=env,
                timeout=10.0,
            )

            stdout_clean = res.stdout.strip()
            stderr_clean = res.stderr.strip()

            # 1. Handle SUT process crashes (exit code != 0)
            if res.returncode != 0:
                err_details = stderr_clean if stderr_clean else f"Process exited with code {res.returncode}"
                logger.error(f"SUT Execution Failed for payload '{payload}': {err_details}")
                return {
                    "__error__": True,
                    "type": "PROCESS_CRASH",
                    "exit_code": res.returncode,
                    "reason": err_details,
                    "raw_stdout": stdout_clean,
                }

            # 2. Try parsing stdout as JSON
            try:
                return json.loads(stdout_clean)
            except json.JSONDecodeError as e:
                return {
                    "__error__": True,
                    "type": "INVALID_JSON_OUTPUT",
                    "reason": f"SUT stdout is not valid JSON: {str(e)}",
                    "raw_stdout": stdout_clean,
                    "stderr": stderr_clean,
                }

        except subprocess.TimeoutExpired:
            return {
                "__error__": True,
                "type": "TIMEOUT",
                "reason": "SUT execution timed out after 10.0 seconds",
            }
        except Exception as e:
            return {
                "__error__": True,
                "type": "RUNNER_EXECUTION_FAILURE",
                "reason": str(e),
            }

    return subprocess_sut_invoker