from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup


BASE_URL = (
    "https://football.fantasysports.yahoo.com/f1/buzzindex"
)


def build_buzz_index_url(date_yyyy_mm_dd: Optional[str]) -> str:
    """
    Build the Buzz Index URL. If date is None, Yahoo will default to the latest.
    Example with date: ...?sort=BI_A&src=combined&bimtab=A&trendtab=O&pos=ALL&date=2025-09-03
    """
    params = (
        "sort=BI_A",
        "src=combined",
        "bimtab=A",
        "trendtab=O",
        "pos=ALL",
    )
    query = "&".join(params)
    if date_yyyy_mm_dd:
        query = f"{query}&date={date_yyyy_mm_dd}"
    return f"{BASE_URL}?{query}"


@dataclass
class PlayerRow:
    name: str
    team_pos: Optional[str]
    adds: int
    drops: int
    url: Optional[str]


async def fetch_buzz_index_html(url: str, user_agent: str, timeout_seconds: int) -> str:
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
    }
    async with httpx.AsyncClient(timeout=timeout_seconds, headers=headers, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


def _safe_int(text: str) -> int:
    digits = "".join(ch for ch in text if ch.isdigit())
    try:
        return int(digits)
    except ValueError:
        return 0


def _find_table_by_headers(soup: BeautifulSoup, required_headers: Tuple[str, ...]) -> Optional[Tuple[object, dict]]:
    """
    Find a table whose header row contains required headers. Returns (table, header_index_map).
    Header matching is case-insensitive and strips whitespace.
    """
    tables = soup.find_all("table")
    for table in tables:
        thead = table.find("thead")
        if not thead:
            # Some pages may use the first row in tbody as header
            pass
        header_cells = None
        if thead:
            header_row = thead.find("tr")
            if header_row:
                header_cells = header_row.find_all(["th", "td"]) or []
        if not header_cells:
            # try first row in tbody
            tbody = table.find("tbody")
            if not tbody:
                continue
            first_row = tbody.find("tr")
            if not first_row:
                continue
            header_cells = first_row.find_all(["th", "td"]) or []

        header_map = {}
        for idx, cell in enumerate(header_cells):
            label = (cell.get_text(" ", strip=True) or "").lower()
            header_map[label] = idx

        # Find indices for required headers by best-effort fuzzy match
        def find_index_for(label: str) -> Optional[int]:
            label_l = label.lower()
            for k, idx in header_map.items():
                if label_l in k:
                    return idx
            return None

        mapping = {}
        ok = True
        for req in required_headers:
            idx = find_index_for(req)
            if idx is None:
                ok = False
                break
            mapping[req] = idx
        if ok:
            return table, mapping
    return None


def parse_buzz_index(html: str) -> List[PlayerRow]:
    soup = BeautifulSoup(html, "lxml")

    table_and_map = _find_table_by_headers(
        soup, required_headers=("player", "add", "drop")
    )
    if not table_and_map:
        return []

    table, header_map = table_and_map
    tbody = table.find("tbody") or table
    rows = []
    for tr in tbody.find_all("tr"):
        cells = tr.find_all(["td", "th"]) or []
        if len(cells) < len(header_map):
            continue

        # Player cell
        player_idx = header_map.get("player")
        adds_idx = header_map.get("add")
        drops_idx = header_map.get("drop")
        if player_idx is None or adds_idx is None or drops_idx is None:
            continue

        player_cell = cells[player_idx]
        name_link = player_cell.find("a")
        player_name = (name_link.get_text(" ", strip=True) if name_link else player_cell.get_text(" ", strip=True))
        player_url = name_link.get("href") if name_link else None

        # Try to extract team/pos if present in the cell, often as a span or parentheses
        team_pos = None
        full_text = player_cell.get_text(" ", strip=True)
        # Heuristic: text after player name separated by ' - ' or within parentheses
        if " - " in full_text:
            parts = full_text.split(" - ", 1)
            if len(parts) == 2 and parts[1]:
                team_pos = parts[1]

        adds_text = cells[adds_idx].get_text(" ", strip=True)
        drops_text = cells[drops_idx].get_text(" ", strip=True)
        adds = _safe_int(adds_text)
        drops = _safe_int(drops_text)

        if player_name:
            rows.append(PlayerRow(name=player_name, team_pos=team_pos, adds=adds, drops=drops, url=player_url))

    return rows


async def fetch_and_parse_buzz_index(
    date_yyyy_mm_dd: Optional[str],
    user_agent: str,
    timeout_seconds: int,
) -> List[PlayerRow]:
    url = build_buzz_index_url(date_yyyy_mm_dd)
    html = await fetch_buzz_index_html(url=url, user_agent=user_agent, timeout_seconds=timeout_seconds)
    return parse_buzz_index(html)


# For ad-hoc local testing: `python -m waiver_bot.scraper --date 2025-09-03`
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Yahoo Buzz Index scraper")
    parser.add_argument("--date", dest="date", default=None, help="YYYY-MM-DD date override")
    parser.add_argument("--timeout", dest="timeout", type=int, default=30)
    args = parser.parse_args()

    async def _main() -> None:
        rows = await fetch_and_parse_buzz_index(args.date, user_agent="Mozilla/5.0", timeout_seconds=args.timeout)
        for r in rows[:25]:
            print(f"{r.name:30s} adds={r.adds:6d} drops={r.drops:6d} team_pos={r.team_pos}")
        print(f"Total rows: {len(rows)}")

    asyncio.run(_main())


