"""
Database layer for the PMF ingestion pipeline.
Uses aiosqlite for async SQLite; swap to asyncpg/PostgreSQL for production.
"""

import aiosqlite
from pathlib import Path
from datetime import date, datetime
from typing import Optional

DEFAULT_PATH = Path(__file__).parent.parent / "data" / "pmf.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    app_id          INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    genres          TEXT DEFAULT '[]',
    release_date    TEXT,
    first_seen      TEXT NOT NULL,
    last_updated    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id          INTEGER NOT NULL,
    snapshot_date   TEXT NOT NULL,
    total_reviews   INTEGER NOT NULL DEFAULT 0,
    positive        INTEGER NOT NULL DEFAULT 0,
    negative        INTEGER NOT NULL DEFAULT 0,
    recent_total    INTEGER DEFAULT 0,
    recent_positive INTEGER DEFAULT 0,
    recent_negative INTEGER DEFAULT 0,
    fetched_at      TEXT NOT NULL,
    UNIQUE(app_id, snapshot_date)
);
CREATE INDEX IF NOT EXISTS idx_review_snapshots_app_date
    ON review_snapshots(app_id, snapshot_date);

CREATE TABLE IF NOT EXISTS playtime_samples (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id          INTEGER NOT NULL,
    recommendationid TEXT NOT NULL,
    playtime_forever INTEGER NOT NULL DEFAULT 0,
    review_score    INTEGER DEFAULT 0,
    review_text     TEXT,
    fetched_at      TEXT NOT NULL,
    UNIQUE(app_id, recommendationid)
);
CREATE INDEX IF NOT EXISTS idx_playtime_app ON playtime_samples(app_id);

CREATE TABLE IF NOT EXISTS achievement_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id          INTEGER NOT NULL,
    snapshot_date   TEXT NOT NULL,
    total           INTEGER NOT NULL DEFAULT 0,
    completions_json TEXT DEFAULT '[]',
    deepest_pct     REAL DEFAULT 0,
    avg_pct         REAL DEFAULT 0,
    fetched_at      TEXT NOT NULL,
    UNIQUE(app_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS ccu_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id          INTEGER NOT NULL,
    snapshot_date   TEXT NOT NULL,
    player_count    INTEGER NOT NULL DEFAULT 0,
    fetched_at      TEXT NOT NULL,
    UNIQUE(app_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS news_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id          INTEGER NOT NULL,
    gid             TEXT NOT NULL,
    title           TEXT,
    url             TEXT,
    date_posted     TEXT,
    contents        TEXT,
    is_patch        INTEGER DEFAULT 0,
    fetched_at      TEXT NOT NULL,
    UNIQUE(app_id, gid)
);
CREATE INDEX IF NOT EXISTS idx_news_app_date ON news_items(app_id, date_posted);

CREATE TABLE IF NOT EXISTS fetch_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id          INTEGER NOT NULL,
    data_type       TEXT NOT NULL,
    last_fetched    TEXT NOT NULL,
    status          TEXT DEFAULT 'ok',
    error_msg       TEXT,
    UNIQUE(app_id, data_type)
);
"""


async def get_db(db_path: Optional[str] = None):
    path = db_path or str(DEFAULT_PATH)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.executescript(SCHEMA)
    await db.commit()
    return db


async def upsert_game(db: aiosqlite.Connection, app_id: int, name: str,
                      genres: list[str], release_date: Optional[str] = None):
    now = datetime.utcnow().isoformat()
    await db.execute(
        """INSERT INTO games (app_id, name, genres, release_date, first_seen, last_updated)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(app_id) DO UPDATE SET
             name=excluded.name, genres=excluded.genres,
             release_date=excluded.release_date, last_updated=excluded.last_updated""",
        (app_id, name, str(genres), release_date, now, now))
    await db.commit()


async def insert_review_snapshot(db: aiosqlite.Connection, app_id: int,
                                 total: int, positive: int, negative: int,
                                 recent_total: int = 0, recent_positive: int = 0,
                                 recent_negative: int = 0):
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()
    await db.execute(
        """INSERT OR REPLACE INTO review_snapshots
           (app_id, snapshot_date, total_reviews, positive, negative,
            recent_total, recent_positive, recent_negative, fetched_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (app_id, today, total, positive, negative,
         recent_total, recent_positive, recent_negative, now))
    await db.commit()


async def insert_playtime_samples(db: aiosqlite.Connection, app_id: int,
                                  reviews: list[dict]):
    now = datetime.utcnow().isoformat()
    for r in reviews:
        rec_id = r.get("recommendationid", "")
        pt = r.get("author", {}).get("playtime_forever", 0)
        vf = r.get("voted_feed", {})
        vf_score = vf.get("score") if isinstance(vf, dict) else 0
        review_text = r.get("review", "")
        try:
            await db.execute(
                """INSERT OR REPLACE INTO playtime_samples
                   (app_id, recommendationid, playtime_forever, review_score, review_text, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (app_id, rec_id, pt, vf_score or 0, review_text, now))
        except Exception:
            pass
    await db.commit()


async def insert_achievement_snapshot(db: aiosqlite.Connection, app_id: int,
                                      achievements: list[dict]):
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()
    total = len(achievements)
    percents = [float(a.get("percent", 0)) for a in achievements]
    deepest = min(percents) if percents else 0
    avg = sum(percents) / len(percents) if percents else 0
    await db.execute(
        """INSERT OR REPLACE INTO achievement_snapshots
           (app_id, snapshot_date, total, completions_json, deepest_pct, avg_pct, fetched_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (app_id, today, total, str(percents), deepest, avg, now))
    await db.commit()


async def insert_ccu_snapshot(db: aiosqlite.Connection, app_id: int, player_count: int):
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()
    await db.execute(
        """INSERT OR REPLACE INTO ccu_snapshots
           (app_id, snapshot_date, player_count, fetched_at)
           VALUES (?, ?, ?, ?)""",
        (app_id, today, player_count, now))
    await db.commit()


async def insert_news_items(db: aiosqlite.Connection, app_id: int, news: list[dict]):
    now = datetime.utcnow().isoformat()
    patch_keywords = ["update", "patch", "hotfix", "version", "release", "build"]
    for n in news:
        gid = n.get("gid", "")
        title = n.get("title", "")
        contents = n.get("contents", "")
        combined = f"{title} {contents}".lower()
        is_patch = 1 if any(kw in combined for kw in patch_keywords) else 0
        try:
            await db.execute(
                """INSERT OR REPLACE INTO news_items
                   (app_id, gid, title, url, date_posted, contents, is_patch, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (app_id, gid, title, n.get("url", ""),
                 datetime.fromtimestamp(n.get("date", 0)).isoformat() if n.get("date") else now,
                 contents, is_patch, now))
        except Exception:
            pass
    await db.commit()


async def log_fetch(db: aiosqlite.Connection, app_id: int, data_type: str,
                    status: str = "ok", error_msg: Optional[str] = None):
    now = datetime.utcnow().isoformat()
    await db.execute(
        """INSERT OR REPLACE INTO fetch_log (app_id, data_type, last_fetched, status, error_msg)
           VALUES (?, ?, ?, ?, ?)""",
        (app_id, data_type, now, status, error_msg))
    await db.commit()


async def get_last_fetch(db: aiosqlite.Connection, app_id: int, data_type: str) -> Optional[str]:
    cursor = await db.execute(
        "SELECT last_fetched FROM fetch_log WHERE app_id = ? AND data_type = ?",
        (app_id, data_type))
    row = await cursor.fetchone()
    return row["last_fetched"] if row else None


async def get_apps_needing_refresh(db: aiosqlite.Connection, data_type: str,
                                    stale_seconds: int = 86400) -> list[int]:
    """Return app_ids whose data is older than stale_seconds."""
    threshold = datetime.utcnow()
    cursor = await db.execute("SELECT app_id FROM games")
    all_apps = [row["app_id"] for row in await cursor.fetchall()]
    result = []
    for app_id in all_apps:
        last = await get_last_fetch(db, app_id, data_type)
        if last is None:
            result.append(app_id)
        else:
            last_dt = datetime.fromisoformat(last)
            if (threshold - last_dt).total_seconds() > stale_seconds:
                result.append(app_id)
    return result
