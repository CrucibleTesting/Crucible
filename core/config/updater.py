from __future__ import annotations
import json
from pathlib import Path
from crucible.core.semantic_root_engine.paths import assert_and_get_project_root

def save_confirmed_semantic_root(component_name: str, chosen_root: str) -> Path:
    """
    Appends the developer-approved semantic root directly back to the project's
    local .crucible.json file. This eliminates background state drifting.
    
    Returns:
        Path: The absolute path to the modified configuration file.
    """
    project_root = assert_and_get_project_root()
    config_path = project_root / ".crucible.json"
    
    # 1. Read existing config safely
    if config_path.exists():
        try:
            config_data = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            config_data = {}
    else:
        config_data = {}
        
    # 2. Ensure nested structural blocks exist
    components = config_data.setdefault("components", {})
    component_entry = components.setdefault(component_name, {})
    
    # 3. Format path uniformly with standard JSONPath prefixing for clarity
    component_entry["semantic_root"] = f"$.{chosen_root}"
    
    # 4. Atomic Flush back to project root workspace
    temp_path = config_path.with_suffix(".tmp")
    try:
        temp_path.write_text(json.dumps(config_data, indent=4) + "\n", encoding="utf-8")
        temp_path.replace(config_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
            
    return config_path