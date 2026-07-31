from __future__ import annotations
import json
from pathlib import Path
from typing import Dict


def _suite_dir(root: Path, application: str, sut: str) -> Path:
    """
    Behavioural Test Suite directory for a given Application/SUT:

        suites/<Application>/<SUT>/Gold/
    """
    return root / "suites" / application / sut / "Gold"


def _labels_path(root: Path, application: str, sut: str) -> Path:
    return _suite_dir(root, application, sut) / "semantic_labels.json"


def _ensure_suite_dir(root: Path, application: str, sut: str) -> Path:
    suite_dir = _suite_dir(root, application, sut)
    suite_dir.mkdir(parents=True, exist_ok=True)
    return suite_dir


def _validate_semantic_labels(data: Dict) -> None:
    if not isinstance(data, dict):
        raise ValueError("semantic_labels.json must be a JSON object.")
    if "semantic_labels" not in data:
        raise ValueError("semantic_labels.json must contain a 'semantic_labels' object.")
    labels = data["semantic_labels"]
    if not isinstance(labels, dict):
        raise ValueError("'semantic_labels' must be an object mapping field → label.")
    for k, v in labels.items():
        if not isinstance(k, str):
            raise ValueError("All field names in 'semantic_labels' must be strings.")
        if not isinstance(v, str):
            raise ValueError(f"Semantic label for field '{k}' must be a string.")


def load_suite_metadata(application: str, sut: str, root: Path) -> Dict:
    path = _labels_path(root, application, sut)
    if not path.exists():
        return {"semantic_labels": {}}
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    _validate_semantic_labels(data)
    return data


def save_suite_metadata(application: str, sut: str, root: Path, data: Dict) -> None:
    _ensure_suite_dir(root, application, sut)
    _validate_semantic_labels(data)
    path = _labels_path(root, application, sut)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def list_labels(application: str, sut: str, root: Path) -> Dict[str, str]:
    data = load_suite_metadata(application, sut, root)
    return data.get("semantic_labels", {})


def add_label(application: str, sut: str, root: Path, field: str, label: str) -> None:
    data = load_suite_metadata(application, sut, root)
    labels = data.get("semantic_labels", {})
    labels[field] = label
    data["semantic_labels"] = labels
    save_suite_metadata(application, sut, root, data)


def remove_label(application: str, sut: str, root: Path, field: str) -> None:
    data = load_suite_metadata(application, sut, root)
    labels = data.get("semantic_labels", {})
    if field in labels:
        del labels[field]
    data["semantic_labels"] = labels
    save_suite_metadata(application, sut, root, data)
