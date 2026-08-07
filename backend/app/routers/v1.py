"""
V1 API router — wraps the pipeline for web consumption.
All endpoints return JSON matching the frontend's expected format.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import pipeline.ingest as ingest
import pipeline.report as report
import pipeline.cohort as cohort
import pipeline.updates as updates
import pipeline.db as db

router = APIRouter(prefix="/api/v1", tags=["v1"])


class AnalyzeRequest(BaseModel):
    app_id: int


@router.post("/analyze")
async def analyze_game(req: AnalyzeRequest):
    app_id = req.app_id

    # Ensure data is ingested
    result = await ingest.ingest_app(app_id, force=False)
    if result["status"] == "error" and "No data" in str(result.get("error", "")):
        raise HTTPException(status_code=404, detail="Game not found on Steam")

    # Compute cohort
    cohort_data = await cohort.compute_cohort(app_id)

    # Generate report data as structured JSON
    database = await db.get_db()
    cursor = await database.execute(
        "SELECT name, genres, release_date, first_seen FROM games WHERE app_id = ?", (app_id,))
    game = await cursor.fetchone()
    if not game:
        await database.close()
        raise HTTPException(status_code=404, detail="Game not in database")
    name = game["name"]
    genres = eval(game["genres"] or "[]") if game["genres"] else ["Indie"]

    cursor = await database.execute(
        "SELECT * FROM review_snapshots WHERE app_id = ? ORDER BY snapshot_date DESC LIMIT 1", (app_id,))
    rev = dict(await cursor.fetchone() or {})

    cursor = await database.execute(
        "SELECT playtime_forever FROM playtime_samples WHERE app_id = ?", (app_id,))
    playtimes = [r["playtime_forever"] for r in await cursor.fetchall()]

    cursor = await database.execute(
        "SELECT * FROM achievement_snapshots WHERE app_id = ? ORDER BY snapshot_date DESC LIMIT 1", (app_id,))
    ach = dict(await cursor.fetchone() or {})
    ach_pcts = eval(ach.get("completions_json", "[]") or "[]") if ach.get("completions_json") else []

    cursor = await database.execute(
        "SELECT player_count FROM ccu_snapshots WHERE app_id = ? ORDER BY snapshot_date DESC LIMIT 1", (app_id,))
    ccu = await cursor.fetchone()
    peak_ccu = ccu["player_count"] if ccu else 0

    cursor = await database.execute(
        "SELECT COUNT(*) as cnt FROM news_items WHERE app_id = ? AND is_patch = 1", (app_id,))
    patch_row = await cursor.fetchone()
    patch_count = patch_row["cnt"] if patch_row else 0

    await database.close()

    total_rev = rev.get("total_reviews", 0)
    positive = rev.get("positive", 0)
    recent_total = rev.get("recent_total", 0)
    recent_positive = rev.get("recent_positive", 0)

    sat = report.score_satisfaction(positive, total_rev, recent_positive, recent_total)
    eng = report.score_engagement(playtimes, ach_pcts)
    reach = report.score_reach(total_rev, recent_total, peak_ccu)

    label = report.generate_label(sat, eng, reach)
    recs = report.generate_recommendations(sat, eng, reach, genres, patch_count)

    return {
        "app_id": app_id,
        "game_name": name,
        "genres": genres,
        "release_date": game["release_date"],
        "lenses": {
            "satisfaction": sat,
            "engagement": eng,
            "reach": reach,
        },
        "label": label,
        "cohort": cohort_data if not cohort_data.get("error") else None,
        "recommendations": recs,
        "patch_count": patch_count,
        "data_quality": {
            "review_sample_size": len(playtimes) if playtimes else 0,
            "achievements_available": len(ach_pcts) > 0,
            "ccu_available": peak_ccu > 0,
        },
    }
