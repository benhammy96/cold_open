"""Prompt quality validator (Task 3, enforcing handoff §4 / R45).

Rules enforced:
  1. At least MIN_ANSWERS valid answers (warn below TARGET_ANSWERS).
  2. Answers span a popularity range: the derived prior shares must cover at
     least a few distinct rarity tiers, and must not all be clustered.
  3. Objective checkability: the prompt wording must not contain subjective
     superlatives ("best", "scariest", "funniest", ...).
  4. No plot spoilers: wording must avoid spoiler trigger phrases
     ("dies", "is actually", "turns out to be", "the killer is", ...).
  5. No single answer expected to exceed ~40% of submissions (dominance).

The validator separates ERRORS (block publishing) from WARNINGS (allow, but
flag). Count-below-target is a warning; count-below-minimum is an error.

Input: a PromptDef plus its resolved answer set as (title, prior_share) pairs.
Resolution (query -> entities) happens in Task 4; curated prompts pass their
titles with shares already derived. This keeps the validator independent of the
DB and unit-testable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .. import config
from ..scoring import tier_for_share
from .schema import PromptDef

MIN_ANSWERS = 40
TARGET_ANSWERS = 100

SUBJECTIVE_WORDS = [
    "best", "worst", "greatest", "scariest", "funniest", "saddest",
    "most underrated", "most overrated", "favorite", "favourite",
    "coolest", "dumbest", "stupidest", "weirdest", "cringiest",
    "most iconic", "perfect", "flawless",
]

SPOILER_PATTERNS = [
    r"\bdies\b", r"\bis dead\b", r"\bis actually\b", r"\bturns out\b",
    r"\bthe killer is\b", r"\bthe twist\b", r"\brevealed to be\b",
    r"\bsecretly\b", r"\bwas a ghost\b", r"\bis the father\b",
]


@dataclass
class ValidationResult:
    prompt_id: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# Proper-noun phrases that legitimately contain a subjective-looking word (e.g.
# the award name "Best Picture"). These are masked out before the wording check
# so an objective prompt isn't flagged for naming a real award/category.
ALLOWED_PHRASES = [
    "best picture", "best actor", "best actress", "best director",
    "best original", "best supporting", "best animated", "best adapted",
    "best film", "best documentary", "greatest showman",
]


def _check_wording(prompt: PromptDef, res: ValidationResult) -> None:
    low = prompt.text.lower()
    masked = low
    for phrase in ALLOWED_PHRASES:
        masked = masked.replace(phrase, " ")
    for word in SUBJECTIVE_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", masked):
            res.errors.append(
                f"subjective wording: '{word}' makes the prompt not objectively checkable"
            )
    for pat in SPOILER_PATTERNS:
        if re.search(pat, low):
            res.errors.append(f"possible spoiler in wording (matched /{pat}/)")
    if not low.startswith("name "):
        res.warnings.append("prompt text conventionally starts with 'Name a/an ...'")


def _check_answer_set(
    prompt: PromptDef,
    answers: list[tuple[str, float]],
    res: ValidationResult,
    min_answers: int,
) -> None:
    n = len(answers)
    if n < min_answers:
        res.errors.append(f"only {n} valid answers; need at least {min_answers}")
    elif n < TARGET_ANSWERS:
        res.warnings.append(f"{n} valid answers; target is {TARGET_ANSWERS}+")

    if n == 0:
        return

    shares = [s for _, s in answers]
    top = max(shares)

    # Dominance (§4): no single answer above the configured cap.
    if top > config.PRIOR_MAX_SINGLE_SHARE + 1e-6:
        dominant = next(t for t, s in answers if s == top)
        res.errors.append(
            f"answer '{dominant}' expected at {top:.0%} of submissions, "
            f"over the {config.PRIOR_MAX_SINGLE_SHARE:.0%} cap"
        )

    # Spread: require the set to cover a range of tiers, not cluster in one.
    tiers = {tier_for_share(s).tier for s in shares}
    if n >= MIN_ANSWERS and len(tiers) < 3:
        res.warnings.append(
            f"answers cluster in {len(tiers)} rarity tier(s); a good prompt spans a range"
        )

    # Duplicate-title guard inside the set.
    titles = [t.lower() for t, _ in answers]
    if len(set(titles)) != len(titles):
        res.errors.append("duplicate titles in the answer set")


def validate_prompt(
    prompt: PromptDef,
    answers: list[tuple[str, float]],
    min_answers: int = MIN_ANSWERS,
) -> ValidationResult:
    """Validate one prompt against its resolved (title, prior_share) answer set.

    min_answers defaults to the §4 hard rule (40). Callers running on the small
    fixture catalog may lower it; production should keep the default.
    """
    res = ValidationResult(prompt_id=prompt.id)
    if not prompt.text.strip():
        res.errors.append("empty prompt text")
    _check_wording(prompt, res)
    _check_answer_set(prompt, answers, res, min_answers)
    return res


def format_results(results: list[ValidationResult]) -> str:
    lines: list[str] = []
    n_err = sum(1 for r in results if r.errors)
    n_warn = sum(len(r.warnings) for r in results)
    for r in results:
        status = "FAIL" if r.errors else ("WARN" if r.warnings else "OK")
        lines.append(f"[{status}] {r.prompt_id}")
        for e in r.errors:
            lines.append(f"    error:   {e}")
        for w in r.warnings:
            lines.append(f"    warning: {w}")
    lines.append("")
    lines.append(
        f"{len(results)} prompts, {n_err} with errors, {n_warn} warnings total"
    )
    return "\n".join(lines)
