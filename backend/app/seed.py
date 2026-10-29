"""Create the schema and seed offline content, then register a Daily for a range
of dates (so `GET /api/daily` always works regardless of the machine date).

Run:  python -m app.seed
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .config import get_settings
from .db import SessionLocal, engine
from .matching import normalize
from .models import (
    Alias,
    Base,
    Entity,
    Prompt,
    PromptAnswer,
    Puzzle,
)
from .seed_data import PROMPTS

settings = get_settings()


def reset_schema() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed() -> None:
    reset_schema()
    db = SessionLocal()
    try:
        prompt_ids: list[str] = []
        for pdef in PROMPTS:
            prompt = Prompt(
                text=pdef["text"],
                accepted_entity_types=pdef["types"],
                status="published",
            )
            db.add(prompt)
            db.flush()
            prompt_ids.append(prompt.id)

            for (title, etype, year, prior, aliases) in pdef["answers"]:
                norm = normalize(title)
                entity = (
                    db.query(Entity)
                    .filter(Entity.normalized_title == norm, Entity.type == etype)
                    .first()
                )
                if entity is None:
                    entity = Entity(
                        type=etype,
                        canonical_title=title,
                        normalized_title=norm,
                        year=year,
                        popularity=prior * 100,
                        vote_count=int(prior * 10000),
                    )
                    db.add(entity)
                    db.flush()
                    for a in aliases:
                        db.add(Alias(entity_id=entity.id, alias_normalized=normalize(a)))
                db.add(
                    PromptAnswer(
                        prompt_id=prompt.id, entity_id=entity.id, prior_share=prior
                    )
                )
        db.flush()

        # Register the same 7-prompt Daily for a window around "today" so the game
        # is playable immediately in the offline slice. Real deployments generate
        # distinct puzzles per date.
        today = datetime.now(settings.tz).date()
        base_number = 1
        for offset in range(-3, 8):  # a few past days + the next week
            d = today + timedelta(days=offset)
            db.add(
                Puzzle(
                    date=d.isoformat(),
                    mode="daily",
                    prompt_ids=prompt_ids,
                    number=base_number + (offset + 3),
                )
            )

        db.commit()
        print(f"Seeded {len(PROMPTS)} prompts and a Daily for {today.isoformat()} "
              f"(+/- window). DB: {settings.database_url}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
