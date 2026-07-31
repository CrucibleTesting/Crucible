import importlib.util
import os
import tomllib

# Simple in-memory cache to prevent infinite disk-reads during UI rendering
_PLUGIN_CACHE = {}


def get_plugin_dir() -> str:
    """Reads the configuration to find the user's plugin directory."""
    try:
        with open("crucible.toml", "rb") as f:
            config = tomllib.load(f)
            return config.get("crucible", {}).get("plugins_dir", "./my_plugins")
    except FileNotFoundError:
        return "./my_plugins"


def load_explainer(sut_name: str):
    """Dynamically loads and caches a specific user plugin on demand."""
    if not sut_name:
        return None

    # Hit the runtime cache first to guarantee high-performance UI loops
    if sut_name in _PLUGIN_CACHE:
        return _PLUGIN_CACHE[sut_name]

    plugins_dir = get_plugin_dir()
    file_path = os.path.join(plugins_dir, f"{sut_name}.py")

    if not os.path.exists(file_path):
        _PLUGIN_CACHE[sut_name] = None  # Cache negative results too
        return None

    try:
        spec = importlib.util.spec_from_file_location(sut_name, file_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            explain_fn = getattr(module, "explain", None)
            _PLUGIN_CACHE[sut_name] = explain_fn
            return explain_fn
    except Exception:
        # Prevent the UI thread from crashing; fall back gracefully
        _PLUGIN_CACHE[sut_name] = None

    return None