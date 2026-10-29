import pytest

from app.prompts.schema import PromptParseError, parse_prompts_yaml
from app.prompts.validator import MIN_ANSWERS, validate_prompt


CURATED_YAML = """
prompts:
  - id: best-picture
    text: "Name a movie that won the Best Picture Oscar"
    kind: curated
    accepted_entity_types: [movie]
    tags: [oscars]
    answers: [Titanic, Parasite, Gladiator]
"""

QUERY_YAML = """
prompts:
  - id: nolan
    text: "Name a film directed by Christopher Nolan"
    kind: query
    accepted_entity_types: [movie]
    query:
      genres_any: [878, 53]
      year_min: 1998
      min_vote_count: 200
      limit: 120
"""


def test_parse_curated():
    [p] = parse_prompts_yaml(CURATED_YAML)
    assert p.kind == "curated"
    assert p.answers == ["Titanic", "Parasite", "Gladiator"]
    assert p.accepted_entity_types == ["movie"]


def test_parse_query():
    [p] = parse_prompts_yaml(QUERY_YAML)
    assert p.kind == "query"
    assert p.query is not None
    assert p.query.genres_any == [878, 53]
    assert p.query.year_min == 1998
    assert p.query.limit == 120


def test_bad_kind_rejected():
    with pytest.raises(PromptParseError):
        parse_prompts_yaml(
            "prompts:\n  - id: x\n    text: t\n    kind: bogus\n    accepted_entity_types: [movie]\n"
        )


def test_bad_entity_type_rejected():
    with pytest.raises(PromptParseError):
        parse_prompts_yaml(
            "prompts:\n  - id: x\n    text: t\n    kind: curated\n    accepted_entity_types: [banana]\n    answers: [a]\n"
        )


def test_duplicate_ids_rejected():
    y = (
        "prompts:\n"
        "  - {id: x, text: Name a movie, kind: curated, accepted_entity_types: [movie], answers: [a]}\n"
        "  - {id: x, text: Name a show, kind: curated, accepted_entity_types: [show], answers: [b]}\n"
    )
    with pytest.raises(PromptParseError):
        parse_prompts_yaml(y)


# ---- validator ----

def _answers(n: int, top: float = 0.12):
    # n answers spanning tiers: one common, rest tapering into the tail.
    out = [("Famous Pick", top)]
    for i in range(1, n):
        out.append((f"Title {i}", max(0.0005, top * (0.9 ** i))))
    return out


def _prompt(text="Name a movie set in space"):
    from app.prompts.schema import PromptDef

    return PromptDef(id="p", text=text, kind="curated", accepted_entity_types=["movie"])


def test_valid_prompt_passes():
    r = validate_prompt(_prompt(), _answers(MIN_ANSWERS + 20))
    assert r.ok, r.errors


def test_too_few_answers_errors():
    r = validate_prompt(_prompt(), _answers(10))
    assert not r.ok
    assert any("at least" in e for e in r.errors)


def test_subjective_wording_errors():
    r = validate_prompt(_prompt("Name the best movie ever made"), _answers(MIN_ANSWERS + 1))
    assert not r.ok
    assert any("subjective" in e for e in r.errors)


def test_award_name_is_not_subjective():
    # "Best Picture" is an award name, not a subjective judgment.
    r = validate_prompt(
        _prompt("Name a movie that won the Best Picture Oscar"), _answers(MIN_ANSWERS + 1)
    )
    assert r.ok, r.errors


def test_spoiler_wording_errors():
    r = validate_prompt(
        _prompt("Name a movie where the main character dies"), _answers(MIN_ANSWERS + 1)
    )
    assert not r.ok
    assert any("spoiler" in e for e in r.errors)


def test_dominant_answer_errors():
    ans = [("Overwhelming", 0.65)] + [(f"t{i}", 0.001) for i in range(MIN_ANSWERS)]
    r = validate_prompt(_prompt(), ans)
    assert not r.ok
    assert any("over the" in e for e in r.errors)


def test_clustered_answers_warns():
    ans = [(f"t{i}", 0.02) for i in range(MIN_ANSWERS + 5)]  # all Cult Classic tier
    r = validate_prompt(_prompt(), ans)
    assert r.ok  # not an error
    assert any("cluster" in w for w in r.warnings)


def test_count_below_target_warns():
    r = validate_prompt(_prompt(), _answers(MIN_ANSWERS + 5))
    assert r.ok
    assert any("target" in w for w in r.warnings)
