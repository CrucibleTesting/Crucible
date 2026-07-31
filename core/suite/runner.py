# crucible/core/runner.py

import importlib

def load_adapter(path: str):
    module_name, func_name = path.split(":")
    module = importlib.import_module(module_name)
    return getattr(module, func_name)
