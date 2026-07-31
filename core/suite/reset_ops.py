from pathlib import Path
from crucible.core.suite.clear_ops import clear_all
from crucible.core.storage.base import LocalStorage
from crucible.core.suite.runner import load_adapter


def _parse_adapter(adapter_path: str) -> tuple[str, str]:
    """
    adapter_path: "<application>.crucible.<sut>:run"
    """
    module_name, _, _ = adapter_path.partition(":")
    parts = module_name.split(".")
    application = parts[0]
    sut = parts[-1]
    return application, sut


def reset_and_generate_all(adapters, root: Path):
    """
    Clear all → regenerate staging snapshots for all adapters.
    """
    for adapter in adapters:
        app, sut = _parse_adapter(adapter)
        clear_all(app, sut, root)
        storage = LocalStorage(app, sut)
        sut_fn = load_adapter(adapter)
        storage._sut = sut_fn  # optional seeding
        storage.generate_snapshots(sut_fn)


def factory_reset(adapters, root: Path):
    """
    Clear EVERYTHING including candidate pools.
    """
    for adapter in adapters:
        app, sut = _parse_adapter(adapter)
        clear_all(app, sut, root)
        pool = root / "Suites" / app / sut / "Bronze" / "candidate_pool.txt"
        if pool.exists():
            pool.unlink()
