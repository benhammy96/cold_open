"""Resolve a prompt into its concrete answer set (Task 4).

A `query` prompt declares criteria (entity types, genre filters, year range,
min vote count, explicit titles). This module turns that into a list of
ingested entities, derives each entity's prior share via priors.derive_prior_shares
(Task 2), and returns results for both:
  - the validator  -> list[(title, prior_share)]
  - the seeder     -> list[ResolvedAnswer] with entity ids

A `curated` prompt resolves its explicit `answers` titles to ingested entities
the same way (so curated and query share the exact prior-share math). A curated
title that doesn't match any ingested entity is reported as unresolved so the
author can fix the list (rather than silently dropping it).

DB access is read-only here.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..matching import best_fuzzy_match, normalize
from ..models import Alias, Entity
from ..priors import EntityFame, derive_prior_shares
from .schema import PromptDef, QuerySpec


@dataclass
class ResolvedAnswer:
    entity_id: str
    title: str
    type: str
    prior_share: float


@dataclass
class Resolution:
    answers: list[ResolvedAnswer]
    unresolved_titles: list[str]  # explicit titles that matched no entity

    def as_pairs(self) -> list[tuple[str, float]]:
        return [(a.title, a.prior_share) for a in self.answers]


def _query_entities(db: Session, types: list[str], spec: QuerySpec) -> list[Entity]:
    """Entities matching the query filters, ordered by popularity desc, capped."""
    stmt = select(Entity).where(Entity.type.in_(types))
    if spec.min_vote_count > 0:
        stmt = stmt.where(Entity.vote_count >= spec.min_vote_count)
    if spec.year_min is not None:
        stmt = stmt.where(Entity.year.isnot(None), Entity.year >= spec.year_min)
    if spec.year_max is not None:
        stmt = stmt.where(Entity.year.isnot(None), Entity.year <= spec.year_max)
    stmt = stmt.order_by(Entity.popularity.desc())

    rows = list(db.scalars(stmt))

    # Genre filters are applied in Python because genre_ids is a JSON list
    # (portable across SQLite/Postgres without JSON-operator differences).
    def genre_ok(ent: Entity) -> bool:
        gids = set(ent.genre_ids or [])
        if spec.genres_all and not set(spec.genres_all).issubset(gids):
            return False
        if spec.genres_any and not (set(spec.genres_any) & gids):
            return False
        return True

    filtered = [e for e in rows if genre_ok(e)]
    return filtered[: spec.limit]


def _resolve_titles(db: Session, titles: list[str], types: list[str]) -> tuple[list[Entity], list[str]]:
    """Resolve explicit titles to entities via normalize + alias + fuzzy.
    Returns (entities, unresolved_titles)."""
    if not titles:
        return [], []
    # Build candidate map once for the accepted types. When several entities
    # share a normalized title, map it to the highest-popularity one (so a
    # hand-seeded stub never shadows the real ingested row).
    norm_to_entity: dict[str, str] = {}
    ents_by_id: dict[str, Entity] = {}
    for ent in db.scalars(select(Entity).where(Entity.type.in_(types))):
        ents_by_id[ent.id] = ent
        cur = norm_to_entity.get(ent.normalized_title)
        if cur is None or ent.popularity > ents_by_id[cur].popularity:
            norm_to_entity[ent.normalized_title] = ent.id
    for alias in db.scalars(
        select(Alias).join(Entity, Alias.entity_id == Entity.id).where(Entity.type.in_(types))
    ):
        norm_to_entity.setdefault(alias.alias_normalized, alias.entity_id)

    resolved: list[Entity] = []
    unresolved: list[str] = []
    seen: set[str] = set()
    for title in titles:
        norm = normalize(title)
        eid = norm_to_entity.get(norm) or best_fuzzy_match(norm, norm_to_entity, 1)
        if eid and eid in ents_by_id and eid not in seen:
            resolved.append(ents_by_id[eid])
            seen.add(eid)
        elif eid and eid in ents_by_id:
            pass  # duplicate title, skip silently
        else:
            unresolved.append(title)
    return resolved, unresolved


def resolve(db: Session, prompt: PromptDef) -> Resolution:
    types = prompt.accepted_entity_types
    entities: list[Entity] = []
    unresolved: list[str] = []

    if prompt.kind == "curated":
        entities, unresolved = _resolve_titles(db, prompt.answers, types)
    else:
        spec = prompt.query or QuerySpec()
        entities = _query_entities(db, types, spec)
        # Merge in any explicit titles that aren't already in the query result.
        if spec.titles:
            extra, extra_unresolved = _resolve_titles(db, spec.titles, types)
            have = {e.id for e in entities}
            entities.extend(e for e in extra if e.id not in have)
            unresolved.extend(extra_unresolved)

    # De-duplicate by entity id, then by normalized title. When two entities
    # share a title (a hand-seeded stub vs. an ingested TMDB row, or a remake
    # colliding with its original), keep the higher-popularity one so scoring
    # uses real TMDB signal. Preserve first-seen order otherwise.
    by_id: set[str] = set()
    best_by_title: dict[str, Entity] = {}
    order: list[str] = []  # normalized titles in first-seen order
    for e in entities:
        if e.id in by_id:
            continue
        by_id.add(e.id)
        key = e.normalized_title
        if key not in best_by_title:
            best_by_title[key] = e
            order.append(key)
        elif e.popularity > best_by_title[key].popularity:
            best_by_title[key] = e
    unique = [best_by_title[k] for k in order]

    fames = [EntityFame(e.id, e.popularity, e.vote_count) for e in unique]
    shares = derive_prior_shares(fames)

    answers = [
        ResolvedAnswer(
            entity_id=e.id,
            title=e.canonical_title,
            type=e.type,
            prior_share=shares.get(e.id, 0.0),
        )
        for e in unique
    ]
    # Sort most-famous first for readable validator output.
    answers.sort(key=lambda a: a.prior_share, reverse=True)
    return Resolution(answers=answers, unresolved_titles=unresolved)


def resolve_answer_set(db: Session, prompt: PromptDef) -> list[tuple[str, float]]:
    """Convenience for the validator CLI (--resolve)."""
    return resolve(db, prompt).as_pairs()
