"""Resolver tests use their OWN isolated SQLite DB (a temp file with its own
engine/session), so deleting/ingesting entities here cannot affect the shared
session-scoped DB used by the API and seed tests."""
import math
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.prompts.resolver import resolve
from app.prompts.schema import PromptDef, QuerySpec
from app.tmdb.ingest import ingest


@pytest.fixture
def db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    engine = create_engine(f"sqlite:///{tmp.name}", future=True)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, future=True)
    session = Session()
    ingest(session)  # offline fixtures
    session.commit()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def test_query_by_genre_resolves_horror(db):
    prompt = PromptDef(
        id="horror",
        text="Name a horror movie",
        kind="query",
        accepted_entity_types=["movie"],
        query=QuerySpec(genres_any=[27], min_vote_count=0, limit=200),  # 27 = Horror
    )
    res = resolve(db, prompt)
    titles = [a.title for a in res.answers]
    assert "Alien" in titles
    assert "The Thing" in titles
    assert "Get Out" in titles
    assert "Titanic" not in titles
    assert math.isclose(sum(a.prior_share for a in res.answers), 1.0, abs_tol=1e-6)
    assert res.answers[0].prior_share >= res.answers[-1].prior_share


def test_query_year_filter(db):
    prompt = PromptDef(
        id="modern",
        text="Name a sci-fi movie from the 2010s",
        kind="query",
        accepted_entity_types=["movie"],
        query=QuerySpec(genres_any=[878], year_min=2010, year_max=2019, limit=200),
    )
    res = resolve(db, prompt)
    titles = [a.title for a in res.answers]
    assert "Interstellar" in titles  # 2014 sci-fi
    assert "The Matrix" not in titles  # 1999, filtered out


def test_curated_resolution_reports_unresolved(db):
    prompt = PromptDef(
        id="mix",
        text="Name a classic movie",
        kind="curated",
        accepted_entity_types=["movie"],
        answers=["Inception", "The Matrix", "A Totally Made Up Film 9000"],
    )
    res = resolve(db, prompt)
    resolved_titles = [a.title for a in res.answers]
    assert "Inception" in resolved_titles
    assert "The Matrix" in resolved_titles
    assert "A Totally Made Up Film 9000" in res.unresolved_titles


def test_duplicate_title_keeps_most_popular(db):
    # Insert a low-popularity stub sharing a canonical title with a fixture row.
    from app.matching import normalize
    from app.models import Entity

    stub = Entity(
        tmdb_id=None,
        type="movie",
        canonical_title="Inception",
        normalized_title=normalize("Inception"),
        year=2010,
        popularity=1.0,
        vote_count=1,
        genre_ids=[],
        source="seed",
    )
    db.add(stub)
    db.commit()

    prompt = PromptDef(
        id="dup",
        text="Name a movie",
        kind="curated",
        accepted_entity_types=["movie"],
        answers=["Inception"],
    )
    res = resolve(db, prompt)
    # Exactly one "Inception", and it's the high-popularity fixture row.
    incs = [a for a in res.answers if a.title == "Inception"]
    assert len(incs) == 1
    assert incs[0].entity_id != stub.id


def test_query_titles_merge_in(db):
    prompt = PromptDef(
        id="nolan",
        text="Name a film directed by Christopher Nolan",
        kind="query",
        accepted_entity_types=["movie"],
        query=QuerySpec(titles=["Inception", "Interstellar", "The Dark Knight"], limit=200),
    )
    res = resolve(db, prompt)
    titles = [a.title for a in res.answers]
    assert "Inception" in titles
    assert "Interstellar" in titles
    assert "The Dark Knight" in titles
