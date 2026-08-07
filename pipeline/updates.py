"""
Update-cadence correlation analysis — overlays patch history on review sentiment
and CCU to detect inflection points. The second moat feature per spec.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
import pipeline.db as db


async def analyze_update_cadence(app_id: int,
                                   db_path: Optional[str] = None) -> dict:
    database = await db.get_db(db_path)

    # Get game name
    cursor = await database.execute("SELECT name, release_date FROM games WHERE app_id = ?", (app_id,))
    game = await cursor.fetchone()
    if not game:
        await database.close()
        return {"error": f"App {app_id} not found"}

    name = game["name"]
    release_date_str = game["release_date"]

    # Get all patches (news items flagged as patches)
    cursor = await database.execute(
        "SELECT gid, title, date_posted, contents FROM news_items "
        "WHERE app_id = ? AND is_patch = 1 ORDER BY date_posted ASC",
        (app_id,))
    patches = [dict(r) for r in await cursor.fetchall()]

    # Get all review snapshots for trend analysis
    cursor = await database.execute(
        "SELECT snapshot_date, total_reviews, positive FROM review_snapshots "
        "WHERE app_id = ? ORDER BY snapshot_date ASC",
        (app_id,))
    reviews = [dict(r) for r in await cursor.fetchall()]

    await database.close()

    # Analyze: for each patch, check what happened to reviews in the 14 days after
    patch_impacts = []
    for patch in patches:
        patch_date = None
        try:
            patch_date = datetime.fromisoformat(patch["date_posted"])
        except (ValueError, TypeError):
            try:
                patch_date = datetime.strptime(patch["date_posted"], "%Y-%m-%d")
            except (ValueError, TypeError):
                continue

        # Find reviews before and after the patch (within reasonable windows)
        before_scores = []
        after_scores = []
        for r in reviews:
            try:
                review_date = datetime.fromisoformat(r["snapshot_date"])
            except (ValueError, TypeError):
                continue
            delta = (review_date - patch_date).days
            pct = (r["positive"] / r["total_reviews"] * 100) if r["total_reviews"] > 0 else 0
            if -14 <= delta < 0:
                before_scores.append(pct)
            elif 0 <= delta <= 14:
                after_scores.append(pct)

        before_avg = sum(before_scores) / len(before_scores) if before_scores else None
        after_avg = sum(after_scores) / len(after_scores) if after_scores else None

        impact = None
        if before_avg and after_avg:
            diff = after_avg - before_avg
            if diff >= 2:
                impact = "positive"
            elif diff <= -2:
                impact = "negative"
            else:
                impact = "neutral"

        patch_impacts.append({
            "title": patch["title"],
            "date": patch_date.strftime("%Y-%m-%d"),
            "before_avg_score": round(before_avg, 1) if before_avg else None,
            "after_avg_score": round(after_avg, 1) if after_avg else None,
            "impact": impact,
        })

    # Find inflection points — significant sentiment shifts from review snapshots
    inflections = []
    for i in range(1, len(reviews)):
        prev = reviews[i - 1]
        curr = reviews[i]
        prev_pct = (prev["positive"] / prev["total_reviews"] * 100) if prev["total_reviews"] > 0 else 0
        curr_pct = (curr["positive"] / curr["total_reviews"] * 100) if curr["total_reviews"] > 0 else 0
        diff = curr_pct - prev_pct
        if abs(diff) >= 3:
            inflections.append({
                "date": curr["snapshot_date"],
                "score": round(curr_pct, 1),
                "change": round(diff, 1),
                "direction": "up" if diff > 0 else "down",
            })

    return {
        "app_id": app_id,
        "game_name": name,
        "release_date": release_date_str,
        "patch_count": len(patches),
        "review_snapshots": len(reviews),
        "patches": patch_impacts,
        "inflections": inflections,
        "has_signal": len(inflections) > 0 or len(patch_impacts) > 0,
    }


def format_cadence_report(data: dict) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append(f"  UPDATE-CADENCE ANALYSIS — {data.get('game_name', '')}")
    lines.append("=" * 70)
    lines.append(f"  Release date: {data.get('release_date', 'Unknown')}")
    lines.append(f"  Patches detected: {data.get('patch_count', 0)}")
    lines.append(f"  Review snapshots: {data.get('review_snapshots', 0)}")
    lines.append("")

    patches = data.get("patches", [])
    inflections = data.get("inflections", [])

    if patches:
        lines.append("  ── Patch timeline ──")
        for p in patches:
            impact_icon = {"positive": "▲", "negative": "▼", "neutral": "─"}.get(p["impact"], "?")
            lines.append(
                f"  {p['date']}  {impact_icon}  {p['title'][:55]}")
            if p["before_avg_score"] and p["after_avg_score"]:
                lines.append(
                    f"           Score: {p['before_avg_score']}% → {p['after_avg_score']}% "
                    f"({p['impact']})")
        lines.append("")

        pos = sum(1 for p in patches if p["impact"] == "positive")
        neg = sum(1 for p in patches if p["impact"] == "negative")
        neu = sum(1 for p in patches if p["impact"] == "neutral")
        unknown = len(patches) - pos - neg - neu
        lines.append(f"  Impact summary: {pos} positive, {neg} negative, "
                     f"{neu} neutral, {unknown} unknown (insufficient data)")
        lines.append("")

    if inflections:
        lines.append("  ── Sentiment inflection points ──")
        for inf in inflections:
            direction = "▲ UP" if inf["direction"] == "up" else "▼ DOWN"
            lines.append(
                f"  {inf['date']}  {direction}  {inf['score']}% "
                f"(change: {inf['change']:+.1f}%)")
        lines.append("")

    if not patches and not inflections:
        lines.append("  No significant patch or sentiment signals detected.")
        lines.append("  This may indicate a quiet post-launch period or")
        lines.append("  insufficient snapshot history (collect more daily data).")

    lines.append("=" * 70)
    return "\n".join(lines)
