"""CLI: python -m app.tmdb [--movie-pages N] [--tv-pages N]

Creates the schema if needed and ingests entities (live if TMDB_API_KEY /
TMDB_READ_TOKEN is set, else fixtures).
"""
from __future__ import annotations

import argparse

from ..db import SessionLocal, engine
from ..models import Base
from .ingest import ingest


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest TMDB entities.")
    # Default None -> use configured volume (COLDOPEN_TMDB_MOVIE_PAGES/_TV_PAGES).
    parser.add_argument("--movie-pages", type=int, default=None)
    parser.add_argument("--tv-pages", type=int, default=None)
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        result = ingest(db, movie_pages=args.movie_pages, tv_pages=args.tv_pages)
        db.commit()
        print(
            f"Ingest [{result['mode']}]: {result['records']} records -> "
            f"{result['created']} created, {result['updated']} updated"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
