SCREEN_REGISTRY = {}
SCREEN_CACHE = {}

def register_screen(name: str):
    def decorator(cls):
        SCREEN_REGISTRY[name] = cls
        return cls
    return decorator