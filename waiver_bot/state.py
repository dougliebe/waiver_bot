from __future__ import annotations

import collections
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Deque, Dict, Optional


@dataclass
class Snapshot:
    adds: int
    drops: int
    ts: datetime


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlayerHistory:
    def __init__(self, smoothing_n: int) -> None:
        self.smoothing_n: int = max(1, smoothing_n)
        self.snapshots: Deque[Snapshot] = collections.deque(maxlen=self.smoothing_n)

    def add_snapshot(self, adds: int, drops: int, ts: Optional[datetime] = None) -> None:
        self.snapshots.append(
            Snapshot(adds=adds, drops=drops, ts=ts or utcnow())
        )

    def get_previous(self) -> Optional[Snapshot]:
        if len(self.snapshots) == 0:
            return None
        return self.snapshots[-1]

    def get_first(self) -> Optional[Snapshot]:
        if len(self.snapshots) == 0:
            return None
        return self.snapshots[0]

    def size(self) -> int:
        return len(self.snapshots)


class InMemoryState:
    def __init__(self, smoothing_n: int) -> None:
        self.smoothing_n: int = max(1, smoothing_n)
        self.player_name_to_history: Dict[str, PlayerHistory] = {}
        # Track alerts per player per UTC day
        self.alert_counts: Dict[str, Dict[str, int]] = {}

    def get_or_create_history(self, player_name: str) -> PlayerHistory:
        history = self.player_name_to_history.get(player_name)
        if history is None:
            history = PlayerHistory(self.smoothing_n)
            self.player_name_to_history[player_name] = history
        return history

    def increment_alert_count(self, player_name: str) -> int:
        day_key = utcnow().strftime("%Y-%m-%d")
        per_day = self.alert_counts.setdefault(player_name, {})
        per_day[day_key] = per_day.get(day_key, 0) + 1
        # Garbage collect old days to keep small
        for key in list(per_day.keys()):
            if key != day_key:
                # keep only current day counts
                del per_day[key]
        return per_day[day_key]

    def get_alert_count(self, player_name: str) -> int:
        day_key = utcnow().strftime("%Y-%m-%d")
        per_day = self.alert_counts.get(player_name, {})
        return per_day.get(day_key, 0)


