from __future__ import annotations

import asyncio
import signal
import logging
from typing import Optional

from .config import Config
from .logic import evaluate_rows
from .notifier import DiscordNotifier
from .scraper import fetch_and_parse_buzz_index
from .state import InMemoryState


async def send_alerts(notifier: DiscordNotifier, alerts) -> None:
    for a in alerts:
        title = f"{a.player_name} {f'({a.team_pos})' if a.team_pos else ''}"
        lines = [
            f"Kind: {a.kind}",
            f"Add Δ: {a.add_delta} (rate {a.add_rate_per_min:.2f}/min)",
            f"Drop Δ: {a.drop_delta} (rate {a.drop_rate_per_min:.2f}/min)",
        ]
        await notifier.send("\n".join(lines), title=title)


async def run_once(cfg: Config, state: InMemoryState, date_override: Optional[str]) -> None:
    rows = await fetch_and_parse_buzz_index(
        date_yyyy_mm_dd=date_override,
        user_agent=cfg.user_agent,
        timeout_seconds=cfg.request_timeout_seconds,
    )
    logging.info(f"Fetched {len(rows)} rows from Yahoo (date={date_override or 'latest'})")
    is_baseline = len(state.player_name_to_history) == 0
    alerts = evaluate_rows(
        state=state,
        rows=rows,
        add_rate_threshold=cfg.add_rate_threshold,
        drop_rate_threshold=cfg.drop_rate_threshold,
        min_abs_add_delta=cfg.min_abs_add_delta,
        min_abs_drop_delta=cfg.min_abs_drop_delta,
        max_alerts_per_player=cfg.max_alerts_per_player,
    )
    notifier = DiscordNotifier(cfg.discord_webhook_url, cfg.dry_run)
    await send_alerts(notifier, alerts)
    if not alerts:
        if is_baseline:
            logging.info("Baseline established. Run again (or use continuous mode) to detect changes.")
        else:
            logging.info("No alerts this run.")


async def run_loop(cfg: Config, date_override: Optional[str]) -> None:
    state = InMemoryState(cfg.smoothing_n)
    notifier = DiscordNotifier(cfg.discord_webhook_url, cfg.dry_run)

    stop_event = asyncio.Event()

    def _handle_stop():
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_stop)
        except NotImplementedError:
            # Windows on Python < 3.8 may not support signal handlers in asyncio
            pass

    while not stop_event.is_set():
        rows = await fetch_and_parse_buzz_index(
            date_yyyy_mm_dd=date_override,
            user_agent=cfg.user_agent,
            timeout_seconds=cfg.request_timeout_seconds,
        )
        logging.info(f"Fetched {len(rows)} rows from Yahoo (date={date_override or 'latest'})")
        alerts = evaluate_rows(
            state=state,
            rows=rows,
            add_rate_threshold=cfg.add_rate_threshold,
            drop_rate_threshold=cfg.drop_rate_threshold,
            min_abs_add_delta=cfg.min_abs_add_delta,
            min_abs_drop_delta=cfg.min_abs_drop_delta,
            max_alerts_per_player=cfg.max_alerts_per_player,
        )
        await send_alerts(notifier, alerts)
        if not alerts and len(state.player_name_to_history) <= 1:
            logging.info("Baseline established on first loop iteration. Subsequent iterations will detect changes.")
        elif not alerts:
            logging.info("No alerts this iteration.")
        # Sleep for interval; KeyboardInterrupt will stop the loop. On POSIX signals, stop_event will be set.
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=cfg.check_interval_min * 60)
        except asyncio.TimeoutError:
            pass


async def run_iterations(
    cfg: Config,
    date_override: Optional[str],
    iterations: int,
    interval_seconds: Optional[int],
) -> None:
    state = InMemoryState(cfg.smoothing_n)
    notifier = DiscordNotifier(cfg.discord_webhook_url, cfg.dry_run)
    sleep_seconds = interval_seconds if interval_seconds is not None else cfg.check_interval_min * 60

    for i in range(iterations):
        rows = await fetch_and_parse_buzz_index(
            date_yyyy_mm_dd=date_override,
            user_agent=cfg.user_agent,
            timeout_seconds=cfg.request_timeout_seconds,
        )
        logging.info(f"[iter {i+1}/{iterations}] Fetched {len(rows)} rows from Yahoo (date={date_override or 'latest'})")
        alerts = evaluate_rows(
            state=state,
            rows=rows,
            add_rate_threshold=cfg.add_rate_threshold,
            drop_rate_threshold=cfg.drop_rate_threshold,
            min_abs_add_delta=cfg.min_abs_add_delta,
            min_abs_drop_delta=cfg.min_abs_drop_delta,
            max_alerts_per_player=cfg.max_alerts_per_player,
        )
        await send_alerts(notifier, alerts)
        if not alerts and i == 0:
            logging.info("Baseline established. Subsequent iterations will detect changes.")
        elif not alerts:
            logging.info("No alerts this iteration.")
        if i < iterations - 1:
            await asyncio.sleep(max(0, sleep_seconds))


async def main_async(date_override: Optional[str], once: bool, iterations: int, interval_seconds: Optional[int]) -> None:
    cfg = Config.from_env()
    if iterations and iterations > 1:
        await run_iterations(cfg, date_override, iterations=iterations, interval_seconds=interval_seconds)
        return
    if once:
        state = InMemoryState(cfg.smoothing_n)
        await run_once(cfg, state, date_override)
        return
    await run_loop(cfg, date_override)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Yahoo Buzz Index Discord Bot")
    parser.add_argument("--date", dest="date", default=None, help="YYYY-MM-DD date override")
    parser.add_argument("--once", dest="once", action="store_true", help="Run a single iteration and exit")
    parser.add_argument("--iterations", dest="iterations", type=int, default=1, help="Run N iterations in one process (state persists)")
    parser.add_argument("--interval-seconds", dest="interval_seconds", type=int, default=None, help="Seconds to wait between iterations (default: CHECK_INTERVAL_MIN * 60)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    asyncio.run(main_async(date_override=args.date, once=args.once, iterations=args.iterations, interval_seconds=args.interval_seconds))


if __name__ == "__main__":
    main()


