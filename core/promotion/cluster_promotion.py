# crucible/core/promotion/cluster_promotion.py

from __future__ import annotations

from typing import Any, Callable

from crucible.core.promotion import promote_cluster_representative


def promote_cluster(
    storage: Any,
    sut: Callable[[str], Any],
    cluster_id: str,
) -> None:
    """
    Entry point used by the TUI to promote a cluster.

    Delegates to the promotion subsystem.
    """
    promote_cluster_representative(storage, sut, cluster_id)
