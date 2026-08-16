# HANDOFF — Game PMF Analyzer

> Read this first. It contains everything the next agent needs: project history, architecture, credentials, deployment, scoring model, and known issues.

---

## 1. One-paragraph summary

A **Product-Market Fit (PMF) analyzer for indie games on Steam**. A user enters any Steam App ID and gets a live 3-lens analysis — **Satisfaction** (are buyers glad?), **Engagement** (are they playing?), **Reach** (is it finding an audience?) — plus a refund-window signal, genre benchmark comparison, sentiment keyword cloud, Sean Ellis survey, and rule-based recommendations.

It is **fully dynamic**: no pre-stored database is required for the web app. The hosted PHP API fetches everything live from Steam's public endpoints. A separate Python CLI/pipeline exists for offline analysis, daily snapshots, and cohort computation (this part uses a local SQLite DB).

---

## 2. Where things live

| Thing | Location |
|---|---|
| **Local project** | `/Users/abbas/Projects/GameOS/PMF` |
| **Live site** | `https://llamagriffin.com/game-os/PMF/` |
| **Live API** | `https://llamagriffin.com/game-os/PMF/api/v1/analyze` (POST `{"app_id": <int>}`) |
| **GitHub repo** | `https://github.com/bakatronix/game-pmf-analyzer` (user: `bakatronix`) |
| **Old/test location** | `https://llamagriffin.com/mtg-test/` (deprecated, ignore) |

Note: an earlier copy also lives at `/Users/abbas/Documents/New OpenCode Project/` — that is the **pre-move** working copy. The canonical project is `/Users/abbas/Projects/GameOS/PMF`.

---

## 3. Project structure

```
PMF/
├── web/                    # React dashboard (Vite + Recharts) — THE PRODUCT
│   ├── src/
│   │   ├── App.jsx         # Layout, search bar, fetch logic
│   │   └── components/
│   │       ├── ScoreCard.jsx        # 3 radial gauges (Sat/Eng/Reach) + CI bands
│   │       ├── ScoreBreakdown.jsx   # per-lens progress bars
│   │       ├── PlaytimeHistogram.jsx # bar chart w/ sub-2h refund signal
│   │       ├── CohortTable.jsx      # percentile ranks vs peers (usually null on live)
│   │       ├── ReviewPanel.jsx      # score %, trend badge, pos/neg counts
│   │       ├── SentimentPanel.jsx   # compound score + keyword cloud
│   │       ├── BenchmarkBars.jsx    # genre benchmark comparison
│   │       ├── Recommendations.jsx  # HIGH/MED/LOW cards
│   │       └── SeanEllisSurvey.jsx  # localStorage-backed survey
│   ├── vite.config.js       # base: '/game-os/PMF/'
│   └── .env.production      # VITE_API_URL=/game-os/PMF/api/v1
│
├── api-backup/v1/index.php  # PHP backend (CANONICAL for shared hosting)
├── pipeline/                # Python CLI + offline engine (SQLite)
│   ├── main.py              # CLI: ingest/backfill/seed/refresh/status/report/cohort/updates
│   ├── fetchers.py          # Steam API fetchers + rate limiter (1.5s, exp backoff)
│   ├── db.py                # SQLite schema (8 tables)
│   ├── ingest.py            # orchestration + daily refresh
│   ├── report.py            # scoring + report formatting
│   ├── cohort.py            # ±90-day cohort, percentile ranks
│   ├── discover.py          # 50-game seed dataset
│   └── updates.py           # patch timeline / inflection analysis
│
├── backend/                 # FastAPI wrapper (optional local API server, port 8000)
├── data/pmf.db              # SQLite DB (~60 games) — gitignored
├── step1_validate.py        # validation notebook (separation test)
├── step1_validation.png     # output chart
├── sync.sh                  # ONE-COMMAND deploy (git+build+FTP)
└── README.md
```

---

## 4. Credentials & deployment

### Git
- **Repo**: `https://github.com/bakatronix/game-pmf-analyzer.git`
- **Token / credentials**: see `CREDENTIALS.md` (gitignored, local-only)
- **Branch**: `main`

### FTP (Namecheap / LiteSpeed)
- **Host**: `ftp.bakatron.com`
- **Credentials**: see `CREDENTIALS.md`
- **Web root path**: `/game-os/PMF/`
- **Site URL**: `https://llamagriffin.com/game-os/PMF/`

---

## 5. Deploy workflow (CRITICAL)

**Every change must be synced to all three places** (user's standing instruction):

```bash
cd /Users/abbas/Projects/GameOS/PMF
bash sync.sh "description of change"
```

`sync.sh` does, in order:
1. `git add -A && git commit && git push origin main`
2. `cd web && npm run build`
3. FTP-uploads `web/dist/**` to `/game-os/PMF/`, restoring the PHP file from `api-backup/v1/index.php` (because Vite wipes `dist/` on rebuild), and writing `.htaccess`.

**⚠️ KNOWN BUG in sync.sh:** line 6 has a stale hardcoded path `cd "/Users/abbas/GameOS/PMF"` — the project moved to `/Users/abbas/Projects/GameOS/PMF`. Fix this before relying on it. (Run it from the correct dir with `cd` already done, or edit the path.)

### Important gotcha when editing PHP
The **canonical PHP backend is `api-backup/v1/index.php`**, NOT `web/dist/api/v1/index.php`. Vite deletes `dist/` on every build, so the live PHP is restored from `api-backup/` by the sync script. **Edit `api-backup/v1/index.php` only**, or your changes will be lost on next build.

---

## 6. Scoring model (the spec — v0.1)

Three independent lens scores (0–100), **no composite as headline** (deliberate design decision — see "Design rationale" below).

### Satisfaction
```
positive_pct = total_positive / total_reviews * 100
recent_pct   = recent_positive / recent_total * 100   (30-day)
trend_bonus  = clip(recent_pct - positive_pct, -10, +10)
satisfaction = clip(positive_pct + 0.5 * trend_bonus, 0, 100)
```
Confidence: ±5 (>500 reviews), ±10 (100–500), ±20 (50–100), undefined (<50).

### Engagement
```
median_hr      = median(playtime_sample) / 60
playtime_score = clip(log1p(median_hr) / log1p(genre_median * 3) * 95, 0, 95)
sub2h_ratio    = fraction of sample < 120 min  ← refund-window signal
hook_score     = clip((1 - sub2h_ratio) * 100, 0, 100)
depth_score    = clip(deepest_achievement_pct * 3, 0, 100)
engagement     = 0.50*playtime_score + 0.30*hook_score + 0.20*depth_score
```

### Reach
```
review_volume_score = clip(log10(max(total_reviews,1)) * 25, 0, 100)
velocity_score      = clip(log1p(velocity) / log1p(cohort_p90_velocity) * 100, 0, 100)
ccu_score           = clip(log1p(peak_ccu) / log1p(cohort_p90_ccu) * 100, 0, 100)
reach               = 0.40*review_volume + 0.35*velocity + 0.25*ccu
```

### Qualitative label (rule-based tree)
- All ≥70 → "Strong PMF signal across all dimensions"
- Sat≥75, Eng≥70, Reach<50 → "Niche hit not yet finding its audience"
- Sat≥70, Eng<50 → "Good first impression, weak retention hook"
- Eng≥70, Sat<60 → "Engaged but divisive"
- All <50 → "Weak signal"
- else → "Mixed signals"

---

## 7. Design rationale (anti-spec — do NOT reintroduce)

From the original deep design note. These were **deliberately rejected**:

- **Single 0–100 PMF score as headline** — too fragile, publicly screenshotable, invites arguing with the number. (The old `frontend/` at the pre-move location had this; it was superseded.)
- **SteamSpy / Boxleiter owner estimates** — degraded since 2018, wide error bars damage credibility.
- **Wishlist velocity in free tier** — Steamworks-gated; can't be honest without OAuth.
- **Generic VADER/distilBERT sentiment** — gaming vernacular breaks it ("sick", "broken", "cope"). Current keyword-lexicon approach is a stopgap; domain-tuned clustering was planned for v0.2.
- **Dev-picked competitors** — flattering-picked; replaced with auto ±90-day + tag-match cohort.
- **In-game telemetry SDK** — chicken-and-egg; deferred to v2.
- **LLM-generated recommendations** — rule-based is more defensible at launch.

---

## 8. History (what was built, in order)

1. **Original build** (at `/Users/abbas/Documents/New OpenCode Project/`): FastAPI backend + React frontend with a single composite PMF score, SteamSpy estimates, generic VADER sentiment. Deployed to `/mtg-test/`.
2. **Deep design note** arrived — full re-spec (3 lenses, no composite, Next-100 cohort, refund-window + update-cadence as moat features, validation-first).
3. **Step 1 — Validation notebook** (`step1_validate.py`): proved 3-lens scoring separates 10 hits from 10 misses. GATE GREEN.
4. **Step 2 — Ingestion pipeline** (`pipeline/`): SQLite DB, Steam fetchers with rate limiting, daily refresh, CLI (`python3 -m pipeline.main`).
5. **Step 3 — CLI report generator** (`pipeline/report.py`): full text report with lens scorecards, playtime histogram, recommendations.
6. **Step 4 — Next 100 cohort** (`pipeline/cohort.py`): ±90-day + tag-match cohort, percentile ranks; 60-game seed DB.
7. **Step 5 — Refund-window + update-cadence** (`pipeline/updates.py`): sub-2h signal + patch timeline overlay.
8. **Step 6 — Web UI** (`web/`): React + Recharts dashboard.
9. **Restored features**: user wanted the old richer UI back — added ReviewPanel, SentimentPanel, BenchmarkBars, SeanEllisSurvey.
10. **Made dynamic**: PHP backend (`api-backup/v1/index.php`) fetches Steam live, no DB needed on hosting.
11. **Moved project** to `/Users/abbas/GameOS/PMF` → later `/Users/abbas/Projects/GameOS/PMF`.
12. **Deployed to** `https://llamagriffin.com/game-os/PMF/`.
13. **Created GitHub repo** `bakatronix/game-pmf-analyzer`, added `sync.sh` for git+build+FTP.

---

## 9. Known issues / gotchas

- **sync.sh has stale path** (line 6): `/Users/abbas/GameOS/PMF` → should be `/Users/abbas/Projects/GameOS/PMF`.
- **PHP is canonical in `api-backup/`**, not `web/dist/` (Vite wipes dist).
- **Velocity calc is approximate** — the PHP backend uses `total/30` as a proxy for recent reviews/day; the proper Steam `filter=recent` endpoint wasn't fully wired. Python pipeline's `fetch_recent_reviews` exists but the PHP doesn't call it.
- **Cohort is null on the live site** — the PHP API doesn't compute cohorts (needs the Python pipeline's SQLite DB). The `CohortTable.jsx` gracefully shows "no cohort data". Full cohort only works via CLI.
- **Achievement endpoints 403** for delisted/old games; code handles gracefully.
- **Git token is committed in remote URL** (`git remote -v` shows it). Fine for personal use, but don't share the repo publicly without rotating.

---

## 10. Data sources (Steam endpoints)

| Signal | Endpoint |
|---|---|
| App metadata / tags | `store.steampowered.com/api/appdetails?appids={id}&l=english` |
| Reviews + playtime | `store.steampowered.com/appreviews/{id}?json=1&num_per_page=100&cursor=*` |
| Achievement % | `api.steampowered.com/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/?gameid={id}` |
| Current players | `api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={id}` |
| Patch/news | `api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid={id}` |

Rate limits: ~1.5s between calls, exponential backoff on 429/5xx, cache 1h (reviews) / 24h (achievements).

---

## 11. Open questions / next steps (not yet done)

- Fix `sync.sh` path bug.
- Wire real `filter=recent` reviews for accurate velocity in PHP.
- Wire cohort computation into the hosted API (would require keeping a server-side DB).
- Sentiment v0.2: domain-tuned keyword clustering (replaces naive lexicon).
- Shareable URLs (`?app_id=105600` auto-load) — user expressed interest.
- Side-by-side comparison mode — user expressed interest.
- Real review snippets in UI — user expressed interest.

---

## 12. How to run locally

```bash
# Web app
cd /Users/abbas/Projects/GameOS/PMF/web
npm install
npm run dev          # → http://localhost:5174

# Python pipeline
cd /Users/abbas/Projects/GameOS/PMF
pip3 install -r pipeline/requirements.txt
python3 -m pipeline.main status
python3 -m pipeline.main report 105600

# FastAPI backend (optional)
cd /Users/abbas/Projects/GameOS/PMF/backend
python3 -m uvicorn app.main:app --port 8000
```

---

## 13. Test App IDs

Hits: `105600` Terraria, `413150` Stardew Valley, `1145360` Hades, `2379780` Balatro, `367520` Hollow Knight.
Misses: `49540` Aliens: Colonial Marines, `578080` PUBG, `582660` Skylight Freerange 2, `37100` Aztaka.
