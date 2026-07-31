import random
import threading
import copy
import time
from collections import defaultdict
from typing import Any, Dict, Callable, List

class AppContext:
    """Enterprise-Grade Isolated State Container with True Per-Key Optimistic Concurrency."""
    def __init__(self):
        self._lock = threading.RLock()
        self._versions: Dict[str, int] = defaultdict(int)
        self.store: Dict[str, Any] = {
            "global_counter": 0,
            "session_user": "Developer",
            "system_status": "Nominal",
        }
        self._data_registry: Dict[str, Any] = {
            "records": []
        }

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            if key in self._data_registry:
                return copy.deepcopy(self._data_registry[key])
            val = self.store.get(key, default)
            if isinstance(val, (int, float, str, bool, type(None))):
                return val
            return copy.deepcopy(val)

    def get_records_slice(self, offset: int, limit: int) -> List[Dict[str, Any]]:
        """
        High-performance reader designed for large datasets (e.g., 1000 test cases).
        Bypasses slow deepcopy calls by utilizing shallow list slicing.
        """
        with self._lock:
            records = self._data_registry.get("records", [])
            return [item.copy() for item in records[offset:offset + limit]]

    def get_records_count(self) -> int:
        """Safely retrieves the total count of test cases in the data registry."""
        with self._lock:
            return len(self._data_registry.get("records", []))

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._data_registry:
                self._data_registry[key] = copy.deepcopy(value)
            else:
                self.store[key] = copy.deepcopy(value)
            self._versions[key] += 1

    def mutate_atomic(self, key: str, func: Callable[[Any], Any], max_retries: int = 7) -> None:
        """
        Executes a non-blocking optimistic concurrency mutation loop with per-key tracking.
        """
        for attempt in range(max_retries):
            with self._lock:
                baseline_version = self._versions[key]
                is_registry = key in self._data_registry
                raw_val = self._data_registry[key] if is_registry else self.store.get(key)
                current_val = raw_val if isinstance(raw_val, (int, float, str, bool, type(None))) else copy.deepcopy(raw_val)
                
                updated_val = func(current_val)
                
            with self._lock:
                if self._versions[key] == baseline_version:
                    final_val = updated_val if isinstance(updated_val, (int, float, str, bool, type(None))) else copy.deepcopy(updated_val)
                    if is_registry:
                        self._data_registry[key] = final_val
                    else:
                        self.store[key] = final_val
                    self._versions[key] += 1
                    return  # Success!
                    
            base_delay = 0.002 * (2 ** attempt)
            jitter = random.uniform(0, 0.5 * base_delay)
            time.sleep(base_delay + jitter)
            
        raise RuntimeError(f"State mutation on key '{key}' failed after {max_retries} isolated concurrent collision attempts.")