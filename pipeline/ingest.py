"""
Ingestion pipeline: orchestrates fetching all data sources for an app
and storing results in the database with rate-limit awareness.
"""

import asyncio
import httpx
from datetime import datetime
from typing import Optional
import pipeline.db as db
import pipeline.fetchers as f


BATCH_DELAY = 3.0


async def ingest_app(app_id: int, db_path: Optional[str] = None,
                      force: bool = False) -> dict:
    database = await db.get_db(db_path)
    try:
        last_fetch = await db.get_last_fetch(database, app_id, "full")
        if last_fetch and not force:
            last_dt = datetime.fromisoformat(last_fetch)
            if (datetime.utcnow() - last_dt).total_seconds() < 3600:
                print(f"  [skip] App {app_id} ingested recently ({last_fetch})")
                return {"app_id": app_id, "status": "cached"}

        async with httpx.AsyncClient(timeout=30) as client:
            data = await f.fetch_everything(client, app_id)

        if not data.get("name"):
            await database.close()
            return {"app_id": app_id, "status": "error", "error": "No data fetched"}

        await db.upsert_game(
            database, app_id, data["name"], data.get("genres", []),
            data.get("release_date_raw"))

        summary = data.get("review_summary", {})
        total = summary.get("total_reviews", 0)
        positive = summary.get("total_positive", 0)
        negative = summary.get("total_negative", 0)

        recent = data.get("recent_review_summary", {})
        r_total = recent.get("total_reviews", 0)
        r_positive = recent.get("total_positive", 0)
        r_negative = recent.get("total_negative", 0)

        await db.insert_review_snapshot(
            database, app_id, total, positive, negative,
            r_total, r_positive, r_negative)

        reviews = data.get("reviews", [])
        if reviews:
            await db.insert_playtime_samples(database, app_id, reviews)

        achievements = data.get("achievements", [])
        if achievements:
            await db.insert_achievement_snapshot(database, app_id, achievements)

        players = data.get("player_count", 0)
        await db.insert_ccu_snapshot(database, app_id, players)

        news = data.get("news", [])
        if news:
            await db.insert_news_items(database, app_id, news)

        await db.log_fetch(database, app_id, "full", "ok")
        await db.log_fetch(database, app_id, "reviews", "ok")
        await db.log_fetch(database, app_id, "achievements", "ok")
        await db.log_fetch(database, app_id, "ccu", "ok")
        await db.log_fetch(database, app_id, "news", "ok")

        print(f"  ✓ App {app_id} ({data['name']}): "
              f"{total} reviews, {players} CCU, {len(achievements)} achievements, "
              f"{len(news)} news items")
        return {"app_id": app_id, "status": "ok", "reviews": total,
                "ccu": players, "name": data["name"]}

    except Exception as e:
        print(f"  ✗ App {app_id} failed: {e}")
        try:
            await db.log_fetch(database, app_id, "full", "error", str(e))
        except Exception:
            pass
        return {"app_id": app_id, "status": "error", "error": str(e)}
    finally:
        await database.close()


async def ingest_batch(app_ids: list[int], db_path: Optional[str] = None,
                        delay: Optional[float] = None):
    delay = delay if delay is not None else BATCH_DELAY
    results = []
    for i, app_id in enumerate(app_ids):
        if i > 0:
            await asyncio.sleep(delay)
        r = await ingest_app(app_id, db_path=db_path)
        results.append(r)
    return results


async def daily_refresh(db_path: Optional[str] = None, stale_hours: int = 24):
    """Refresh data for all tracked games that haven't been updated in stale_hours."""
    database = await db.get_db(db_path)
    stale_seconds = stale_hours * 3600

    cursor = await database.execute("SELECT app_id, name FROM games")
    games = [(row["app_id"], row["name"]) for row in await cursor.fetchall()]
    await database.close()

    to_refresh = []
    for app_id, name in games:
        db2 = await db.get_db(db_path)
        last = await db.get_last_fetch(db2, app_id, "full")
        await db2.close()
        if not last:
            to_refresh.append(app_id)
        else:
            last_dt = datetime.fromisoformat(last)
            if (datetime.utcnow() - last_dt).total_seconds() > stale_seconds:
                to_refresh.append(app_id)

    print(f"Daily refresh: {len(games)} tracked, {len(to_refresh)} need update")
    if to_refresh:
        results = await ingest_batch(to_refresh, db_path=db_path, delay=2.0)
        ok = sum(1 for r in results if r["status"] == "ok")
        print(f"Refresh complete: {ok}/{len(to_refresh)} succeeded")
    return to_refresh
