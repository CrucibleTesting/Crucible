import os
import sys

# Silence native C-extension, Arrow, and IPC memory-map warnings prior to imports
os.environ["ARROW_DEBUG_MEMORY_POOL"] = "0"
os.environ["ARROW_LOG_LEVEL"] = "ERROR"
os.environ["PYTHONWARNINGS"] = "ignore"

import logging
from pathlib import Path

from ui.engine import SimpleEngine
from ui.broker_spec import AbstractSystemBroker
from crucible.core.lifecycle.ui_broker import CoreUIBroker
import ui.screens  # Explicitly executes register_screen decorators

log_dir = Path(".crucible")
log_dir.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=log_dir / "crucible.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


def main():
    broker = CoreUIBroker()

    if broker.has_registered_components() and not broker.is_system_hydrated():
        initial_screen = "cold_boot"
    else:
        initial_screen = "component_list"

    engine = SimpleEngine(
        broker=broker,
        initial_screen=initial_screen
    )

    try:
        engine.run()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()