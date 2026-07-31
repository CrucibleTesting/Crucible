from __future__ import annotations

import importlib
import json
from typing import Any, Dict, Tuple

from crucible.core.normalisation.semantic_root import _get_subtree  # reuse helper
from crucible.core.normalisation.truncation import MAX_SNAPSHOT_BYTES


class AdapterLintError(Exception):
    pass


def _load_adapter(adapter_path: str):
    module_name, _, fn_name = adapter_path.partition(":")
    if not module_name or not fn_name:
        raise AdapterLintError(f"Invalid adapter path: {adapter_path}")
    module = importlib.import_module(module_name)
    return getattr(module, fn_name)


def _run_adapter(adapter_fn, sample_input: str) -> Any:
    return adapter_fn(sample_input)


def lint_adapter(adapter_path: str, sample_input: str, semantic_root: str | None = None) -> Tuple[bool, str]:
    """
    Adapter conformance checks:
      - returns JSON-serialisable object
      - top-level is dict
      - snapshot size < MAX_SNAPSHOT_BYTES
      - semantic_root (if provided) resolves
      - no pre-normalisation logic (best-effort heuristic)
    """
    adapter_fn = _load_adapter(adapter_path)

    try:
        raw = _run_adapter(adapter_fn, sample_input)
    except Exception as e:
        return False, f"Adapter raised exception: {e}"

    # JSON-serialisable?
    try:
        encoded = json.dumps(raw)
    except Exception as e:
        return False, f"Adapter output is not JSON-serialisable: {e}"

    # Size check
    if len(encoded.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        return False, f"Adapter output exceeds max snapshot size ({MAX_SNAPSHOT_BYTES} bytes)"

    # Top-level dict
    if not isinstance(raw, dict):
        return False, "Adapter output must be a dict at the top level"

    # Semantic root resolution (if provided)
    if semantic_root:
        subtree = _get_subtree(raw, semantic_root)
        if subtree is raw:
            return False, f"Semantic root '{semantic_root}' did not resolve in adapter output"

    # Heuristic: no pre-normalisation (we just warn if it looks too 'clean')
    # e.g. very shallow, very few keys, no meta/debug fields.
    if len(raw.keys()) <= 2:
        return False, "Adapter output looks pre-normalised (too few top-level keys)"

    return True, "Adapter passed lint checks"
