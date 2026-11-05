"""Seed the database from the real prompt corpus (Task 5).

Pipeline:
  1. reset schema
  2. ingest entities (TMDB if a key is set, else fixtures)
  3. load content/prompts.yaml
  4. for each prompt: ensure its curated titles exist as entities (auto-create
     low-signal stubs for titles not in the catalog, so curated prompts are
     playable keyless and upgrade automatically when real TMDB rows land)
  5. resolve the prompt -> entities + prior shares, write Prompt + PromptAnswer
  6. validate (relaxed minimum in fixture mode) and report
  7. build a rotating schedule of distinct daily puzzles

Run:  python -m app.seed [--prompts PATH]
"""
from __future__ import annotations

import argparse
import os
import random
from datetime import datetime, timedelta

from .config import get_settings
from .db import SessionLocal, engine
from .matching import normalize
from .models import Alias, Base, Entity, Prompt, PromptAnswer, Puzzle
from .prompts.resolver import resolve
from .prompts.schema import PromptDef, load_prompts_file
from .prompts.validator import MIN_ANSWERS, validate_prompt
from .tmdb.ingest import ingest

settings = get_settings()

DEFAULT_PROMPTS = os.path.join(os.path.dirname(__file__), "..", "content", "prompts.yaml")


def reset_schema() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _ensure_curated_stubs(db, prompt: PromptDef) -> None:
    """Create low-signal entity stubs for curated titles missing from the catalog
    so the prompt is playable offline. Stubs get a small popularity so a real
    ingested row (higher popularity) always wins during resolution.

    Skipped in strict_content (live/prod) mode: there we WANT a curated title that
    doesn't match the real TMDB catalog to surface as unresolved, rather than be
    papered over by a stub (so authoring mistakes are caught)."""
    if settings.strict_content:
        return
    if prompt.kind != "curated" and not (prompt.query and prompt.query.titles):
        return
    titles = list(prompt.answers) if prompt.kind == "curated" else list(prompt.query.titles)
    etype = prompt.accepted_entity_types[0]  # stub as the prompt's primary type
    for title in titles:
        norm = normalize(title)
        exists = (
            db.query(Entity)
            .filter(Entity.normalized_title == norm, Entity.type.in_(prompt.accepted_entity_types))
            .first()
        )
        if exists is None:
            # Deterministic tiny popularity spread so stubs aren't all identical
            # (keeps prior shares from collapsing to uniform for offline play).
            seed_val = (abs(hash(norm)) % 1000) / 1000.0
            ent = Entity(
                type=etype,
                canonical_title=title,
                normalized_title=norm,
                year=None,
                popularity=1.0 + seed_val * 4.0,
                vote_count=int(50 + seed_val * 450),
                genre_ids=[],
                source="stub",
            )
            db.add(ent)
            db.flush()


def seed(prompts_path: str = DEFAULT_PROMPTS) -> None:
    reset_schema()
    db = SessionLocal()
    try:
        ingest_result = ingest(db)
        db.flush()

        corpus = load_prompts_file(prompts_path)
        min_answers = MIN_ANSWERS if settings.strict_content else settings.min_answers_fixture

        prompt_ids: list[str] = []
        failures: list[str] = []
        unresolved: dict[str, list[str]] = {}
        for pdef in corpus:
            _ensure_curated_stubs(db, pdef)
            db.flush()

            resolution = resolve(db, pdef)
            if resolution.unresolved_titles:
                unresolved[pdef.id] = resolution.unresolved_titles
            vr = validate_prompt(pdef, resolution.as_pairs(), min_answers=min_answers)
            if not vr.ok:
                failures.append(f"{pdef.id}: {'; '.join(vr.errors)}")
                continue  # skip prompts that fail validation

            prompt = Prompt(
                text=pdef.text,
                category=(pdef.tags[0] if pdef.tags else "general"),
                difficulty=pdef.difficulty,
                status="published",
                tags=pdef.tags,
                accepted_entity_types=pdef.accepted_entity_types,
            )
            db.add(prompt)
            db.flush()
            prompt_ids.append(prompt.id)
            for ans in resolution.answers:
                db.add(
                    PromptAnswer(
                        prompt_id=prompt.id,
                        entity_id=ans.entity_id,
                        prior_share=ans.prior_share,
                    )
                )
        db.flush()

        if len(prompt_ids) < settings.prompts_per_daily:
            raise RuntimeError(
                f"Only {len(prompt_ids)} prompts passed validation; need at least "
                f"{settings.prompts_per_daily} for a Daily."
            )

        _build_schedule(db, prompt_ids)
        db.commit()

        print(
            f"Seeded from {len(corpus)} authored prompts: {len(prompt_ids)} published, "
            f"{len(failures)} skipped. Entities [{ingest_result['mode']}]: "
            f"{ingest_result['created']} created. DB: {settings.database_url}"
        )
        if failures:
            print("Skipped prompts (insufficient/invalid):")
            for f in failures:
                print(f"  - {f}")
        if unresolved:
            total = sum(len(v) for v in unresolved.values())
            print(f"Unresolved curated titles ({total}) — fix these in prompts.yaml:")
            for pid, titles in unresolved.items():
                print(f"  {pid}: {', '.join(titles)}")
    finally:
        db.close()


def _build_schedule(db, prompt_ids: list[str]) -> None:
    """Register a window of distinct daily puzzles. Each day draws 7 prompts via
    a date-seeded shuffle so every date is a different, reproducible set."""
    today = datetime.now(settings.tz).date()
    per = settings.prompts_per_daily
    for offset in range(-3, 15):
        d = today + timedelta(days=offset)
        rng = random.Random(d.toordinal())  # reproducible per date
        pool = list(prompt_ids)
        rng.shuffle(pool)
        chosen = pool[:per]
        db.add(
            Puzzle(
                date=d.isoformat(),
                mode="daily",
                prompt_ids=chosen,
                number=d.toordinal() - today.toordinal() + 100,  # stable-ish number
            )
        )


def seed_if_empty(prompts_path: str = DEFAULT_PROMPTS) -> bool:
    """Idempotent bootstrap for deploys: seed only when the DB has no puzzles.

    Safe to run on every boot — it never drops data if content already exists.
    Returns True if seeding happened. Creates tables first so a fresh managed
    Postgres comes up populated.
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(Puzzle).first()
        if existing is not None:
            return False
    finally:
        db.close()
    seed(prompts_path)
    return True


def boot_seed(prompts_path: str = DEFAULT_PROMPTS) -> None:
    """Deploy boot entry. Honors COLDOPEN_RESEED_ON_BOOT: when true, force a full
    reseed (used once after adding the TMDB key); otherwise seed only if empty."""
    if settings.reseed_on_boot:
        print("RESEED_ON_BOOT=true -> forcing full reseed")
        seed(prompts_path)
    else:
        did = seed_if_empty(prompts_path)
        print("Seeded (DB was empty)." if did else "Content already present; skipped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Cold Open content.")
    parser.add_argument("--prompts", default=DEFAULT_PROMPTS)
    parser.add_argument(
        "--if-empty",
        action="store_true",
        help="Only seed when the DB has no puzzles (safe for deploy boot).",
    )
    parser.add_argument(
        "--boot",
        action="store_true",
        help="Deploy boot mode: full reseed if COLDOPEN_RESEED_ON_BOOT=true, else seed-if-empty.",
    )
    args = parser.parse_args()
    if args.boot:
        boot_seed(args.prompts)
    elif args.if_empty:
        did = seed_if_empty(args.prompts)
        print("Seeded." if did else "Content already present; skipped.")
    else:
        seed(args.prompts)


if __name__ == "__main__":
    main()
