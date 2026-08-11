# Game PMF Analyzer

Post-launch product-market fit signal report for indie games on Steam.

Enter any Steam App ID and get a 3-lens analysis: Satisfaction, Engagement, Reach.

## Quick Start

```bash
cd web
npm install
npm run dev
```

Open http://localhost:5174 — enter a Steam App ID like `105600` (Terraria).

## Full Pipeline (CLI)

```bash
pip3 install -r pipeline/requirements.txt
python3 -m pipeline.main seed         # ingest 50+ games
python3 -m pipeline.main report 730   # PMF report for CS2
python3 -m pipeline.main cohort 730   # cohort comparison
python3 -m pipeline.main updates 730  # patch timeline
```

## Deploy

```bash
bash sync.sh "your commit message"
```

Builds frontend, pushes to git, and uploads to FTP.

## Structure

```
web/        — React dashboard (Vite + Recharts)
pipeline/   — Python CLI tools (SQLite, Steam ingestion, scoring)
backend/    — FastAPI wrapper (optional, for local API server)
api-backup/ — PHP fallback for shared hosting
```
