from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional

from .scraper import PlayerRow
from .state import InMemoryState, utcnow


@dataclass
class Alert:
    player_name: str
    team_pos: Optional[str]
    add_delta: int
    drop_delta: int
    add_rate_per_min: float
    drop_rate_per_min: float
    kind: str  # "add" or "drop"


def minutes_between(now: datetime, then: datetime) -> float:
    return max((now - then).total_seconds() / 60.0, 1e-6)


def evaluate_rows(
    state: InMemoryState,
    rows: Iterable[PlayerRow],
    *,
    add_rate_threshold: float,
    drop_rate_threshold: float,
    min_abs_add_delta: int,
    min_abs_drop_delta: int,
    max_alerts_per_player: int,
) -> List[Alert]:
    now = utcnow()
    alerts: List[Alert] = []

    for r in rows:
        history = state.get_or_create_history(r.name)
        prev = history.get_previous()

        if prev is not None:
            dt_min = minutes_between(now, prev.ts)
            add_delta = r.adds - prev.adds
            drop_delta = r.drops - prev.drops
            add_rate = float(add_delta) / dt_min
            drop_rate = float(drop_delta) / dt_min

            # Enforce minimum absolute changes as well as rate thresholds
            if add_delta >= min_abs_add_delta and add_rate >= add_rate_threshold:
                if state.get_alert_count(r.name) < max_alerts_per_player:
                    alerts.append(
                        Alert(
                            player_name=r.name,
                            team_pos=r.team_pos,
                            add_delta=add_delta,
                            drop_delta=drop_delta,
                            add_rate_per_min=add_rate,
                            drop_rate_per_min=drop_rate,
                            kind="add",
                        )
                    )
                    state.increment_alert_count(r.name)

            if drop_delta >= min_abs_drop_delta and drop_rate >= drop_rate_threshold:
                if state.get_alert_count(r.name) < max_alerts_per_player:
                    alerts.append(
                        Alert(
                            player_name=r.name,
                            team_pos=r.team_pos,
                            add_delta=add_delta,
                            drop_delta=drop_delta,
                            add_rate_per_min=add_rate,
                            drop_rate_per_min=drop_rate,
                            kind="drop",
                        )
                    )
                    state.increment_alert_count(r.name)

        # Record snapshot at the end
        history.add_snapshot(adds=r.adds, drops=r.drops, ts=now)

    return alerts


