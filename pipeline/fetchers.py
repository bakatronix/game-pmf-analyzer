"""
Data fetchers for Steam public endpoints.
Each fetcher is an async function with rate-limit awareness.
"""

import asyncio
import httpx
from datetime import datetime
from typing import Optional


class RateLimiter:
    def __init__(self, min_interval: float = 1.5):
        self.min_interval = min_interval
        self._last_call = 0.0
        self._lock = asyncio.Lock()

    async def wait(self):
        async with self._lock:
            now = asyncio.get_event_loop().time()
            since_last = now - self._last_call
            if since_last < self.min_interval:
                await asyncio.sleep(self.min_interval - since_last)
            self._last_call = asyncio.get_event_loop().time()


_limiter = RateLimiter(min_interval=1.5)


async def _fetch(client: httpx.AsyncClient, url: str, max_retries: int = 3) -> Optional[dict]:
    for attempt in range(max_retries):
        await _limiter.wait()
        try:
            resp = await client.get(url, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code in (429, 502, 503, 504):
                wait = 2 ** attempt * 2
                print(f"  ⚠ {resp.status_code} on {url[:80]}..., retrying in {wait}s")
                await asyncio.sleep(wait)
            else:
                print(f"  ⚠ HTTP {resp.status_code} on {url[:80]}...")
                return None
        except Exception as e:
            print(f"  ⚠ fetch error: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
    return None


async def fetch_app_details(client: httpx.AsyncClient, app_id: int) -> Optional[dict]:
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=english"
    data = await _fetch(client, url)
    if data and str(app_id) in data and data[str(app_id)].get("success"):
        return data[str(app_id)]["data"]
    return None


async def fetch_reviews(client: httpx.AsyncClient, app_id: int,
                         cursor: str = "*", pages: int = 5) -> tuple[dict, list[dict]]:
    all_reviews = []
    summary = {}
    for _ in range(pages):
        url = (f"https://store.steampowered.com/appreviews/{app_id}"
               f"?json=1&language=all&purchase_type=all&num_per_page=100&cursor={cursor}")
        data = await _fetch(client, url)
        if not data:
            break
        if not summary:
            summary = data.get("query_summary", {})
        reviews = data.get("reviews", [])
        if not reviews:
            break
        all_reviews.extend(reviews)
        cursor = data.get("cursor", "*")
        if cursor == "*":
            break
    return summary, all_reviews


async def fetch_recent_reviews(client: httpx.AsyncClient, app_id: int) -> tuple[dict, list[dict]]:
    """Fetch only the recent (30-day) reviews for velocity calculation."""
    summary = {}
    url = (f"https://store.steampowered.com/appreviews/{app_id}"
           f"?json=1&language=all&purchase_type=all&num_per_page=100&filter=recent")
    data = await _fetch(client, url)
    if data:
        summary = data.get("query_summary", {})
        return summary, data.get("reviews", [])
    return summary, []


async def fetch_achievements(client: httpx.AsyncClient, app_id: int) -> list[dict]:
    url = (f"https://api.steampowered.com/ISteamUserStats/"
           f"GetGlobalAchievementPercentagesForApp/v2/?gameid={app_id}")
    data = await _fetch(client, url)
    if data:
        return data.get("achievementpercentages", {}).get("achievements", [])
    return []


async def fetch_player_count(client: httpx.AsyncClient, app_id: int) -> int:
    url = (f"https://api.steampowered.com/ISteamUserStats/"
           f"GetNumberOfCurrentPlayers/v1/?appid={app_id}")
    data = await _fetch(client, url)
    if data and "response" in data:
        return data["response"].get("player_count", 0)
    return 0


async def fetch_news(client: httpx.AsyncClient, app_id: int,
                      count: int = 20) -> list[dict]:
    url = (f"https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"
           f"?appid={app_id}&count={count}&maxlength=300")
    data = await _fetch(client, url)
    if data and "appnews" in data:
        return data["appnews"].get("newsitems", [])
    return []


async def fetch_everything(client: httpx.AsyncClient, app_id: int) -> dict:
    """Fetch all free-tier data for a single app. Returns a structured dict."""
    result = {"app_id": app_id, "errors": []}

    details = await fetch_app_details(client, app_id)
    if details:
        result["name"] = details.get("name", f"App {app_id}")
        result["genres"] = [g["description"] for g in details.get("genres", [])]
        result["release_date_raw"] = details.get("release_date", {}).get("date")
    else:
        result["name"] = f"App {app_id}"
        result["genres"] = []
        result["release_date_raw"] = None
        result["errors"].append("app_details_failed")

    summary, reviews = await fetch_reviews(client, app_id, pages=3)
    result["review_summary"] = summary or {}
    result["reviews"] = reviews

    recent_summary, recent_reviews = await fetch_recent_reviews(client, app_id)
    result["recent_review_summary"] = recent_summary or {}
    result["recent_reviews"] = recent_reviews

    achievements = await fetch_achievements(client, app_id)
    result["achievements"] = achievements

    players = await fetch_player_count(client, app_id)
    result["player_count"] = players

    news = await fetch_news(client, app_id)
    result["news"] = news

    result["fetched_at"] = datetime.utcnow().isoformat()
    return result
