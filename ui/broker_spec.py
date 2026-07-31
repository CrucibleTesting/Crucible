from typing import Any, Dict, List, Callable, Optional
from pathlib import Path


class AbstractSystemBroker:
    def get_components(self) -> List[Dict[str, str]]:
        raise NotImplementedError

    def has_active_workspaces(self) -> bool:
        raise NotImplementedError

    def has_registered_components(self) -> bool:
        raise NotImplementedError

    def is_system_hydrated(self) -> bool:
        raise NotImplementedError

    def hydrate_system(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[str]:
        raise NotImplementedError

    def open_candidate_pool_in_editor(self, component_id: str) -> Path:
        raise NotImplementedError

    def sync_candidate_pool(self, component_id: str) -> Dict[str, int]:
        raise NotImplementedError

    def run_pipeline(
        self,
        component_id: str,
        progress_callback: Callable[[int, int], None]
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def fetch_reviews(self, component_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError