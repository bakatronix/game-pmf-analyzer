"""
CLI entry point for the PMF ingestion pipeline.

Usage:
    python -m pipeline.main ingest <app_id> [<app_id> ...]   # Ingest specific games
    python -m pipeline.main backfill                          # Ingest validation set (20 games)
    python -m pipeline.main seed                              # Ingest seed dataset (50+ games)
    python -m pipeline.main refresh                           # Daily refresh of tracked games
    python -m pipeline.main status                            # Show tracked games
    python -m pipeline.main report <app_id>                   # Generate PMF report
    python -m pipeline.main cohort <app_id>                   # Compute Next 100 cohort
"""

import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pipeline.ingest as ingest
import pipeline.report as report
import pipeline.cohort as cohort
import pipeline.discover as discover
import pipeline.updates as updates
import pipeline.db as db

VALIDATION_SET = {
    105600, 413150, 1145360, 1794680, 367520,   # hits
    2379780, 1868140, 504230, 588650, 646570,   # hits
    582660, 43810, 1930, 49540, 209230,          # misses
    23570, 48330, 4850, 7830, 37100,             # misses
}


async def cmd_ingest(argv):
    if len(argv) < 3:
        print("Usage: python -m pipeline.main ingest <app_id> [<app_id> ...]")
        return
    app_ids = [int(a) for a in argv[2:]]
    print(f"Ingesting {len(app_ids)} apps...")
    results = await ingest.ingest_batch(app_ids, delay=2.0)
    ok = sum(1 for r in results if r["status"] == "ok")
    cached = sum(1 for r in results if r["status"] == "cached")
    failed = sum(1 for r in results if r["status"] == "error")
    print(f"\nDone: {ok} ok, {cached} cached, {failed} failed")


async def cmd_backfill(argv):
    print(f"Backfilling validation set ({len(VALIDATION_SET)} apps)...")
    results = await ingest.ingest_batch(sorted(VALIDATION_SET), delay=2.0)
    ok = sum(1 for r in results if r["status"] in ("ok", "cached"))
    failed = sum(1 for r in results if r["status"] == "error")
    print(f"\nDone: {ok} succeeded, {failed} failed")


async def cmd_refresh(argv):
    print("Running daily refresh...")
    await ingest.daily_refresh(stale_hours=24)


async def cmd_status(argv):
    database = await db.get_db()
    cursor = await database.execute(
        "SELECT app_id, name, genres, last_updated FROM games ORDER BY name")
    games = [dict(row) for row in await cursor.fetchall()]

    cursor2 = await database.execute(
        "SELECT app_id, snapshot_date, total_reviews, positive FROM review_snapshots "
        "ORDER BY app_id, snapshot_date DESC")
    snapshot_rows = [dict(r) for r in await cursor2.fetchall()]

    latest_reviews = {}
    for r in snapshot_rows:
        if r["app_id"] not in latest_reviews:
            latest_reviews[r["app_id"]] = r

    print(f"\nTracked games: {len(games)}\n")
    for g in games:
        aid = g["app_id"]
        lr = latest_reviews.get(aid, {})
        total = lr.get("total_reviews", 0)
        pos = lr.get("positive", 0)
        pct = f"{pos/total*100:.1f}%" if total > 0 else "N/A"
        print(f"  {aid:>7}  {g['name'][:35]:<35}  {total:>9,} reviews  {pct:>6} positive")

    await database.close()


async def cmd_report(argv):
    if len(argv) < 3:
        print("Usage: python -m pipeline.main report <app_id>")
        return
    app_id = int(argv[2])

    # Generate cohort data
    print("Computing cohort...")
    cohort_data = await cohort.compute_cohort(app_id)
    if cohort_data.get("error"):
        print(f"  Note: cohort unavailable — {cohort_data['error']}")

    text = await report.generate_report(app_id, cohort_data)
    print(text)


async def cmd_cohort(argv):
    if len(argv) < 3:
        print("Usage: python -m pipeline.main cohort <app_id>")
        return
    app_id = int(argv[2])
    print(f"Computing Next 100 cohort for app {app_id}...")
    data = await cohort.compute_cohort(app_id)
    if data.get("error"):
        print(f"  Error: {data['error']}")
        return

    print(f"\n  Cohort: {data['cohort_size']} games (from {data.get('candidates_found', 0)} candidates)")
    print(f"  Window:  {data['window']}")
    print(f"\n  ── Cohort Medians ──")
    m = data["medians"]
    print(f"  Review volume:  {m['review_volume']:,}")
    print(f"  Review score:   {m['review_score']}%")
    print(f"  Median playtime: {m['median_playtime_hr']}h")
    print(f"  Sub-2h ratio:   {m['sub2h_ratio']}%")
    print(f"  Peak CCU:       {m['peak_ccu']:,}")
    print(f"  Deepest ach:    {m['deepest_achievement']}%")

    ranks = data.get("percentile_ranks", {})
    if ranks:
        print(f"\n  ── Percentile Ranks ──")
        for key, info in ranks.items():
            arrow = "▲" if info["percentile"] > 50 else "▼" if info["percentile"] < 50 else "─"
            print(f"  {key}:  {info['percentile']}th percentile {arrow}  "
                  f"(yours: {info['value']}, median: {info['cohort_median']})")


async def cmd_seed(argv):
    print("Ingesting seed games into database...")
    await discover.seed_database()


async def cmd_updates(argv):
    if len(argv) < 3:
        print("Usage: python -m pipeline.main updates <app_id>")
        return
    app_id = int(argv[2])
    data = await updates.analyze_update_cadence(app_id)
    if data.get("error"):
        print(f"Error: {data['error']}")
        return
    print(updates.format_cadence_report(data))


async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    if cmd == "ingest":
        await cmd_ingest(sys.argv)
    elif cmd == "backfill":
        await cmd_backfill(sys.argv)
    elif cmd == "seed":
        await cmd_seed(sys.argv)
    elif cmd == "refresh":
        await cmd_refresh(sys.argv)
    elif cmd == "status":
        await cmd_status(sys.argv)
    elif cmd == "report":
        await cmd_report(sys.argv)
    elif cmd == "cohort":
        await cmd_cohort(sys.argv)
    elif cmd == "updates":
        await cmd_updates(sys.argv)
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: ingest, backfill, seed, refresh, status, report, cohort, updates")


if __name__ == "__main__":
    asyncio.run(main())
