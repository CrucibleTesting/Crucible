# crucible/core/promotion/class_engine.py

from __future__ import annotations

from typing import Any, Dict


def create_or_update_class(
    storage: Any,
    cluster_id: str,
    exemplar_id: str,
) -> str:
    """
    Minimal class metadata management.

    FIX:
    ----
    - Use storage.write_classes(...) (the working API from review_engine).
    - Keep the correct shape: { "classes": { "C_<cluster_id>": {...} } }.
    """

    class_id = f"C_{cluster_id}"

    try:
        classes: Dict[str, Any] = storage.load_classes()
    except Exception:
        classes = {}

    if classes is None:
        classes = {}

    # Ensure top-level "classes" key exists
    classes.setdefault("classes", {})

    # Store/update class metadata
    classes["classes"][class_id] = {
        "cluster_id": cluster_id,
        "exemplar_id": exemplar_id,
    }

    # ------------------------------------------------------------
    # OLD (WRONG) PERSISTENCE ATTEMPT — LEFT FOR REFERENCE
    # ------------------------------------------------------------
    # if hasattr(storage, "_write_classes"):
    #     storage._write_classes(classes)

    # NEW: use the same API that worked in review_engine
    storage.write_classes(classes)

    return class_id
