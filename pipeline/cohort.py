"""
Cohort computation — auto-selects comparison cohort by release date ±90 days
and tag overlap, computes percentile ranks for key metrics.
"""

from datetime import datetime, date, timedelta
from typing import Optional
import pipeline.db as db


async def compute_cohort(app_id: int, db_path: Optional[str] = None,
                          window_days: int = 90, max_cohort_size: int = 100) -> dict:
    """Find and analyze the comparison cohort for a given app."""
    database = await db.get_db(db_path)

    # Get target game's metadata
    cursor = await database.execute(
        "SELECT name, genres, release_date FROM games WHERE app_id = ?", (app_id,))
    target = await cursor.fetchone()
    if not target:
        await database.close()
        return {"error": f"App {app_id} not in database"}

    target_genres = set(eval(target["genres"] or "[]"))
    target_release = target["release_date"]

    # Parse release date — try multiple formats
    target_dt = None
    if target_release:
        for fmt in ["%d %b, %Y", "%d %B, %Y", "%Y-%m-%d", "%b %d, %Y", "%B %d, %Y"]:
            try:
                target_dt = datetime.strptime(target_release, fmt)
                break
            except ValueError:
                continue

    if not target_dt:
        await database.close()
        return {"error": f"Could not parse release date: {target_release}",
                "cohort_size": 0, "candidates_found": 0}

    window_start = target_dt - timedelta(days=window_days)
    window_end = target_dt + timedelta(days=window_days)

    # Find all games with release dates in the database
    cursor = await database.execute(
        "SELECT app_id, name, genres, release_date FROM games WHERE app_id != ?", (app_id,))
    candidates = []
    for row in await cursor.fetchall():
        rd = row["release_date"]
        if not rd:
            continue
        row_dt = None
        for fmt in ["%d %b, %Y", "%d %B, %Y", "%Y-%m-%d", "%b %d, %Y", "%B %d, %Y"]:
            try:
                row_dt = datetime.strptime(rd, fmt)
                break
            except ValueError:
                continue
        if not row_dt:
            continue

        # Check within window
        if window_start <= row_dt <= window_end:
            row_genres = set(eval(row["genres"] or "[]"))
            tag_overlap = len(target_genres & row_genres) if target_genres else 0
            candidates.append({
                "app_id": row["app_id"],
                "name": row["name"],
                "genres": row["genres"],
                "release_date": rd,
                "tag_overlap": tag_overlap,
                "date_distance": abs((row_dt - target_dt).days),
            })

    # Sort by tag_overlap desc, then date_distance asc
    candidates.sort(key=lambda c: (-c["tag_overlap"], c["date_distance"]))
    cohort = candidates[:max_cohort_size]

    # Gather metrics for cohort members
    cohort_metrics = []
    for c in cohort:
        cid = c["app_id"]

        # Review data
        cursor = await database.execute(
            "SELECT total_reviews, positive FROM review_snapshots "
            "WHERE app_id = ? ORDER BY snapshot_date DESC LIMIT 1", (cid,))
        rev = await cursor.fetchone()
        rev_total = rev["total_reviews"] if rev else 0
        rev_pct = (rev["positive"] / rev["total_reviews"] * 100) if rev and rev["total_reviews"] > 0 else 0

        # Playtime data
        cursor = await database.execute(
            "SELECT playtime_forever FROM playtime_samples WHERE app_id = ?", (cid,))
        pts = [r["playtime_forever"] for r in await cursor.fetchall()]
        pts = [p for p in pts if p > 0]
        median_hr = 0
        sub2h_ratio = 0
        if pts:
            sorted_pts = sorted(pts)
            median_hr = sorted_pts[len(sorted_pts) // 2] / 60.0
            sub2h_ratio = sum(1 for p in sorted_pts if p < 120) / len(sorted_pts)

        # CCU
        cursor = await database.execute(
            "SELECT player_count FROM ccu_snapshots "
            "WHERE app_id = ? ORDER BY snapshot_date DESC LIMIT 1", (cid,))
        ccu_row = await cursor.fetchone()
        peak_ccu = ccu_row["player_count"] if ccu_row else 0

        # Achievement data
        cursor = await database.execute(
            "SELECT completions_json FROM achievement_snapshots "
            "WHERE app_id = ? ORDER BY snapshot_date DESC LIMIT 1", (cid,))
        ach_row = await cursor.fetchone()
        ach_pcts = []
        if ach_row and ach_row["completions_json"]:
            try:
                ach_pcts = eval(ach_row["completions_json"])
            except Exception:
                pass
        deepest_ach = min(ach_pcts) if ach_pcts else 100.0

        cohort_metrics.append({
            "app_id": cid,
            "name": c["name"],
            "tag_overlap": c["tag_overlap"],
            "date_distance": c["date_distance"],
            "total_reviews": rev_total,
            "review_pct": round(rev_pct, 1),
            "median_hr": round(median_hr, 1),
            "sub2h_ratio": round(sub2h_ratio * 100, 1),
            "peak_ccu": peak_ccu,
            "deepest_ach_pct": round(deepest_ach, 1),
        })

    # Compute cohort-level medians (from members with >0 reviews for that metric)
    def safe_median(values):
        if not values:
            return 0
        s = sorted(values)
        return s[len(s) // 2]

    rev_totals = [m["total_reviews"] for m in cohort_metrics if m["total_reviews"] > 0]
    rev_pcts = [m["review_pct"] for m in cohort_metrics if m["review_pct"] > 0]
    median_hrs = [m["median_hr"] for m in cohort_metrics if m["median_hr"] > 0]
    sub2h_ratios = [m["sub2h_ratio"] for m in cohort_metrics if m["total_reviews"] > 0]
    ccus = [m["peak_ccu"] for m in cohort_metrics if m["peak_ccu"] >= 0]
    deepest_achs = [m["deepest_ach_pct"] for m in cohort_metrics if m["deepest_ach_pct"] < 100]

    cohort_stats = {
        "cohort_size": len(cohort),
        "candidates_found": len(candidates),
        "window_days": window_days,
        "target_date": target_dt.strftime("%Y-%m-%d"),
        "window": f"{window_start.strftime('%Y-%m-%d')} to {window_end.strftime('%Y-%m-%d')}",
        "medians": {
            "review_volume": safe_median(rev_totals),
            "review_score": round(safe_median(rev_pcts), 1),
            "median_playtime_hr": round(safe_median(median_hrs), 1),
            "sub2h_ratio": round(safe_median(sub2h_ratios), 1),
            "peak_ccu": safe_median(ccus),
            "deepest_achievement": round(safe_median(deepest_achs), 1),
        },
        "p90": {
            "review_volume": sorted(rev_totals)[int(len(rev_totals) * 0.9)] if rev_totals else 0,
            "peak_ccu": sorted(ccus)[int(len(ccus) * 0.9)] if ccus else 0,
        },
        "members": cohort_metrics,
    }

    await database.close()

    # Compute percentile ranks for the target game
    # Get target metrics
    cursor2 = await db.get_db(db_path)
    cur = await cursor2.execute(
        "SELECT total_reviews, positive FROM review_snapshots "
        "WHERE app_id = ? ORDER BY snapshot_date DESC LIMIT 1", (app_id,))
    t_rev = await cur.fetchone()
    t_total = t_rev["total_reviews"] if t_rev else 0
    t_pct = (t_rev["positive"] / t_total * 100) if t_rev and t_total > 0 else 0

    cur = await cursor2.execute(
        "SELECT playtime_forever FROM playtime_samples WHERE app_id = ?", (app_id,))
    t_pts = [r["playtime_forever"] for r in await cur.fetchall()]
    t_pts = [p for p in t_pts if p > 0]
    t_median_hr = sorted(t_pts)[len(t_pts) // 2] / 60.0 if t_pts else 0
    t_sub2h = sum(1 for p in t_pts if p < 120) / len(t_pts) * 100 if t_pts else 0

    cur = await cursor2.execute(
        "SELECT player_count FROM ccu_snapshots "
        "WHERE app_id = ? ORDER BY snapshot_date DESC LIMIT 1", (app_id,))
    t_ccu = await cur.fetchone()
    t_peak = t_ccu["player_count"] if t_ccu else 0
    await cursor2.close()

    def percentile_rank(value, cohort_values):
        if not cohort_values:
            return 50
        below = sum(1 for v in cohort_values if v < value)
        return round(below / len(cohort_values) * 100, 1)

    ranks = {
        "review_volume": {
            "value": t_total,
            "cohort_median": cohort_stats["medians"]["review_volume"],
            "percentile": percentile_rank(t_total, rev_totals),
        },
        "review_score": {
            "value": round(t_pct, 1),
            "cohort_median": cohort_stats["medians"]["review_score"],
            "percentile": percentile_rank(round(t_pct, 1), rev_pcts),
        },
        "median_playtime": {
            "value": round(t_median_hr, 1),
            "cohort_median": cohort_stats["medians"]["median_playtime_hr"],
            "percentile": percentile_rank(round(t_median_hr, 1), median_hrs),
        },
        "sub2h_ratio": {
            "value": round(t_sub2h, 1),
            "cohort_median": cohort_stats["medians"]["sub2h_ratio"],
            "percentile": 100 - percentile_rank(round(t_sub2h, 1), sub2h_ratios),  # lower is better
        },
        "peak_ccu": {
            "value": t_peak,
            "cohort_median": cohort_stats["medians"]["peak_ccu"],
            "percentile": percentile_rank(t_peak, ccus),
        },
    }

    cohort_stats["percentile_ranks"] = ranks

    return cohort_stats
