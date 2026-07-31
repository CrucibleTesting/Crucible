from __future__ import annotations
from typing import Dict, Any, Callable
from jsonschema import validate
from crucible.core.storage.config import Config
from crucible.core.schemas.schemas import GOLDEN_SCHEMA
from crucible.core.normalisation.normaliser import Normaliser
from crucible.core.promotion.class_engine import create_or_update_class
from crucible.core.config.sut_meta import get_sut_version

def promote_cluster_representative(
    storage: Any,
    sut: Callable[[str], Any],
    cluster_id: str,
) -> None:
    staging = storage.load_staging()
    golden = storage.load_golden()
    cases = staging.get("cases", [])
    
    cluster_cases = [
        c for c in cases
        if c.get("meta", {}).get("cluster_id") == cluster_id
    ]
    if not cluster_cases:
        return

    exemplar = cluster_cases[0]
    case_id = exemplar["id"]
    input_str = exemplar["input"]
    expected = sut(input_str) or {}

    golden_cases = golden.get("cases", [])
    golden_cases = [
        c for c in golden_cases
        if c.get("meta", {}).get("cluster_id") != cluster_id
    ]
    golden["cases"] = golden_cases

    classes = storage.load_classes() or {}
    classes.setdefault("classes", {})
    class_id = f"C_{cluster_id}"
    classes["classes"][class_id] = {
        "cluster_id": cluster_id,
        "exemplar_id": case_id,
    }
    storage.write_classes(classes)

    roots = storage.get_active_semantic_roots()
    normaliser = Normaliser(semantic_roots=roots, adapter_id=storage.resolver)
    
    snapshot = storage.get_snapshot(cluster_id)
    if snapshot is None:
        signature = normaliser.normalise(expected).identity
    else:
        signature = normaliser.normalise(snapshot).identity

    # Construct component configuration context for multi-runtime execution
    component_config = {"command": storage.resolver}
    sut_ver = get_sut_version(component_config)

    fixture_meta = {
        "state": "golden",
        "promoted_at": Config.now(),
        "resolver": storage.resolver,
        "sut_version": sut_ver,  # ✅ Fixed contextual version resolution
        "cluster_id": cluster_id,
        "class": class_id,
        "signature": signature,
    }
    
    fixture = {
        "id": case_id,
        "input": input_str,
        "expected": expected,
        "meta": fixture_meta,
    }
    
    golden.setdefault("cases", []).append(fixture)
    validate(instance=golden, schema=GOLDEN_SCHEMA)
    storage._write_golden(golden)

    # ✅ Performance Fix: Batch approve all cluster items in a single I/O pass
    all_cluster_case_ids = [c["id"] for c in cluster_cases]
    storage.bulk_approve(all_cluster_case_ids, component_config=component_config)