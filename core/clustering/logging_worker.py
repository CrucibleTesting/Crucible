# crucible/core/clustering/logging_worker.py

from __future__ import annotations
import json
import threading
from queue import Queue
from typing import Optional, Dict, Any, TextIO


class LoggingWorker:
    """
    Background worker that drains a queue of event dicts and writes them
    as JSONL lines to a file. Uses a poison pill (None) for shutdown.
    """

    def __init__(self, queue: Queue, file: TextIO) -> None:
        self._queue = queue
        self._file = file
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while True:
            event: Optional[Dict[str, Any]] = self._queue.get()
            if event is None:
                # Poison pill: flush and exit
                self._file.flush()
                break
            line = json.dumps(event)
            self._file.write(line + "\n")

    def join(self) -> None:
        self._thread.join()
