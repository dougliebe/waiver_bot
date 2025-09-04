from __future__ import annotations

import asyncio
from typing import Optional

import httpx


class DiscordNotifier:
    def __init__(self, webhook_url: Optional[str], dry_run: bool) -> None:
        self.webhook_url = webhook_url
        self.dry_run = dry_run or not webhook_url

    async def send(self, content: str, *, title: Optional[str] = None) -> None:
        if self.dry_run or not self.webhook_url:
            print(f"[DRY_RUN] {title or ''}\n{content}")
            return

        payload = {
            "embeds": [
                {
                    "title": title or "Waiver Bot Alert",
                    "description": content,
                    "color": 0x2ecc71,
                }
            ]
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(self.webhook_url, json=payload)
            resp.raise_for_status()


