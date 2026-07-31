from __future__ import annotations
import hashlib
import os
import sys
from pathlib import Path
from typing import Optional
from crucible.core.semantic_root_engine.paths import assert_and_get_project_root

# Global In-Memory Cache Singleton
_CACHED_SUT_VERSION: Optional[str] = None

def _compute_generic_sut_hash(component_config: dict) -> str:
    """
    Computes a unique signature for any SUT by hashing its target 
    executable binary, script, or configuration footprint.
    """
    # 1. Grab the command string from the user's .crucible.json config
    command_str = component_config.get("command", "")
    if not command_str:
        return "static-env"

    try:
        project_root = assert_and_get_project_root()
        
        # 2. Extract the likely binary/executable name from the start of the command
        # e.g., "node ./dist/app.js" -> look at the app.js or the node setup
        parts = command_str.split()
        
        # Look for the first argument that looks like a real file path target
        target_file = None
        for part in parts:
            potential_path = project_root / part
            if potential_path.is_file():
                target_file = potential_path
                break
                
        # 3. If it's a file (like a Go/Rust binary or compiled JS pack), hash its structural traits
        if target_file and target_file.exists():
            stat = target_file.stat()
            # Fast fingerprinting: Combine size + modification time to avoid reading massive binaries
            fingerprint = f"{target_file.name}-{stat.st_size}-{stat.st_mtime}"
            return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:12]
            
        # 4. Fallback: Hash the raw command string if it's a global system command (like "curl")
        return hashlib.sha256(command_str.encode("utf-8")).hexdigest()[:12]

    except Exception:
        return "fallback-generic"

def get_sut_version(component_config: dict) -> str:
    """
    Performance-Optimized & Language-Agnostic:
    Returns the unique hash representing the active SUT version structure.
    
    Bypasses disk I/O after initial module boot by caching the signature in RAM.
    Works seamlessly whether the SUT is Python, Go, Node.js, or an executable binary.
    """
    global _CACHED_SUT_VERSION
    if _CACHED_SUT_VERSION is None:
        _CACHED_SUT_VERSION = _compute_generic_sut_hash(component_config)
    return _CACHED_SUT_VERSION