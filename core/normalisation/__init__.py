"""
CRUCIBLE v3.3 — Normalisation Subsystem

This package exposes the public API for:
  - Normaliser (main v3.3 pipeline)
  - lint_adapter (adapter conformance checks)
"""

from .normaliser import Normaliser
from .adapter_lint import lint_adapter

__all__ = [
    "Normaliser",
    "lint_adapter",
]