import os
import httpx
from cachetools import TTLCache

STEAM_API_KEY = os.getenv("STEAM_API_KEY", "")

cache = TTLCache(maxsize=500, ttl=3600)


async def get_app_details(app_id: int) -> dict:
    cache_key = f"app_details_{app_id}"
    if cache_key in cache:
        return cache[cache_key]

    url = "https://store.steampowered.com/api/appdetails"
    params = {"appids": app_id, "l": "english"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params)
        data = resp.json()
        result = data.get(str(app_id), {})
        cache[cache_key] = result
        return result


async def get_game_name(app_id: int) -> str:
    details = await get_app_details(app_id)
    if details.get("success") and details.get("data"):
        return details["data"].get("name", f"App {app_id}")
    return f"App {app_id}"


async def get_genres(app_id: int) -> list[str]:
    details = await get_app_details(app_id)
    if details.get("success") and details.get("data"):
        genres_data = details["data"].get("genres", [])
        return [g["description"] for g in genres_data]
    return ["Indie"]


async def get_reviews(app_id: int) -> dict:
    cache_key = f"reviews_{app_id}"
    if cache_key in cache:
        return cache[cache_key]

    url = f"https://store.steampowered.com/appreviews/{app_id}"
    params = {"json": 1, "language": "all", "purchase_type": "all", "num_per_page": 100}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params)
        data = resp.json()

    query_summary = data.get("query_summary", {})
    result = {
        "total": query_summary.get("total_reviews", 0),
        "positive": query_summary.get("total_positive", 0),
        "negative": query_summary.get("total_negative", 0),
        "score": query_summary.get("review_score", 0),
        "reviews": data.get("reviews", []),
    }

    recent_params = {"json": 1, "language": "all", "purchase_type": "all",
                     "num_per_page": 100, "filter": "recent"}
    async with httpx.AsyncClient(timeout=30) as client:
        recent_resp = await client.get(url, params=recent_params)
        recent_data = recent_resp.json()
    recent_summary = recent_data.get("query_summary", {})
    result["recent_total"] = recent_summary.get("total_reviews", 0)
    result["recent_positive"] = recent_summary.get("total_positive", 0)
    result["recent_negative"] = recent_summary.get("total_negative", 0)
    result["recent_score"] = recent_summary.get("review_score", 0)
    result["recent_reviews"] = recent_data.get("reviews", [])

    cache[cache_key] = result
    return result


async def get_player_count(app_id: int) -> dict:
    cache_key = f"players_{app_id}"
    if cache_key in cache:
        return cache[cache_key]

    url = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
    params = {"appid": app_id}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params)
        data = resp.json()
    result = data.get("response", {"player_count": 0})
    cache[cache_key] = result
    return result


async def get_achievement_percentages(app_id: int) -> dict:
    cache_key = f"achievements_{app_id}"
    if cache_key in cache:
        return cache[cache_key]

    url = "https://api.steampowered.com/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/"
    params = {"gameid": app_id}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params)
        data = resp.json()
    achievements = data.get("achievementpercentages", {}).get("achievements", [])
    result = {
        "achievements": achievements,
        "total": len(achievements),
    }
    cache[cache_key] = result
    return result


async def get_playtime_breakdown_from_reviews(reviews_data: list[dict]) -> dict:
    playtimes = [r.get("author", {}).get("playtime_forever", 0) for r in reviews_data if r.get("author", {}).get("playtime_forever")]
    total = len(playtimes) or 1
    under_1h = sum(1 for p in playtimes if p < 60)
    one_to_10h = sum(1 for p in playtimes if 60 <= p < 600)
    over_10h = sum(1 for p in playtimes if p >= 600)
    median = sorted(playtimes)[len(playtimes) // 2] if playtimes else 0

    return {
        "under_1h": round(under_1h / total * 100, 1),
        "one_to_10h": round(one_to_10h / total * 100, 1),
        "over_10h": round(over_10h / total * 100, 1),
        "median_minutes": median,
    }


async def get_estimated_owners(app_id: int) -> str:
    cache_key = f"owners_{app_id}"
    if cache_key in cache:
        return cache[cache_key]

    try:
        url = f"https://steamspy.com/api.php"
        params = {"request": "appdetails", "appid": app_id}
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
        owners = data.get("owners", "0..0")
        result = owners
        cache[cache_key] = result
        return result
    except Exception:
        return "Unknown"


async def get_ccu_history(app_id: int) -> dict:
    cache_key = f"ccu_{app_id}"
    if cache_key in cache:
        return cache[cache_key]

    current = await get_player_count(app_id)
    player_count = current.get("player_count", 0)

    try:
        url = "https://steamcharts.com/app/" + str(app_id) + "/chart-data.json"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            data = resp.json()
        peak = max(d.get("y", 0) for d in data) if data else player_count
    except Exception:
        peak = player_count

    result = {"peak": peak, "current": player_count}
    cache[cache_key] = result
    return result
