import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


def _get_env_text(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _get_env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _get_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


@dataclass(frozen=True)
class Config:
    discord_webhook_url: Optional[str]
    check_interval_min: int
    add_rate_threshold: float
    drop_rate_threshold: float
    min_abs_add_delta: int
    min_abs_drop_delta: int
    smoothing_n: int
    max_alerts_per_player: int
    dry_run: bool
    user_agent: str
    request_timeout_seconds: int

    @staticmethod
    def from_env() -> "Config":
        load_dotenv()

        return Config(
            discord_webhook_url=_get_env_text("DISCORD_WEBHOOK_URL"),
            check_interval_min=_get_env_int("CHECK_INTERVAL_MIN", 5),
            add_rate_threshold=_get_env_float("ADD_RATE_THRESHOLD", 4.0),
            drop_rate_threshold=_get_env_float("DROP_RATE_THRESHOLD", 4.0),
            min_abs_add_delta=_get_env_int("MIN_ABS_ADD_DELTA", 15),
            min_abs_drop_delta=_get_env_int("MIN_ABS_DROP_DELTA", 15),
            smoothing_n=max(1, _get_env_int("SMOOTHING_N", 3)),
            max_alerts_per_player=_get_env_int("MAX_ALERTS_PER_PLAYER", 3),
            dry_run=_get_env_bool("DRY_RUN", True),
            user_agent=_get_env_text("USER_AGENT", "Mozilla/5.0"),
            request_timeout_seconds=_get_env_int("REQUEST_TIMEOUT_SECONDS", 30),
        )


