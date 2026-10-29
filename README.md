# Cold Open

A free, browser-based daily game for movie & TV fans. Every day everyone gets the same 7 prompts. Type an answer; the **rarer** your valid answer, the more points it scores. A fixed pixel-art character climbs a rags-to-fame ladder as you score, and the location you finish in is your daily rank.

> This repository is a **runnable offline vertical slice** (Option B from the handoff). It runs with **no TMDB key and no external database** — a FastAPI backend with SQLite seed data, and a React + Vite + Tailwind PWA with a 180×320 Canvas pixel-art climb. TMDB ingestion, Postgres/Supabase, the full prompt corpus, Endless/Packs/social, and the admin queue are planned follow-ups.

## Layout

```
backend/    FastAPI: matching, scoring, rarity blend, run lifecycle, SQLite, tests
frontend/   React + TS + Vite + Tailwind PWA, Canvas pixel-art climb renderer
.kiro/      Spec (requirements.md; design/tasks to follow)
```

## Quick start

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed          # create + seed cold_open.db
uvicorn app.main:app --reload --port 8000
```

API now at http://localhost:8000 (docs at /docs).

Run the tests:

```bash
cd backend
source .venv/bin/activate
pytest -q
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App at http://localhost:5173 (proxies /api to the backend on :8000).

## Design decisions baked in

- **Server-authoritative** scoring and timing. No valid-answer or rarity data reaches the client before submission (R9, R10, R50).
- **Rarity blend:** `share = (prior_weight * prior_share + observed) / (prior_weight + total)` with `prior_weight = max(20, 200 - total)` (R18, Q4 default).
- **Typed prompts:** each prompt declares `accepted_entity_types` (Q1 default).
- **Score locking** at submission time (R17).
- **Pixel art:** 180×320 internal resolution, integer scaling, `image-rendering: pixelated`, single palette file, placeholder procedural art behind an asset manifest (R37–R40).

## Attribution

Movie/TV data model is TMDB-shaped. When real TMDB data is wired in, the required TMDB attribution must be shown wherever that data appears (R54). This product uses TMDB but is not endorsed or certified by TMDB.
