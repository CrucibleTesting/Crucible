import os
from pathlib import Path


def _safe_write_text(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)


def _safe_truncate_json(path: Path, payload: str) -> None:
    _safe_write_text(path, payload + "\n")


def _safe_truncate_text(path: Path, payload: str = "") -> None:
    _safe_write_text(path, payload)


def _base(app: str, sut: str, root: Path) -> Path:
    return root / "suites" / app / sut


def clear_staging(app: str, sut: str, root: Path) -> None:
    path = _base(app, sut, root) / "Silver" / "snapshots.json"
    if path.exists():
        _safe_truncate_json(path, '{"meta": {}, "cases": []}')


def clear_golden(app: str, sut: str, root: Path) -> None:
    path = _base(app, sut, root) / "Gold" / "fixtures.json"
    if path.exists():
        _safe_truncate_json(path, '{"meta": {}, "cases": []}')


def clear_classes(app: str, sut: str, root: Path) -> None:
    path = _base(app, sut, root) / "Gold" / "classes.json"
    if path.exists():
        _safe_truncate_json(path, '{"classes": {}}')


def clear_candidate_pool(app: str, sut: str, root: Path) -> None:
    path = _base(app, sut, root) / "Bronze" / "candidate_pool.txt"
    if path.exists():
        _safe_truncate_text(path, "")


def clear_snapshot_cache(app: str, sut: str, root: Path) -> None:
    path = _base(app, sut, root) / "Silver" / "snapshot_cache.json"
    if path.exists():
        os.remove(path)


def clear_all(app: str, sut: str, root: Path) -> None:
    clear_staging(app, sut, root)
    clear_golden(app, sut, root)
    clear_classes(app, sut, root)
    clear_candidate_pool(app, sut, root)
    clear_snapshot_cache(app, sut, root)
