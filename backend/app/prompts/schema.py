"""Prompt authoring format (Task 3).

Two prompt kinds:
  - curated: an explicit, hand-reviewed list of answer titles.
  - query:   answer set derived from TMDB-style criteria (resolved in Task 4).

A prompts file is YAML:

    prompts:
      - id: best-picture-winners
        text: "Name a movie that won the Best Picture Oscar"
        kind: curated
        accepted_entity_types: [movie]
        tags: [oscars]
        answers: ["Titanic", "Parasite", ...]

      - id: nolan-films
        text: "Name a film directed by Christopher Nolan"
        kind: query
        accepted_entity_types: [movie]
        query:
          genres_any: [878, 53]   # optional TMDB genre id filters (OR)
          genres_all: []          # optional (AND)
          year_min: 1998
          year_max: 2024
          min_vote_count: 200
          titles: ["Inception", ...]   # optional explicit members merged in
          limit: 150

This module only parses and type-checks structure. Quality rules live in
validator.py; resolving a query into entities lives in resolver.py (Task 4).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import yaml

VALID_ENTITY_TYPES = {"movie", "show", "person", "character"}


class PromptParseError(ValueError):
    pass


@dataclass
class QuerySpec:
    genres_any: list[int] = field(default_factory=list)
    genres_all: list[int] = field(default_factory=list)
    year_min: int | None = None
    year_max: int | None = None
    min_vote_count: int = 0
    titles: list[str] = field(default_factory=list)  # explicit members to merge in
    limit: int = 200


@dataclass
class PromptDef:
    id: str
    text: str
    kind: str  # curated|query
    accepted_entity_types: list[str]
    tags: list[str] = field(default_factory=list)
    difficulty: int = 1
    # curated:
    answers: list[str] = field(default_factory=list)
    # query:
    query: QuerySpec | None = None


def _require(d: dict, key: str, ctx: str):
    if key not in d:
        raise PromptParseError(f"{ctx}: missing required field '{key}'")
    return d[key]


def parse_prompt(raw: dict, index: int) -> PromptDef:
    ctx = f"prompt[{index}]"
    if not isinstance(raw, dict):
        raise PromptParseError(f"{ctx}: expected a mapping, got {type(raw).__name__}")

    pid = str(_require(raw, "id", ctx))
    text = str(_require(raw, "text", ctx))
    kind = str(_require(raw, "kind", ctx))
    if kind not in ("curated", "query"):
        raise PromptParseError(f"{ctx} ({pid}): kind must be 'curated' or 'query', got '{kind}'")

    types = _require(raw, "accepted_entity_types", f"{ctx} ({pid})")
    if not isinstance(types, list) or not types:
        raise PromptParseError(f"{ctx} ({pid}): accepted_entity_types must be a non-empty list")
    bad = [t for t in types if t not in VALID_ENTITY_TYPES]
    if bad:
        raise PromptParseError(f"{ctx} ({pid}): invalid entity types {bad}")

    tags = list(raw.get("tags", []) or [])
    difficulty = int(raw.get("difficulty", 1))

    if kind == "curated":
        answers = _require(raw, "answers", f"{ctx} ({pid})")
        if not isinstance(answers, list):
            raise PromptParseError(f"{ctx} ({pid}): answers must be a list")
        answers = [str(a).strip() for a in answers if str(a).strip()]
        return PromptDef(
            id=pid, text=text, kind=kind, accepted_entity_types=list(types),
            tags=tags, difficulty=difficulty, answers=answers,
        )

    # query
    q = raw.get("query") or {}
    if not isinstance(q, dict):
        raise PromptParseError(f"{ctx} ({pid}): query must be a mapping")
    spec = QuerySpec(
        genres_any=[int(g) for g in q.get("genres_any", []) or []],
        genres_all=[int(g) for g in q.get("genres_all", []) or []],
        year_min=q.get("year_min"),
        year_max=q.get("year_max"),
        min_vote_count=int(q.get("min_vote_count", 0) or 0),
        titles=[str(t).strip() for t in (q.get("titles", []) or []) if str(t).strip()],
        limit=int(q.get("limit", 200) or 200),
    )
    return PromptDef(
        id=pid, text=text, kind=kind, accepted_entity_types=list(types),
        tags=tags, difficulty=difficulty, query=spec,
    )


def parse_prompts_yaml(text: str) -> list[PromptDef]:
    data = yaml.safe_load(text)
    if not isinstance(data, dict) or "prompts" not in data:
        raise PromptParseError("top-level 'prompts' list is required")
    items = data["prompts"]
    if not isinstance(items, list) or not items:
        raise PromptParseError("'prompts' must be a non-empty list")
    out = [parse_prompt(p, i) for i, p in enumerate(items)]
    # Duplicate id guard.
    seen: set[str] = set()
    for p in out:
        if p.id in seen:
            raise PromptParseError(f"duplicate prompt id '{p.id}'")
        seen.add(p.id)
    return out


def load_prompts_file(path: str) -> list[PromptDef]:
    with open(path, encoding="utf-8") as f:
        return parse_prompts_yaml(f.read())
