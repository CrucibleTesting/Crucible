from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

@dataclass
class NormalisedSnapshot:
    canonical: Dict[str, Any]
    identity: str
    meta: Dict[str, Any]

@dataclass
class ClusterStats:
    count: int = 0
    first_seen_ts_utc: float = field(default_factory=lambda: time.time())
    last_seen_ts_utc: float = field(default_factory=lambda: time.time())
    first_seen_monotonic_ns: int = field(default_factory=lambda: time.monotonic_ns())
    last_seen_monotonic_ns: int = field(default_factory=lambda: time.monotonic_ns())

    def update(self) -> None:
        now_utc = time.time()
        now_mono = time.monotonic_ns()
        self.count += 1
        self.last_seen_ts_utc = now_utc
        self.last_seen_monotonic_ns = now_mono

@dataclass
class Cluster:
    identity_key: str
    cluster_id: str  # Mandatory, stable structural hash
    label: str = "Unlabelled behaviour"
    stats: ClusterStats = field(default_factory=ClusterStats)
    representative: Optional[Dict[str, Any]] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    lineage: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ClusterAssignment:
    cluster_id: str
    is_new_cluster: bool
    cluster_label: str
    snapshot_count: int