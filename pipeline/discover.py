"""
Seed dataset of indie games with known release dates.
Expands the database to make cohort computation meaningful.
Each entry: (app_id, name, release_date_str)
"""
import asyncio
import pipeline.ingest as ingest
from typing import Optional


SEED_GAMES = [
    # 2024 releases
    (2379780, "Balatro", "20 Feb, 2024"),
    (1868140, "DAVE THE DIVER", "28 Jun, 2023"),
    (1794680, "Vampire Survivors", "20 Oct, 2022"),
    (1145360, "Hades", "17 Sep, 2020"),
    # Major indie hits
    (105600,  "Terraria", "16 May, 2011"),
    (413150,  "Stardew Valley", "26 Feb, 2016"),
    (367520,  "Hollow Knight", "24 Feb, 2017"),
    (504230,  "Celeste", "25 Jan, 2018"),
    (588650,  "Dead Cells", "6 Aug, 2018"),
    (646570,  "Slay the Spire", "23 Jan, 2019"),
    # More indies (various release dates for cohort diversity)
    (250900,  "The Binding of Isaac: Rebirth", "4 Nov, 2014"),
    (219740,  "Don't Starve", "23 Apr, 2013"),
    (220,     "Half-Life 2", "16 Nov, 2004"),
    (550,    "Left 4 Dead 2", "17 Nov, 2009"),
    (620,    "Portal 2", "18 Apr, 2011"),
    (440,    "Team Fortress 2", "10 Oct, 2007"),
    (570,    "Dota 2", "9 Jul, 2013"),
    (730,    "Counter-Strike 2", "21 Aug, 2012"),
    (292030, "The Witcher 3", "18 May, 2015"),
    (1245620, "Elden Ring", "25 Feb, 2022"),
    (1086940, "Baldur's Gate 3", "3 Aug, 2023"),
    (489830, "Skyrim Special Edition", "28 Oct, 2016"),
    (275850, "No Man's Sky", "12 Aug, 2016"),
    (480,    "Spacewar", "1 Jan, 2015"),
    (289070, "Sid Meier's Civilization VI", "21 Oct, 2016"),
    (1174180, "Red Dead Redemption 2", "5 Dec, 2019"),
    (271590, "Grand Theft Auto V", "14 Apr, 2015"),
    (374320, "DARK SOULS III", "12 Apr, 2016"),
    (814380, "Sekiro: Shadows Die Twice", "22 Mar, 2019"),
    (1091500, "Cyberpunk 2077", "10 Dec, 2020"),
    (582010, "Monster Hunter: World", "9 Aug, 2018"),
    (251570,  "7 Days to Die", "13 Dec, 2013"),
    (381210,  "Dead by Daylight", "14 Jun, 2016"),
    (578080,  "PUBG: BATTLEGROUNDS", "21 Dec, 2017"),
    (359550,  "Tom Clancy's Rainbow Six Siege", "1 Dec, 2015"),
    (252490,  "Rust", "11 Dec, 2013"),
    (431960,  "Wallpaper Engine", "17 Nov, 2018"),
    (1172470, "Apex Legends", "5 Nov, 2020"),
    (440900,  "Conan Exiles", "8 May, 2018"),
    (346110,  "ARK: Survival Evolved", "2 Jun, 2015"),
    (242760,  "The Forest", "30 Apr, 2018"),
    (294100,  "RimWorld", "17 Oct, 2018"),
    (261550,  "Mount & Blade II: Bannerlord", "25 Oct, 2022"),
    (108600,  "Project Zomboid", "8 Nov, 2013"),
    (427520,  "Factorio", "14 Aug, 2020"),
    (322330,  "Don't Starve Together", "21 Apr, 2016"),
    (1366540, "Dyson Sphere Program", "21 Jan, 2021"),
    (892970,  "Valheim", "2 Feb, 2021"),
    (1150690, "Omega Strikers", "16 Sep, 2022"),
    (1332010, "Stray", "19 Jul, 2022"),
    (1426210, "It Takes Two", "26 Mar, 2021"),
]


async def seed_database(db_path: Optional[str] = None, max_games: int = 50) -> list[int]:
    """Ingest seed games into the database. Skips already-ingested games."""
    import pipeline.db as db

    database = await db.get_db(db_path)

    # Check which apps are already in the database
    cursor = await database.execute("SELECT app_id FROM games")
    existing = {row["app_id"] for row in await cursor.fetchall()}
    await database.close()

    to_ingest = [app_id for app_id, _, _ in SEED_GAMES[:max_games]
                 if app_id not in existing]

    print(f"Seed: {len(to_ingest)} new games to ingest out of {len(SEED_GAMES[:max_games])} seed games")

    if to_ingest:
        results = await ingest.ingest_batch(to_ingest, db_path=db_path, delay=2.0)
        ok = sum(1 for r in results if r["status"] in ("ok", "cached"))
        failed = sum(1 for r in results if r["status"] == "error")
        print(f"Seed complete: {ok} ok, {failed} failed")
    else:
        print("All seed games already in database.")

    # Force correct release dates for seed games
    database = await db.get_db(db_path)
    for app_id, name, rel_date in SEED_GAMES[:max_games]:
        if app_id in to_ingest or True:  # Always update release date
            await database.execute(
                "UPDATE games SET release_date = ? WHERE app_id = ?",
                (rel_date, app_id))
    await database.commit()
    await database.close()

    return [(app_id, name) for app_id, name, _ in SEED_GAMES[:max_games]]
