"""
Step 1 — Validation Notebook: Prove the PMF scoring model separates hits from misses.
This fetches public Steam data for ~20 games and computes three-lens scores.
Output: scatter plots + a separation check to gate the build.
"""
import asyncio, json, math, os, sys, time
from collections import defaultdict
from pathlib import Path

import httpx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

CACHE_DIR = Path(__file__).parent / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

# ── Game list: 10 hits, 10 misses/flops ──
GAMES = {
    # HITS (Metacritic > 85 or overwhelmingly positive, high volume)
    "hits": {
        105600: ("Terraria", "Action-Adventure sandbox"),
        413150: ("Stardew Valley", "Farming life sim"),
        1145360: ("Hades", "Roguelike action"),
        1794680: ("Vampire Survivors", "Reverse bullet hell"),
        367520: ("Hollow Knight", "Metroidvania"),
        2379780: ("Balatro", "Roguelike deckbuilder"),
        1868140: ("Dave the Diver", "Adventure management"),
        504230: ("Celeste", "Precision platformer"),
        588650: ("Dead Cells", "Roguelike action"),
        646570: ("Slay the Spire", "Roguelike deckbuilder"),
    },
    # MISSES / FLOPS (mixed-to-negative reviews, or very low engagement)
    "misses": {
        582660: ("Skylight Freerange 2", "Open-world RPG failure"),
        43810:  ("Flatout 3", "Notorious franchise killer"),
        1930:   ("Two Worlds", "Ambitious but broken"),
        49540:  ("Aliens: Colonial Marines", "Infamous AAA flop"),
        209230: ("Ride to Hell: Retribution", "Legendary bad game"),
        23570:  ("Postal 3", "Franchise disappointment"),
        48330:  ("Duke Nukem Forever", "15-year development disaster"),
        4850:   ("Codename: Gordon", "Delisted half-life spinoff"),
        7830:   ("Garshasp: The Monster Slayer", "Low-budget indie miss"),
        37100:  ("FlatOut", "Mix-up with FlatOut 1 — actually decent reviews but low playtime"),
    },
}


def load_cache(key):
    path = CACHE_DIR / f"{key}.json"
    if path.exists() and (time.time() - path.stat().st_mtime) < 7200:
        return json.loads(path.read_text())
    return None

def save_cache(key, data):
    (CACHE_DIR / f"{key}.json").write_text(json.dumps(data, default=str))


async def fetch(client, url, cache_key):
    cached = load_cache(cache_key)
    if cached is not None:
        return cached
    print(f"  → fetching {cache_key}...")
    try:
        resp = await client.get(url, timeout=30)
        if resp.status_code != 200:
            print(f"  ⚠ {cache_key} returned {resp.status_code}")
            return None
        data = resp.json()
        save_cache(cache_key, data)
        await asyncio.sleep(1.5)  # rate limit
        return data
    except Exception as e:
        print(f"  ⚠ {cache_key} error: {e}")
        return None


async def fetch_app_details(client, app_id):
    data = await fetch(client, f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=english", f"app_{app_id}")
    if data and str(app_id) in data and data[str(app_id)].get("success"):
        return data[str(app_id)]["data"]
    return None


async def fetch_reviews(client, app_id, cursor="*", pages=5):
    """Paginate reviews, return all fetched + summary."""
    all_reviews = []
    summary = {}
    for _ in range(pages):
        url = (f"https://store.steampowered.com/appreviews/{app_id}?json=1"
               f"&language=all&purchase_type=all&num_per_page=100&cursor={cursor}")
        data = await fetch(client, url, f"reviews_{app_id}_{cursor[:8]}")
        if not data:
            break
        if not summary:
            summary = data.get("query_summary", {})
        reviews = data.get("reviews", [])
        if not reviews:
            break
        all_reviews.extend(reviews)
        cursor = data.get("cursor", "*")
        await asyncio.sleep(1.5)
    return summary, all_reviews


async def fetch_achievements(client, app_id):
    data = await fetch(client,
        f"https://api.steampowered.com/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/?gameid={app_id}",
        f"ach_{app_id}")
    if data:
        return data.get("achievementpercentages", {}).get("achievements", [])
    return []


async def fetch_players(client, app_id):
    data = await fetch(client,
        f"https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={app_id}",
        f"players_{app_id}")
    if data and "response" in data:
        return data["response"].get("player_count", 0)
    return 0


async def fetch_news(client, app_id):
    data = await fetch(client,
        f"https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid={app_id}&count=20&maxlength=300",
        f"news_{app_id}")
    if data and "appnews" in data:
        return data["appnews"].get("newsitems", [])
    return []


# ── Scoring per the new spec (v0.1) ──

def clamp(val, lo=0, hi=100):
    return max(lo, min(hi, val))


def score_satisfaction(positive, total, recent_positive, recent_total):
    """Satisfaction lens: review score + trend bonus."""
    if total < 50:
        return None  # undefined confidence
    positive_pct = positive / total * 100
    recent_pct = recent_positive / recent_total * 100 if recent_total > 0 else positive_pct
    trend_bonus = clamp(recent_pct - positive_pct, -10, 10)
    score = clamp(positive_pct + 0.5 * trend_bonus, 0, 100)

    if total > 500:
        ci = 5
    elif total > 100:
        ci = 10
    else:
        ci = 20
    return {"score": round(score, 1), "ci": ci, "positive_pct": round(positive_pct, 1),
            "recent_pct": round(recent_pct, 1), "trend_bonus": round(trend_bonus, 1)}


def score_engagement(playtimes, achievements, genre_median_hr=10.0):
    """Engagement lens: playtime depth + hook retention + achievement depth."""
    if not playtimes:
        return None

    minutes = [p for p in playtimes if p > 0]
    if not minutes:
        return None
    minutes_sorted = sorted(minutes)
    median_min = minutes_sorted[len(minutes_sorted) // 2]
    median_hr = median_min / 60.0

    playtime_score = clamp(math.log1p(median_hr) / math.log1p(genre_median_hr * 3) * 95, 0, 95)

    sub2h_ratio = sum(1 for m in minutes_sorted if m < 120) / len(minutes_sorted)
    hook_score = clamp((1 - sub2h_ratio) * 100, 0, 100)

    deepest = 0.0
    for a in achievements:
        pct = float(a.get("percent", 0))
        if pct < deepest or deepest == 0:
            deepest = pct
    depth_score = clamp((100 - deepest) * 0.5, 0, 100) if achievements else 50

    score = 0.50 * playtime_score + 0.30 * hook_score + 0.20 * depth_score

    return {"score": round(score, 1), "playtime_score": round(playtime_score, 1),
            "hook_score": round(hook_score, 1), "depth_score": round(depth_score, 1),
            "median_hr": round(median_hr, 1), "sub2h_ratio": round(sub2h_ratio * 100, 1),
            "deepest_ach_pct": round(deepest, 1) if achievements else None}


def score_reach(total_reviews, recent_reviews_7d, peak_ccu, days_since_launch,
                cohort_p90_velocity=0.5, cohort_p90_ccu=2000):
    """Reach lens: review volume + velocity + CCU."""
    review_volume_score = clamp(math.log10(max(total_reviews, 1)) * 25, 0, 100)

    effective_days = min(days_since_launch or 30, 30)
    velocity = recent_reviews_7d / effective_days if effective_days > 0 else 0
    velocity_score = clamp(math.log1p(velocity) / math.log1p(cohort_p90_velocity) * 100, 0, 100)

    ccu_score = clamp(math.log1p(peak_ccu) / math.log1p(cohort_p90_ccu) * 100, 0, 100)

    score = 0.40 * review_volume_score + 0.35 * velocity_score + 0.25 * ccu_score

    return {"score": round(score, 1), "review_volume_score": round(review_volume_score, 1),
            "velocity_score": round(velocity_score, 1), "ccu_score": round(ccu_score, 1),
            "total_reviews": total_reviews, "velocity": round(velocity, 4), "peak_ccu": peak_ccu}


def generate_label(sat, eng, reach):
    """Qualitative label from rule-based decision tree."""
    parts = []
    if sat is None and eng is None and reach is None:
        return "Insufficient data — fewer than 50 reviews"
    if sat is None:
        parts.append("Satisfaction: undefined (<50 reviews)")
    else:
        s = sat["score"]
        parts.append(f"Satisfaction: {s}/100 ({'Strong' if s >= 70 else 'Weak' if s < 50 else 'Moderate'})")
    if eng is None:
        parts.append("Engagement: undefined (no playtime data)")
    else:
        e = eng["score"]
        parts.append(f"Engagement: {e}/100 ({'Strong' if e >= 70 else 'Weak' if e < 50 else 'Moderate'})")
    if reach is None:
        parts.append("Reach: undefined")
    else:
        r = reach["score"]
        parts.append(f"Reach: {r}/100 ({'Strong' if r >= 70 else 'Weak' if r < 50 else 'Moderate'})")

    header = " | ".join(parts)

    # Decision tree
    if sat and sat["score"] >= 70 and eng and eng["score"] >= 70 and reach and reach["score"] >= 70:
        interpret = "Strong PMF signal across all dimensions"
    elif sat and sat["score"] >= 75 and eng and eng["score"] >= 70 and reach and reach["score"] < 50:
        interpret = "Niche hit not yet finding its audience"
    elif sat and sat["score"] >= 70 and eng and eng["score"] < 50:
        interpret = "Good first impression, weak retention hook"
    elif eng and eng["score"] >= 70 and sat and sat["score"] < 60:
        interpret = "Engaged but divisive — check sentiment breakdown for the fracture"
    elif all(v is not None and v["score"] < 50 for v in [sat, eng, reach] if v):
        interpret = "Weak signal — recommend re-scoping or major update before further marketing spend"
    else:
        interpret = "Mixed signals — review individual lens scores for specifics"
    return f"{header}\n  → {interpret}"


# ── Main validation ──

async def analyze_game(client, app_id, name, note, label):
    print(f"\n{'='*50}\n[{label.upper()}] {name} ({app_id}) — {note}\n{'='*50}")

    details = await fetch_app_details(client, app_id)
    genres = [g["description"] for g in (details.get("genres", []) if details else [])]
    release_date = details.get("release_date", {}).get("date", "Unknown") if details else "Unknown"
    print(f"  Genres: {genres}  |  Released: {release_date}")

    summary, all_reviews = await fetch_reviews(client, app_id, pages=3)
    if not summary:
        print("  ⚠ No review data — skipping")
        return None

    total = summary.get("total_reviews", 0)
    positive = summary.get("total_positive", 0)
    negative = summary.get("total_negative", 0)
    print(f"  Reviews: {total} total, {positive} positive ({positive/total*100:.1f}%)" if total > 0 else "  Reviews: 0")

    # For recent reviews, fetch the "recent" filter separately
    recent_summary, recent_reviews = await fetch_reviews(client, app_id, pages=1)  # first page is recent-ish
    # Actually use the standard summary: all reviews come from the unfiltered endpoint
    # For validation, treat "recent" as the reviews we fetched (last ~100)
    # For a real build we'd use filter=recent — but for validation this is a directional approximation
    recent_total = summary.get("total_reviews", 0)  # use total as proxy for now
    recent_positive = summary.get("total_positive", 0)

    # Extract playtimes from reviews
    playtimes = []
    for r in all_reviews:
        pt = r.get("author", {}).get("playtime_forever", 0)
        if pt > 0:
            playtimes.append(pt)
    print(f"  Playtime samples: {len(playtimes)} reviewers")

    achievements = await fetch_achievements(client, app_id)
    print(f"  Achievements: {len(achievements)}" if achievements else "  Achievements: none")

    ccu = await fetch_players(client, app_id)
    print(f"  Current players: {ccu}")

    news = await fetch_news(client, app_id)
    patch_count = sum(1 for n in news if any(kw in (n.get("title", "") + n.get("contents", "")).lower()
        for kw in ["update", "patch", "hotfix", "version", "release"]))
    print(f"  News items: {len(news)} (estimated patches: {patch_count})")

    # Score
    sat = score_satisfaction(positive, total, recent_positive, recent_total)
    eng = score_engagement(playtimes, achievements)
    reach = score_reach(total, 0, ccu, 30)

    label_text = generate_label(sat, eng, reach)

    print(f"\n  ── Scores ──")
    print(f"  Satisfaction: {sat}" if sat else "  Satisfaction: undefined (<50 reviews)")
    print(f"  Engagement:   {eng}" if eng else "  Engagement: undefined")
    print(f"  Reach:        {reach}" if reach else "  Reach: undefined")
    print(f"  ── Label ──")
    print(f"  {label_text}")

    return {
        "app_id": app_id, "name": name, "note": note, "label": label,
        "genres": genres, "release_date": release_date,
        "total_reviews": total, "positive": positive,
        "sat": sat, "eng": eng, "reach": reach,
        "label_text": label_text,
    }


async def main():
    results = []

    async with httpx.AsyncClient(timeout=30) as client:
        for label, game_list in GAMES.items():
            for app_id, (name, note) in game_list.items():
                result = await analyze_game(client, app_id, name, note, label)
                if result:
                    results.append(result)

    # ── Visualize ──
    print(f"\n\n{'='*60}")
    print("VISUALIZATION")
    print(f"{'='*60}\n")

    hit_sat = [r["sat"]["score"] for r in results if r["label"] == "hits" and r["sat"]]
    miss_sat = [r["sat"]["score"] for r in results if r["label"] == "misses" and r["sat"]]
    hit_eng = [r["eng"]["score"] for r in results if r["label"] == "hits" and r["eng"]]
    miss_eng = [r["eng"]["score"] for r in results if r["label"] == "misses" and r["eng"]]
    hit_reach = [r["reach"]["score"] for r in results if r["label"] == "hits" and r["reach"]]
    miss_reach = [r["reach"]["score"] for r in results if r["label"] == "misses" and r["reach"]]

    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    fig.suptitle("Scores", fontsize=16, fontweight="bold")

    categories = ["Satisfaction", "Engagement", "Reach"]
    colors = {"hits": "#00cec9", "misses": "#ff6b6b"}
    markers = {"hits": "o", "misses": "x"}

    # Scatter: Satisfaction vs Engagement
    ax = axes[0, 0]
    for r in results:
        if r["sat"] and r["eng"]:
            ax.scatter(r["sat"]["score"], r["eng"]["score"],
                       c=colors[r["label"]], marker=markers[r["label"]],
                       s=120, alpha=0.8, edgecolors="white", linewidth=0.5,
                       label=r["label"] if r["app_id"] == list(GAMES[r["label"]].keys())[0] else "")
    ax.set_xlabel("Satisfaction Score", fontsize=12)
    ax.set_ylabel("Engagement Score", fontsize=12)
    ax.set_title("Satisfaction vs Engagement", fontsize=13, fontweight="bold")
    ax.axhline(y=50, color="gray", linestyle="--", alpha=0.3)
    ax.axvline(x=50, color="gray", linestyle="--", alpha=0.3)
    ax.set_xlim(-5, 105)
    ax.set_ylim(-5, 105)
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.15)

    # Scatter: Satisfaction vs Reach
    ax = axes[0, 1]
    for r in results:
        if r["sat"] and r["reach"]:
            ax.scatter(r["sat"]["score"], r["reach"]["score"],
                       c=colors[r["label"]], marker=markers[r["label"]],
                       s=120, alpha=0.8, edgecolors="white", linewidth=0.5)
    ax.set_xlabel("Satisfaction Score", fontsize=12)
    ax.set_ylabel("Reach Score", fontsize=12)
    ax.set_title("Satisfaction vs Reach", fontsize=13, fontweight="bold")
    ax.axhline(y=50, color="gray", linestyle="--", alpha=0.3)
    ax.axvline(x=50, color="gray", linestyle="--", alpha=0.3)
    ax.set_xlim(-5, 105)
    ax.set_ylim(-5, 105)
    ax.grid(True, alpha=0.15)

    # Bar chart: scores per game
    ax = axes[1, 0]
    names = [r["name"] for r in results]
    x = np.arange(len(names))
    w = 0.25
    sat_scores = [r["sat"]["score"] if r["sat"] else 0 for r in results]
    eng_scores = [r["eng"]["score"] if r["eng"] else 0 for r in results]
    reach_scores = [r["reach"]["score"] if r["reach"] else 0 for r in results]
    bar_colors = [colors[r["label"]] for r in results]

    b1 = ax.bar(x - w, sat_scores, w, label="Satisfaction", color="#a29bfe", alpha=0.85)
    b2 = ax.bar(x, eng_scores, w, label="Engagement", color="#00cec9", alpha=0.85)
    b3 = ax.bar(x + w, reach_scores, w, label="Reach", color="#fdcb6e", alpha=0.85)

    for i, (bar, name) in enumerate(zip(ax.patches[::3], names)):
        pass  # skip individual labels
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Score (0-100)", fontsize=12)
    ax.set_title("Three-Lens Scores by Game", fontsize=13, fontweight="bold")
    ax.legend()
    ax.axhline(y=50, color="gray", linestyle="--", alpha=0.3)
    ax.set_ylim(0, 105)
    ax.grid(True, axis="y", alpha=0.15)

    # Aggregation box plot
    ax = axes[1, 1]
    data_sat = [hit_sat, miss_sat]
    data_eng = [hit_eng, miss_eng]
    data_reach = [hit_reach, miss_reach]

    positions = [0, 1, 3, 4, 6, 7]
    bp1 = ax.boxplot([hit_sat, miss_sat], positions=[0, 1], widths=0.6,
                      patch_artist=True, boxprops=dict(facecolor="#a29bfe", alpha=0.7))
    bp2 = ax.boxplot([hit_eng, miss_eng], positions=[3, 4], widths=0.6,
                      patch_artist=True, boxprops=dict(facecolor="#00cec9", alpha=0.7))
    bp3 = ax.boxplot([hit_reach, miss_reach], positions=[6, 7], widths=0.6,
                      patch_artist=True, boxprops=dict(facecolor="#fdcb6e", alpha=0.7))

    # Add individual points
    for i, (pts, pos) in enumerate(zip([hit_sat, miss_sat], [0, 1])):
        jitter = np.random.normal(0, 0.05, len(pts))
        ax.scatter(np.full_like(pts, pos) + jitter, pts, c=colors["hits" if i == 0 else "misses"],
                   s=60, alpha=0.6, zorder=5, edgecolors="white", linewidth=0.5)
    for i, (pts, pos) in enumerate(zip([hit_eng, miss_eng], [3, 4])):
        jitter = np.random.normal(0, 0.05, len(pts))
        ax.scatter(np.full_like(pts, pos) + jitter, pts, c=colors["hits" if i == 0 else "misses"],
                   s=60, alpha=0.6, zorder=5, edgecolors="white", linewidth=0.5)
    for i, (pts, pos) in enumerate(zip([hit_reach, miss_reach], [6, 7])):
        jitter = np.random.normal(0, 0.05, len(pts))
        ax.scatter(np.full_like(pts, pos) + jitter, pts, c=colors["hits" if i == 0 else "misses"],
                   s=60, alpha=0.6, zorder=5, edgecolors="white", linewidth=0.5)

    ax.set_xticks([0.5, 3.5, 6.5])
    ax.set_xticklabels(["Satisfaction", "Engagement", "Reach"], fontsize=12)
    ax.set_ylabel("Score (0-100)", fontsize=12)
    ax.set_title("Score Distribution: Hits vs Misses", fontsize=13, fontweight="bold")
    ax.axhline(y=50, color="gray", linestyle="--", alpha=0.3)
    ax.set_ylim(-5, 105)
    ax.grid(True, axis="y", alpha=0.15)

    # Legend
    from matplotlib.patches import Patch
    ax.legend([Patch(facecolor=colors["hits"], alpha=0.7),
               Patch(facecolor=colors["misses"], alpha=0.7)],
              ["Hits", "Misses"], loc="upper right")

    plt.tight_layout()
    out_path = Path(__file__).parent / "step1_validation.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Chart saved to {out_path}")

    # ── Separation check ──
    print(f"\n{'='*60}")
    print("SEPARATION CHECK")
    print(f"{'='*60}")
    checks = []
    for name, hit_vals, miss_vals in [
        ("Satisfaction", hit_sat, miss_sat),
        ("Engagement", hit_eng, miss_eng),
        ("Reach", hit_reach, miss_reach),
    ]:
        if hit_vals and miss_vals:
            hit_mean = np.mean(hit_vals)
            miss_mean = np.mean(miss_vals)
            diff = hit_mean - miss_mean
            print(f"  {name}: Hit mean={hit_mean:.1f}, Miss mean={miss_mean:.1f}, Diff={diff:+.1f}")
            checks.append(diff > 10)
        else:
            print(f"  {name}: insufficient data")
            checks.append(False)

    all_pass = all(checks)
    print(f"\n  → Separation check {'PASSED' if all_pass else 'FAILED'}")
    if all_pass:
        print("  All three lenses show >10pt mean difference between hits and misses.")
        print("  GATE: GREEN — proceed to Step 2 (ingestion pipeline).")
    else:
        print("  One or more lenses failed to separate. Review the scoring model.")
        print("  GATE: RED — do not proceed until resolved.")

    return results


if __name__ == "__main__":
    results = asyncio.run(main())
