"""Answer normalization and matching (R14).

Pipeline:
  1. normalize (lowercase, strip punctuation, strip leading articles, collapse ws)
  2. exact match against canonical/alias normalized forms
  3. conservative fuzzy match (edit distance <= fuzzy_max_distance)
  4. otherwise unmatched -> caller logs to rejected_answers

Pure functions here so they can be unit-tested without a DB.
"""
from __future__ import annotations

import re
import unicodedata

_LEADING_ARTICLES = ("the ", "a ", "an ")
_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Canonical normalized form used for all matching and logging."""
    if text is None:
        return ""
    # Fold accents (café -> cafe) then lowercase.
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().strip()
    # Treat & as "and" before stripping punctuation.
    text = text.replace("&", " and ")
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    # Strip a single leading article.
    for art in _LEADING_ARTICLES:
        if text.startswith(art):
            text = text[len(art):]
            break
    return text.strip()


def levenshtein(a: str, b: str, max_distance: int | None = None) -> int:
    """Edit distance with optional early-exit when it provably exceeds max_distance."""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > (max_distance if max_distance is not None else len(a) + len(b)):
        return (max_distance or 0) + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        row_min = i
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            val = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            cur.append(val)
            row_min = min(row_min, val)
        if max_distance is not None and row_min > max_distance:
            return max_distance + 1
        prev = cur
    return prev[-1]


def best_fuzzy_match(
    query_norm: str, candidates: dict[str, str], max_distance: int
) -> str | None:
    """Return the entity_id of the closest candidate within max_distance.

    candidates: {normalized_form: entity_id}. Short strings are guarded: for very
    short queries we require exact matches (avoid turning "it" into "if"/"in").
    """
    if len(query_norm) < 4:
        return candidates.get(query_norm)
    best_id: str | None = None
    best_dist = max_distance + 1
    for norm, entity_id in candidates.items():
        if abs(len(norm) - len(query_norm)) > max_distance:
            continue
        d = levenshtein(query_norm, norm, max_distance)
        if d < best_dist:
            best_dist = d
            best_id = entity_id
            if d == 0:
                break
    return best_id if best_dist <= max_distance else None
