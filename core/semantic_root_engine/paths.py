from __future__ import annotations
import sys
from pathlib import Path

def assert_and_get_project_root() -> Path:
    """
    Boundary Guard: Enforces that Crucible must be run directly from 
    the project root directory containing the '.crucible.json' file.
    Fails fast and guides the user if executed from an incorrect folder.
    """
    cwd = Path.cwd().resolve()
    if not (cwd / ".crucible.json").exists():
        print("\n❌ Crucible Execution Error!", file=sys.stderr)
        print("Crucible must be run from the project root folder containing '.crucible.json'.", file=sys.stderr)
        print(f"Current terminal directory: {cwd}\n", file=sys.stderr)
        sys.exit(1)
    return cwd

def normalize_jsonpath(path: str | None) -> str:
    """
    Architectural Boundary Enforcer:
    Ensures all components evaluate identical string structures by
    systematically stripping JSONPath symbol prefixes (e.g., '$.' or '$').
    """
    if not path:
        return ""
    if path.startswith("$."):
        path = path[2:]
    elif path.startswith("$"):
        path = path[1:]
    return path.strip()

def get_global_config_path() -> Path:
    """
    Returns the resolved path to the global crucible configuration file
    located at the asserted project root.
    """
    return assert_and_get_project_root() / ".crucible.json"