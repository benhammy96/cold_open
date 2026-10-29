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
python -m app.seed          # ingest entities + resolve the prompt corpus -> cold_open.db
uvicorn app.main:app --reload --port 8000
```

API now at http://localhost:8000 (docs at /docs).

### Content pipeline

Seeding runs the full pipeline: ingest entities (TMDB or fixtures) -> load
`content/prompts.yaml` -> resolve each prompt to entities + prior shares ->
validate -> publish -> build a rotating daily schedule.

```bash
# Ingest only (TMDB if a key is set, else keyless fixtures):
python -m app.tmdb                       # add --movie-pages / --tv-pages for more

# Validate the prompt corpus (CI-friendly exit code):
python -m app.prompts validate content/prompts.yaml --resolve
```

Prompts come in two kinds (`content/prompts.yaml`): **query** (genre/year/vote
filters, scale automatically on real data) and **curated** (hand-reviewed title
lists for director/award/premise categories).

**TMDB key:** set `TMDB_API_KEY` (v3) or `TMDB_READ_TOKEN` (v4 bearer) in the
environment, then re-seed. Without a key the pipeline uses a ~90-title fixture
catalog, so genre/era prompts with too few fixture answers are skipped (they
publish automatically once real data is ingested). Set
`COLDOPEN_STRICT_CONTENT=true` on real data to enforce the §4 rule of >= 40
answers per prompt.

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
