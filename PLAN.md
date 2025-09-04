# Goal

Create a **simple Discord bot** that checks Yahoo Fantasy Football Buzz Index add/drop trends and notifies when a player's adds or drops spike, without using a database—just in‑memory tracking.

---

## Simplified Approach

1. **Fetch** the Buzz Index page every **X minutes**.
2. **Parse** player rows (name, adds, drops).
3. **Compare** with last snapshot(s) stored in memory.
4. **Compute deltas** and per‑minute rates.
5. **Send notification** if rate exceeds **Y**.
6. **Run continuously** (e.g., asyncio loop).

---

## State Handling (In‑Memory)

* Keep a dict: `last_snapshot[player_name] = {adds, drops, ts}`.
* On each fetch:

  * Compute `add_delta`, `drop_delta`, and `rate` vs previous snapshot.
  * Update dict with the new values.
* Optionally, keep only the **last N snapshots** (e.g., 3–5) for smoothing.

**Pros:**

* No persistence layer.
* Very fast and minimal.

**Cons:**

* If the bot restarts, history resets.
* No long‑term trend logs.

---

## Config (Environment Variables)

```
DISCORD_WEBHOOK_URL=...
CHECK_INTERVAL_MIN=5
ADD_RATE_THRESHOLD=4.0
DROP_RATE_THRESHOLD=4.0
MIN_ABS_ADD_DELTA=15
MIN_ABS_DROP_DELTA=15
SMOOTHING_N=3                # number of recent snapshots to average
MAX_ALERTS_PER_PLAYER=3      # per day
MAX_ALERTS_PER_ITERATION=10  # cap per run/iteration to avoid floods
EMBED_ALERTS_PER_MESSAGE=10  # number of alerts batched per Discord message
MAX_DISCORD_RETRIES=3        # 429/backoff retries
```

---

## Local Setup

1. Create and activate a Python 3.10+ environment.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and set values. Leave `DISCORD_WEBHOOK_URL` empty to run in **DRY_RUN** mode and print alerts to console.
4. Run once for a single fetch/compare step:

```
python -m waiver_bot.main --once --date 2025-09-03
```

5. Run continuous loop (uses `CHECK_INTERVAL_MIN`):

```
python -m waiver_bot.main
```

Notes:

* `--date YYYY-MM-DD` pins Yahoo Buzz Index to a specific date. Omit to use Yahoo's latest.
* On Windows, signal handling may be limited; press Ctrl+C to stop.

---

## Pseudocode

```python
last_snapshot = {}

async def loop():
    while True:
        rows = fetch_and_parse()
        now = utcnow()

        for r in rows:
            prev = last_snapshot.get(r.name)
            if prev:
                dt = minutes_between(now, prev['ts'])
                add_delta = r.adds - prev['adds']
                drop_delta = r.drops - prev['drops']
                add_rate = add_delta / max(dt, 1e-6)
                drop_rate = drop_delta / max(dt, 1e-6)

                if add_rate > ADD_RATE_THRESHOLD and add_delta >= MIN_ABS_ADD_DELTA:
                    send_alert(r, add_rate, add_delta, 'add')

                if drop_rate > DROP_RATE_THRESHOLD and drop_delta >= MIN_ABS_DROP_DELTA:
                    send_alert(r, drop_rate, drop_delta, 'drop')

            last_snapshot[r.name] = {
                'adds': r.adds,
                'drops': r.drops,
                'ts': now
            }

        await asyncio.sleep(CHECK_INTERVAL_MIN * 60)
```

---

## Discord Message

* Simple webhook embed with:

  * Player name
  * Team/pos
  * Rate & delta
  * Link back to Buzz Index

---

## Deployment

* Just run with Python + `asyncio`.
* Use `requirements.txt`:

```
httpx
beautifulsoup4
lxml
python-dotenv
```

* Run in Codespace, VPS, or locally with a screen/tmux session.

---

## Implementation Notes

* The scraper is resilient to minor table/header changes using fuzzy header matching.
* In‑memory state keeps a bounded deque per player, enforcing `SMOOTHING_N`.
* Per‑day alert rate limits via in‑memory counters (`MAX_ALERTS_PER_PLAYER`).
* Discord notifier supports **DRY_RUN** (console output) when webhook is not set.
* Flood control:
  * Alerts are batched as embeds (up to `EMBED_ALERTS_PER_MESSAGE` per message).
  * Per‑iteration cap with `MAX_ALERTS_PER_ITERATION`.
  * 429 handling with exponential backoff up to `MAX_DISCORD_RETRIES`.

---

## Definition of Done

* Bot runs continuously.
* Keeps only recent snapshots in memory.
* Posts alerts to Discord when add/drop rates exceed thresholds.
* No persistence beyond process lifetime.
