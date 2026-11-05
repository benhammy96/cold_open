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

## Deploy (Render)

`render.yaml` is a Render Blueprint defining three resources: managed Postgres,
the FastAPI API, and the static frontend.

1. In the Render dashboard, **New → Blueprint**, connect this repo. Render creates
   the database and both services. The API auto-wires `DATABASE_URL` and generates
   `COLDOPEN_TOKEN_SECRET`; its prestart seeds the DB from keyless fixtures.
2. Two cross-origin URLs can't be auto-wired (a service's public URL isn't known
   until it exists), so set them in the dashboard after the first deploy, then
   redeploy each service:
   - `cold-open-web` → `VITE_API_BASE` = the API's public URL (e.g.
     `https://cold-open-api.onrender.com`)
   - `cold-open-api` → `COLDOPEN_CORS_ORIGINS` = the site's public URL (e.g.
     `https://cold-open-web.onrender.com`)
3. Open the static site URL to play.

The API switches to Postgres automatically via `DATABASE_URL` (a `postgres://`
value is normalized to `postgresql+psycopg://`). Re-seeding is idempotent
(`python -m app.seed --if-empty` only seeds an empty DB). See `backend/.env.example`
and `frontend/.env.example` for all variables.

> **Free tier note:** the free API instance sleeps when idle, so the first
> request after a quiet period takes a few seconds to wake.

### Adding the real TMDB catalog (Task 8)

The first deploy runs on the keyless fixture catalog. To switch to real data:

1. On the **cold-open-api** service, set env vars (the blueprint pre-declares
   these; set the key's VALUE in the dashboard, never in the repo):
   - `TMDB_API_KEY` = your v3 key (or use `TMDB_READ_TOKEN` for a v4 bearer)
   - `COLDOPEN_STRICT_CONTENT` = `true`, `COLDOPEN_TMDB_MOVIE_PAGES` / `_TV_PAGES`
     control ingest volume (defaults 250 / 150 ≈ 5000 movies + 3000 shows)
2. Set `COLDOPEN_RESEED_ON_BOOT` = `true` and **redeploy** the API. On boot it
   runs a full reseed from TMDB (ingest → resolve → validate → publish). Watch
   the deploy logs for the summary and any "Unresolved curated titles" — those
   are `prompts.yaml` titles that didn't match a real TMDB entity; fix and
   redeploy.
3. Set `COLDOPEN_RESEED_ON_BOOT` back to `false` so future restarts don't wipe
   accumulated play data.

Reseeding replaces content (entities, prompts, schedule) but is only triggered
by the toggle; normal restarts seed only an empty DB.

> **SSL note:** the TMDB client uses the `certifi` CA bundle explicitly, so HTTPS
> calls work on containers without a configured system trust store.

## Design decisions baked in

- **Server-authoritative** scoring and timing. No valid-answer or rarity data reaches the client before submission (R9, R10, R50).
- **Rarity blend:** `share = (prior_weight * prior_share + observed) / (prior_weight + total)` with `prior_weight = max(20, 200 - total)` (R18, Q4 default).
- **Typed prompts:** each prompt declares `accepted_entity_types` (Q1 default).
- **Score locking** at submission time (R17).
- **Pixel art:** 180×320 internal resolution, integer scaling, `image-rendering: pixelated`, single palette file, placeholder procedural art behind an asset manifest (R37–R40).

## Attribution

Movie/TV data model is TMDB-shaped. When real TMDB data is wired in, the required TMDB attribution must be shown wherever that data appears (R54). This product uses TMDB but is not endorsed or certified by TMDB.
