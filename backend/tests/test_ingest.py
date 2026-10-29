from app.db import SessionLocal
from app.matching import normalize
from app.models import Entity
from app.tmdb.ingest import _alias_variants, ingest
from sqlalchemy import select, func


def test_alias_variants():
    v = _alias_variants("The Lord of the Rings: The Fellowship of the Ring")
    # Only the leading article is stripped; internal "the" is kept.
    assert "lord of the rings the fellowship of the ring" in v
    assert "lord of the rings" in v  # colon subtitle stripped


def test_alias_roman_numerals():
    v = _alias_variants("Rocky III")
    assert "rocky 3" in v


def test_fixture_ingest_is_idempotent():
    # conftest already seeded; ingest fixtures on top (offline mode, no key).
    db = SessionLocal()
    try:
        r1 = ingest(db)
        db.commit()
        assert r1["mode"] == "fixture"
        assert r1["records"] > 50
        count1 = db.scalar(select(func.count()).select_from(Entity).where(Entity.source == "fixture"))
        # Re-run: nothing new created, existing updated.
        r2 = ingest(db)
        db.commit()
        assert r2["created"] == 0
        count2 = db.scalar(select(func.count()).select_from(Entity).where(Entity.source == "fixture"))
        assert count1 == count2
    finally:
        db.close()


def test_ingested_entity_has_genres_and_popularity():
    db = SessionLocal()
    try:
        ingest(db)
        db.commit()
        inception = db.scalar(
            select(Entity).where(
                Entity.normalized_title == normalize("Inception"),
                Entity.type == "movie",
                Entity.source == "fixture",
            )
        )
        assert inception is not None
        assert inception.popularity > 0
        assert inception.tmdb_id == 27205
        assert 878 in inception.genre_ids  # Sci-Fi
    finally:
        db.close()
