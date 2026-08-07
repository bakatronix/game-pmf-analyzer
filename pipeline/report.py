"""
Report generator — computes three-lens PMF scores from database snapshots
and outputs a structured report per the v0.1 spec.
"""

import math
from datetime import datetime, date
from typing import Optional
import pipeline.db as db


def clamp(val: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, val))


def score_satisfaction(positive: int, total: int, recent_positive: int = 0,
                        recent_total: int = 0) -> Optional[dict]:
    """Satisfaction lens per spec v0.1."""
    if total < 50:
        return None  # undefined
    positive_pct = positive / total * 100
    recent_pct = (recent_positive / recent_total * 100) if recent_total > 0 else positive_pct
    trend_bonus = clamp(recent_pct - positive_pct, -10, 10)
    score = clamp(positive_pct + 0.5 * trend_bonus, 0, 100)

    if total > 500:
        ci = 5
    elif total > 100:
        ci = 10
    else:
        ci = 20
    return {
        "score": round(score, 1), "ci": ci,
        "positive_pct": round(positive_pct, 1),
        "recent_pct": round(recent_pct, 1),
        "trend_bonus": round(trend_bonus, 1),
        "total_reviews": total,
    }


def score_engagement(playtimes: list[int], achievement_pcts: list[float],
                      genre_median_hr: float = 10.0) -> Optional[dict]:
    """Engagement lens per spec v0.1."""
    minutes = [p for p in playtimes if p > 0]
    if not minutes:
        return None
    sorted_m = sorted(minutes)
    median_min = sorted_m[len(sorted_m) // 2]
    median_hr = median_min / 60.0

    playtime_score = clamp(math.log1p(median_hr) / math.log1p(genre_median_hr * 3) * 95, 0, 95)

    sub2h_ratio = sum(1 for m in sorted_m if m < 120) / len(sorted_m)
    hook_score = clamp((1 - sub2h_ratio) * 100, 0, 100)

    deepest = min(achievement_pcts) if achievement_pcts else 100.0
    depth_score = clamp((100 - deepest) * 0.5, 0, 100) if achievement_pcts else 50

    score = 0.50 * playtime_score + 0.30 * hook_score + 0.20 * depth_score

    # Playtime histogram for refund-window analysis
    buckets = {
        "sub_1h": sum(1 for m in sorted_m if m < 60),
        "1h_to_2h": sum(1 for m in sorted_m if 60 <= m < 120),
        "2h_to_5h": sum(1 for m in sorted_m if 120 <= m < 300),
        "5h_to_20h": sum(1 for m in sorted_m if 300 <= m < 1200),
        "20h_plus": sum(1 for m in sorted_m if m >= 1200),
    }

    return {
        "score": round(score, 1),
        "playtime_score": round(playtime_score, 1),
        "hook_score": round(hook_score, 1),
        "depth_score": round(depth_score, 1),
        "median_hr": round(median_hr, 1),
        "sub2h_ratio": round(sub2h_ratio * 100, 1),
        "sub2h_ratio_raw": round(sub2h_ratio, 4),
        "deepest_ach_pct": round(deepest, 1) if achievement_pcts else None,
        "playtime_buckets": buckets,
        "sample_size": len(sorted_m),
    }


def score_reach(total_reviews: int, recent_reviews_7d: int, peak_ccu: int,
                 days_since_launch: int = 30,
                 cohort_p90_velocity: float = 0.5,
                 cohort_p90_ccu: float = 2000) -> dict:
    """Reach lens per spec v0.1."""
    review_volume_score = clamp(math.log10(max(total_reviews, 1)) * 25, 0, 100)

    effective_days = min(days_since_launch or 30, 30)
    velocity = recent_reviews_7d / effective_days if effective_days > 0 else 0
    velocity_score = clamp(
        math.log1p(velocity) / math.log1p(cohort_p90_velocity) * 100, 0, 100)

    ccu_score = clamp(
        math.log1p(peak_ccu) / math.log1p(cohort_p90_ccu) * 100, 0, 100)

    score = 0.40 * review_volume_score + 0.35 * velocity_score + 0.25 * ccu_score
    return {
        "score": round(score, 1),
        "review_volume_score": round(review_volume_score, 1),
        "velocity_score": round(velocity_score, 1),
        "ccu_score": round(ccu_score, 1),
        "total_reviews": total_reviews,
        "velocity": round(velocity, 4),
        "peak_ccu": peak_ccu,
    }


def generate_label(sat: Optional[dict], eng: Optional[dict],
                    reach: Optional[dict]) -> str:
    """Rule-based qualitative label per spec v0.1."""
    labels = []
    for name, lens in [("Satisfaction", sat), ("Engagement", eng), ("Reach", reach)]:
        if lens is None:
            labels.append(f"{name}: undefined (<50 reviews)")
        elif lens["score"] >= 70:
            labels.append(f"{name}: {lens['score']}/100 (Strong)")
        elif lens["score"] >= 50:
            labels.append(f"{name}: {lens['score']}/100 (Moderate)")
        else:
            labels.append(f"{name}: {lens['score']}/100 (Weak)")
    header = " | ".join(labels)

    s = sat["score"] if sat else 0
    e = eng["score"] if eng else 0
    r = reach["score"] if reach else 0

    if sat and eng and reach and s >= 70 and e >= 70 and r >= 70:
        interpret = "Strong PMF signal across all dimensions"
    elif sat and eng and s >= 75 and e >= 70 and reach and r < 50:
        interpret = "Niche hit not yet finding its audience"
    elif sat and s >= 70 and eng and e < 50:
        interpret = "Good first impression, weak retention hook"
    elif eng and e >= 70 and sat and s < 60:
        interpret = "Engaged but divisive — check sentiment breakdown for the fracture"
    elif all(v is None or v["score"] < 50 for v in [sat, eng, reach] if v):
        interpret = "Weak signal — recommend re-scoping or major update before further marketing spend"
    else:
        interpret = "Mixed signals — review individual lens scores for specifics"

    return f"{header}\n  → {interpret}"


def generate_recommendations(sat: Optional[dict], eng: Optional[dict],
                              reach: Optional[dict], genres: list[str],
                              patch_count: int) -> list[dict]:
    """Generate 3 concrete, rule-based recommendations."""
    recs = []
    genre_name = genres[0] if genres else "genre"

    # Refund-window hook signal
    if eng and eng.get("sub2h_ratio", 0) > 30:
        recs.append({
            "priority": "HIGH",
            "category": "Engagement",
            "title": "Hook problem — players bouncing before refund window",
            "detail": (f"{eng['sub2h_ratio']}% of sampled reviewers have under 2 hours of playtime, "
                       f"placing this game in the high-risk zone for refunds. The first 30 minutes "
                       f"are losing players. Prioritize opening-sequence tuning: tutorial pacing, "
                       f"first-reward timing, and immediate moment-to-moment feel."),
        })
    elif eng and eng.get("sub2h_ratio", 0) > 15:
        recs.append({
            "priority": "MEDIUM",
            "category": "Engagement",
            "title": "Elevated early drop-off — watch the refund signal",
            "detail": (f"{eng['sub2h_ratio']}% of reviewers show sub-2h playtime. "
                       f"While not critical, this is above desirable levels. "
                       f"Review the first-session experience for friction points."),
        })

    # Deep engagement signal
    if eng and eng.get("median_hr", 0) > 20:
        recs.append({
            "priority": "HIGH",
            "category": "Engagement",
            "title": "Strong deep engagement — lean into depth as marketing",
            "detail": (f"Median playtime of {eng['median_hr']}h is exceptional. "
                       f"Your core loop is working. Feature longevity and replayability "
                       f"prominently in store presence and creator outreach."),
        })

    # Satisfaction signals
    if sat and sat["score"] < 70:
        recs.append({
            "priority": "HIGH",
            "category": "Satisfaction",
            "title": "Review score below 70% — triage critical complaints",
            "detail": (f"At {sat['positive_pct']}% positive, review sentiment is dragging "
                       f"discovery. Read the most recent 50 negative reviews, extract the "
                       f"top 3 specific complaints, and ship fixes within the next update cycle."),
        })

    if sat and sat.get("trend_bonus", 0) < -3:
        recs.append({
            "priority": "HIGH",
            "category": "Satisfaction",
            "title": "Review trend declining — investigate recent changes",
            "detail": (f"Recent reviews are trending down (trend bonus: {sat['trend_bonus']}). "
                       f"Check if a recent update or external event triggered the shift. "
                       f"Respond publicly if appropriate."),
        })

    # Reach signals
    if reach and reach["score"] < 30:
        recs.append({
            "priority": "HIGH",
            "category": "Reach",
            "title": "Critically low reach — game is not finding its audience",
            "detail": (f"With only {reach['total_reviews']:,} reviews and {reach['peak_ccu']} "
                       f"peak concurrent players, discovery is the primary bottleneck. "
                       f"Prioritize Steam festival participation, content creator outreach, "
                       f"and store-page optimization."),
        })
    elif reach and reach["score"] < 50:
        recs.append({
            "priority": "MEDIUM",
            "category": "Reach",
            "title": "Below-average reach — need discovery push",
            "detail": (f"Review volume and concurrent players are below benchmark. "
                       f"Consider a demo, festival submission, or targeted creator campaign "
                       f"to expand your funnel."),
        })

    # Update cadence signal
    if patch_count == 0:
        recs.append({
            "priority": "LOW",
            "category": "Communication",
            "title": "No recent patches detected — consider a post-launch update",
            "detail": ("Post-launch patches signal active development and can rekindle "
                       "interest. Even a small quality-of-life update with patch notes "
                       "can trigger a review bump."),
        })

    # Cap at 3 main recommendations
    return sorted(recs, key=lambda r: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[r["priority"]])[:3]


async def generate_report(app_id: int, cohort_data: Optional[dict] = None,
                          db_path: Optional[str] = None) -> str:
    """Generate a full PMF report from the database."""
    database = await db.get_db(db_path)

    # Fetch game metadata
    cursor = await database.execute(
        "SELECT name, genres, release_date, first_seen FROM games WHERE app_id = ?",
        (app_id,))
    game = await cursor.fetchone()
    if not game:
        await database.close()
        return f"Error: App {app_id} not found in database. Run 'python -m pipeline.main ingest {app_id}' first."

    name = game["name"]
    genres = eval(game["genres"] or "[]") if game["genres"] else ["Indie"]
    release_date = game["release_date"]
    first_seen = game["first_seen"]

    # Fetch latest review snapshot
    cursor = await database.execute(
        "SELECT * FROM review_snapshots WHERE app_id = ? ORDER BY snapshot_date DESC LIMIT 1",
        (app_id,))
    rev = await cursor.fetchone()
    rev = dict(rev) if rev else {}

    # Fetch playtime samples
    cursor = await database.execute(
        "SELECT playtime_forever FROM playtime_samples WHERE app_id = ?",
        (app_id,))
    playtimes = [row["playtime_forever"] for row in await cursor.fetchall()]

    # Fetch achievement data
    cursor = await database.execute(
        "SELECT * FROM achievement_snapshots WHERE app_id = ? ORDER BY snapshot_date DESC LIMIT 1",
        (app_id,))
    ach = await cursor.fetchone()
    ach = dict(ach) if ach else {}
    ach_pcts = eval(ach.get("completions_json", "[]") or "[]") if ach.get("completions_json") else []

    # Fetch latest CCU
    cursor = await database.execute(
        "SELECT player_count FROM ccu_snapshots WHERE app_id = ? ORDER BY snapshot_date DESC LIMIT 1",
        (app_id,))
    ccu = await cursor.fetchone()
    peak_ccu = ccu["player_count"] if ccu else 0

    # Fetch recent review data for velocity
    rev_recent_total = rev.get("recent_total", 0)
    rev_recent_positive = rev.get("recent_positive", 0)

    # Fetch patch count
    cursor = await database.execute(
        "SELECT COUNT(*) as cnt FROM news_items WHERE app_id = ? AND is_patch = 1",
        (app_id,))
    patch_row = await cursor.fetchone()
    patch_count = patch_row["cnt"] if patch_row else 0

    # Calculate days since launch
    days_since_launch = 30
    if release_date:
        try:
            from dateutil import parser as dateparser
            launch = dateparser.parse(release_date)
            days_since_launch = max(1, (date.today() - launch.date()).days)
        except Exception:
            pass

    await database.close()

    # ── Compute scores ──
    total_rev = rev.get("total_reviews", 0)
    positive = rev.get("positive", 0)
    negative = rev.get("negative", 0)

    sat = score_satisfaction(positive, total_rev, rev_recent_positive, rev_recent_total)
    eng = score_engagement(playtimes, ach_pcts)
    reach = score_reach(total_rev, rev_recent_total, peak_ccu, days_since_launch)

    label = generate_label(sat, eng, reach)
    recs = generate_recommendations(sat, eng, reach, genres, patch_count)

    # ── Format report ──
    lines = []
    lines.append("=" * 70)
    lines.append(f"  PMF REPORT — {name}")
    lines.append("=" * 70)
    lines.append(f"  App ID:        {app_id}")
    lines.append(f"  Genres:        {', '.join(genres)}")
    lines.append(f"  Released:      {release_date or 'Unknown'}")
    lines.append(f"  Days since:    {days_since_launch} (approx)")
    lines.append(f"  Data as of:    {date.today().isoformat()}")
    lines.append("")

    # ── Three lens scorecards ──
    lines.append("-" * 70)
    lines.append("  SATISFACTION LENS  (are buyers glad they bought it?)")
    lines.append("-" * 70)
    if sat:
        ci_str = f"±{sat['ci']}"
        lines.append(f"  Score:         {sat['score']}/100 ({ci_str} confidence)")
        lines.append(f"  Positive:      {sat['positive_pct']}% ({positive:,} / {total_rev:,} reviews)")
        lines.append(f"  Recent 30d:    {sat['recent_pct']}% positive")
        lines.append(f"  Trend bonus:   {sat['trend_bonus']:+.1f}")
        lines.append(f"  Confidence:    {'High' if sat['ci'] == 5 else 'Medium' if sat['ci'] == 10 else 'Low'} "
                     f"(based on {total_rev:,} total reviews)")
    else:
        lines.append(f"  Score:         undefined — fewer than 50 reviews ({total_rev} total)")
    lines.append("")

    lines.append("-" * 70)
    lines.append("  ENGAGEMENT LENS  (are players actually playing?)")
    lines.append("-" * 70)
    if eng:
        lines.append(f"  Score:          {eng['score']}/100")
        lines.append(f"  Median playtime: {eng['median_hr']} hours ({eng['sample_size']} sampled reviewers)")
        lines.append(f"  Sub-2h ratio:   {eng['sub2h_ratio']}%  ⬅ refund-window signal")
        lines.append(f"  Deepest achievement: {eng['deepest_ach_pct']}% completion")
        lines.append(f"  ── Components ──")
        lines.append(f"    Playtime depth: {eng['playtime_score']}/100  (log-scaled vs benchmark)")
        lines.append(f"    Hook retention: {eng['hook_score']}/100  (inverse of sub-2h bounce rate)")
        lines.append(f"    Loop depth:     {eng['depth_score']}/100  (from rarest achievement)")
        lines.append(f"  ── Playtime distribution ──")
        buckets = eng.get("playtime_buckets", {})
        total_samp = eng["sample_size"]
        for label_name, count in [
            ("Under 1h", buckets.get("sub_1h", 0)),
            ("1h–2h", buckets.get("1h_to_2h", 0)),
            ("2h–5h", buckets.get("2h_to_5h", 0)),
            ("5h–20h", buckets.get("5h_to_20h", 0)),
            ("20h+", buckets.get("20h_plus", 0)),
        ]:
            pct = count / total_samp * 100 if total_samp > 0 else 0
            bar = "█" * int(pct / 2)
            lines.append(f"    {label_name:<10} {count:>5} ({pct:>5.1f}%)  {bar}")
        lines.append("")
        lines.append(f"  ⚠ Note: Playtime is sampled from reviewers, who skew toward engaged")
        lines.append(f"     players. The true sub-2h (refund-eligible) ratio is likely higher")
        lines.append(f"     than reported here. Treat this as a directional lower bound.")
    else:
        lines.append(f"  Score:          undefined — no playtime samples available")
    lines.append("")

    lines.append("-" * 70)
    lines.append("  REACH LENS  (is it finding an audience?)")
    lines.append("-" * 70)
    if reach:
        lines.append(f"  Score:          {reach['score']}/100")
        lines.append(f"  Total reviews:  {reach['total_reviews']:,}  → volume score: {reach['review_volume_score']}/100")
        lines.append(f"  Velocity:       {reach['velocity']:.2f} reviews/day (recent) → score: {reach['velocity_score']}/100")
        lines.append(f"  Peak CCU:       {reach['peak_ccu']:,}  → score: {reach['ccu_score']}/100")
    else:
        lines.append(f"  Score:          undefined")
    lines.append("")

    # ── Qualitative label ──
    lines.append("─" * 70)
    lines.append(f"  INTERPRETATION: {label}")
    lines.append("─" * 70)
    lines.append("")

    # ── Update-cadence summary ──
    if patch_count > 0:
        lines.append("-" * 70)
        lines.append("  UPDATE-CADENCE OVERLAY  (is the update strategy working?)")
        lines.append("-" * 70)
        lines.append(f"  Patches detected:  {patch_count}")
        lines.append(f"  Key insight:       {'Active post-launch support — momentum is being maintained.' if patch_count >= 5 else 'Some post-launch activity detected.' if patch_count >= 2 else 'Minimal post-launch updates.'}")
        lines.append(f"  Full timeline:     python -m pipeline.main updates {app_id}")
        lines.append("")

    # ── Cohort comparison ──
    if cohort_data and cohort_data.get("cohort_size", 0) > 0:
        lines.append("-" * 70)
        lines.append(f"  NEXT 100 COHORT  ({cohort_data['cohort_size']} games, ±{cohort_data['window_days']} day window)")
        lines.append("-" * 70)
        ranks = cohort_data.get("percentile_ranks", {})
        if ranks:
            lines.append(f"  {'Metric':<22} {'Yours':>10} {'Median':>10} {'Percentile':>12}")
            lines.append(f"  {'-'*22} {'-'*10} {'-'*10} {'-'*12}")
            for key, info in ranks.items():
                label_name = key.replace("_", " ").title()
                arrow = "▲" if info["percentile"] > 50 else "▼" if info["percentile"] < 50 else "─"
                lines.append(
                    f"  {label_name:<22} {str(info['value']):>10} "
                    f"{str(info['cohort_median']):>10} {info['percentile']:>8.0f}th {arrow}")
        else:
            lines.append("  Insufficient cohort data for percentile comparison.")
        lines.append("")

    # ── Recommendations ──
    lines.append("-" * 70)
    lines.append("  CONCRETE RECOMMENDATIONS  (next 30 days)")
    lines.append("-" * 70)
    for i, r in enumerate(recs, 1):
        lines.append(f"  [{r['priority']}] {i}. {r['title']} ({r['category']})")
        lines.append(f"      {r['detail']}")
        lines.append("")
    if not recs:
        lines.append("  No specific recommendations — all signals are within normal range.")

    lines.append("=" * 70)
    return "\n".join(lines)
