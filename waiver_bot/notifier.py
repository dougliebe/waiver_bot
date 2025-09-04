from __future__ import annotations

import asyncio
from typing import List, Optional

import httpx


class DiscordNotifier:
    def __init__(self, webhook_url: Optional[str], dry_run: bool, *, max_retries: int = 3) -> None:
        self.webhook_url = webhook_url
        self.dry_run = dry_run or not webhook_url
        self.max_retries = max_retries

    async def send(self, content: str, *, title: Optional[str] = None) -> None:
        await self.send_embeds([{"title": title or "Waiver Bot Alert", "description": content, "color": 0x2ecc71}])

    async def send_embeds(self, embeds: List[dict]) -> None:
        if self.dry_run or not self.webhook_url:
            for e in embeds:
                title = e.get("title", "")
                desc = e.get("description", "")
                print(f"[DRY_RUN] {title}\n{desc}")
            return

        payload = {"embeds": embeds}
        attempt = 0
        backoff = 1.0
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                attempt += 1
                resp = await client.post(self.webhook_url, json=payload)
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else backoff
                    await asyncio.sleep(delay)
                    backoff = min(backoff * 2, 10.0)
                    if attempt <= self.max_retries:
                        continue
                try:
                    resp.raise_for_status()
                    return
                except httpx.HTTPStatusError:
                    if attempt > self.max_retries:
                        raise
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 10.0)


