"""Ingest movie/TV entities into the DB.

Live mode (key present): pulls the top N popular movies and shows via discover,
paging until the target count is reached. Offline mode (no key): loads the
fixtures. Either way the output is the same shape: upserted Entity rows keyed on
(tmdb_id, type), with popularity, vote_count and genre_ids, plus a couple of
cheap aliases (e.g. article-stripped, roman-numeral/number variants).

Idempotent: re-running updates popularity/vote_count in place rather than
duplicating rows.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..matching import normalize
from ..models import Alias, Entity
from .client import TMDBClient
from .fixtures import FIXTURE_MOVIES, FIXTURE_TV


@dataclass
class EntityRecord:
    tmdb_id: int
    type: str  # movie|show
    title: str
    year: int | None
    popularity: float
    vote_count: int
    genre_ids: list[int]
    source: str


def _records_from_fixtures() -> list[EntityRecord]:
    out: list[EntityRecord] = []
    for (tid, title, year, pop, votes, genres) in FIXTURE_MOVIES:
        out.append(EntityRecord(tid, "movie", title, year, pop, votes, list(genres), "fixture"))
    for (tid, title, year, pop, votes, genres) in FIXTURE_TV:
        out.append(EntityRecord(tid, "show", title, year, pop, votes, list(genres), "fixture"))
    return out


def _year_from_date(date_str: str | None) -> int | None:
    if not date_str or len(date_str) < 4:
        return None
    try:
        return int(date_str[:4])
    except ValueError:
        return None


def _records_from_tmdb(client: TMDBClient, movie_pages: int, tv_pages: int) -> list[EntityRecord]:
    out: list[EntityRecord] = []
    for page in range(1, movie_pages + 1):
        data = client.discover_movies(page=page, **{"vote_count.gte": 200})
        for r in data.get("results", []):
            out.append(
                EntityRecord(
                    tmdb_id=r["id"],
                    type="movie",
                    title=r.get("title") or r.get("original_title") or "",
                    year=_year_from_date(r.get("release_date")),
                    popularity=float(r.get("popularity", 0.0)),
                    vote_count=int(r.get("vote_count", 0)),
                    genre_ids=list(r.get("genre_ids", [])),
                    source="tmdb",
                )
            )
    for page in range(1, tv_pages + 1):
        data = client.discover_tv(page=page, **{"vote_count.gte": 100})
        for r in data.get("results", []):
            out.append(
                EntityRecord(
                    tmdb_id=r["id"],
                    type="show",
                    title=r.get("name") or r.get("original_name") or "",
                    year=_year_from_date(r.get("first_air_date")),
                    popularity=float(r.get("popularity", 0.0)),
                    vote_count=int(r.get("vote_count", 0)),
                    genre_ids=list(r.get("genre_ids", [])),
                    source="tmdb",
                )
            )
    return out


def _alias_variants(title: str) -> set[str]:
    """Cheap deterministic aliases that help matching without TMDB AKA calls."""
    variants: set[str] = set()
    norm = normalize(title)
    variants.add(norm)
    # Colon subtitle -> main part only ("Star Wars: A New Hope" -> "star wars").
    if ":" in title:
        variants.add(normalize(title.split(":")[0]))
    # Roman numeral / number swaps for common sequels.
    roman = {" ii": " 2", " iii": " 3", " iv": " 4", " v": " 5"}
    for r, n in roman.items():
        if norm.endswith(r):
            variants.add(norm[: -len(r)] + n)
    variants.discard("")
    return variants


def upsert_entities(db: Session, records: list[EntityRecord]) -> tuple[int, int]:
    """Insert or update entities. Returns (created, updated)."""
    created = updated = 0
    for rec in records:
        if not rec.title:
            continue
        existing = db.scalar(
            select(Entity).where(Entity.tmdb_id == rec.tmdb_id, Entity.type == rec.type)
        )
        norm = normalize(rec.title)
        if existing is None:
            ent = Entity(
                tmdb_id=rec.tmdb_id,
                type=rec.type,
                canonical_title=rec.title,
                normalized_title=norm,
                year=rec.year,
                popularity=rec.popularity,
                vote_count=rec.vote_count,
                genre_ids=rec.genre_ids,
                source=rec.source,
            )
            db.add(ent)
            db.flush()
            for a in _alias_variants(rec.title):
                if a != norm:
                    db.add(Alias(entity_id=ent.id, alias_normalized=a))
            created += 1
        else:
            existing.popularity = rec.popularity
            existing.vote_count = rec.vote_count
            existing.genre_ids = rec.genre_ids
            existing.source = rec.source
            updated += 1
    db.flush()
    return created, updated


def ingest(db: Session, movie_pages: int = 5, tv_pages: int = 3) -> dict:
    """Entry point. Uses live TMDB if a key is set, else fixtures."""
    client = TMDBClient()
    if client.offline:
        records = _records_from_fixtures()
        mode = "fixture"
    else:
        records = _records_from_tmdb(client, movie_pages, tv_pages)
        mode = "tmdb"
    created, updated = upsert_entities(db, records)
    return {"mode": mode, "records": len(records), "created": created, "updated": updated}
