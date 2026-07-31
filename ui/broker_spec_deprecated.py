from typing import Any, Dict, List, Callable, Optional


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

    def edit_and_sync_candidate_pool(self, component_id: str) -> Dict[str, Any]:
        raise NotImplementedError

    def run_pipeline(
        self,
        component_id: str,
        progress_callback: Callable[[int, int], None]
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def fetch_reviews(self, component_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError