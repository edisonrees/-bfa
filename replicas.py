"""Replica identity + password sharding for horizontal scale."""

from __future__ import annotations

import os
from dataclasses import dataclass

from config import config


@dataclass(frozen=True)
class ReplicaInfo:
    replica_id: int
    total_replicas: int

    @property
    def label(self) -> str:
        return f"{self.replica_id + 1}/{self.total_replicas}"

    def owns_index(self, index: int) -> bool:
        if self.total_replicas <= 1:
            return True
        return index % self.total_replicas == self.replica_id

    def shard_size(self, total_items: int) -> int:
        if total_items <= 0:
            return 0
        if self.total_replicas <= 1:
            return total_items
        # indices i where i % N == rid
        return (total_items + self.total_replicas - 1 - self.replica_id) // self.total_replicas


def resolve_replica_info() -> ReplicaInfo:
    """Prefer Railway env, then MOCKA config."""
    raw_id = (
        os.getenv("RAILWAY_REPLICA_ID")
        or os.getenv("REPLICA_ID")
        or str(config.REPLICA_ID)
    )
    raw_total = (
        os.getenv("RAILWAY_REPLICA_TOTAL")
        or os.getenv("TOTAL_REPLICAS")
        or str(config.TOTAL_REPLICAS)
    )
    try:
        replica_id = max(0, int(str(raw_id).strip() or "0"))
    except ValueError:
        replica_id = 0
    try:
        total = max(1, int(str(raw_total).strip() or "1"))
    except ValueError:
        total = 1
    if replica_id >= total:
        replica_id = replica_id % total
    return ReplicaInfo(replica_id=replica_id, total_replicas=total)


replica_info = resolve_replica_info()
