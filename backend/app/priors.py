"""Prior-share derivation (Task 2).

Turns TMDB popularity + vote_count into a per-entity expected submission share
for a prompt. Shared by BOTH prompt kinds: query-backed prompts derive their
answer set from TMDB then call this; curated prompts attach a hand-reviewed
entity list and call the same function.

Why per-prompt and not global: rarity is relative to a category. "Titanic" is an
obvious answer to "Best Picture winner" but a deep cut to "movie set on a boat"
only if the boat set is full of more famous titles. So shares are distributed
WITHIN the candidate set.

Method (rank-power, scale-invariant):
  fame_i   = log1p(pop_i)*w_pop + log1p(votes_i)*w_vote
  norm_i   = (fame_i - min_fame) / (max_fame - min_fame)   # 0..1 within the set
  weight_i = (norm_i + floor) ** gamma   # gamma>1 rewards the famous end
  share_i  = weight_i / sum(weights)     # sums to 1 across the set
then cap any single share at PRIOR_MAX_SINGLE_SHARE and redistribute the excess
proportionally (§4 quality rule).

Why rank-power instead of softmax: softmax over a large candidate set spreads so
thin that even the most obvious answer scores as "rare", and over a tiny set it
becomes winner-take-all. Normalizing fame to 0..1 first makes the shape depend on
the fame SPREAD within the set, not on set size, so the famous end stays common
(Popcorn/Matinee) whether the prompt has 3 answers or 300, while the long tail
still reaches Deep Cut / Lost Reel.

Pure functions, DB-free, unit-tested.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import config


@dataclass(frozen=True)
class EntityFame:
    entity_id: str
    popularity: float
    vote_count: int


def fame_score(
    popularity: float,
    vote_count: int,
    pop_weight: float | None = None,
    vote_weight: float | None = None,
) -> float:
    pw = config.PRIOR_POP_WEIGHT if pop_weight is None else pop_weight
    vw = config.PRIOR_VOTE_WEIGHT if vote_weight is None else vote_weight
    return math.log1p(max(0.0, popularity)) * pw + math.log1p(max(0, vote_count)) * vw


def _cap_and_redistribute(shares: dict[str, float], cap: float) -> dict[str, float]:
    """Cap any share at `cap`, pushing the excess onto uncapped entries in
    proportion to their current share. Iterates until stable (at most a few
    passes) so the result still sums to ~1."""
    if not shares or cap >= 1.0:
        return shares
    shares = dict(shares)
    for _ in range(10):
        over = {k: v for k, v in shares.items() if v > cap + 1e-12}
        if not over:
            break
        excess = sum(v - cap for v in over.values())
        for k in over:
            shares[k] = cap
        receivers = {k: v for k, v in shares.items() if v < cap - 1e-12}
        pool = sum(receivers.values())
        if pool <= 0:
            # Everyone is at the cap; nowhere to put the excess. Leave as-is.
            break
        for k, v in receivers.items():
            shares[k] = v + excess * (v / pool)
    return shares


def derive_prior_shares(
    entities: list[EntityFame],
    gamma: float | None = None,
    floor: float | None = None,
    max_single_share: float | None = None,
) -> dict[str, float]:
    """Return {entity_id: prior_share}. Shares sum to ~1 across the set.

    Degenerate cases:
      - empty set -> {}
      - single entity -> {id: 1.0} (then capped if a cap applies)
      - all equal fame -> uniform shares
    """
    if not entities:
        return {}
    g = config.PRIOR_GAMMA if gamma is None else gamma
    fl = config.PRIOR_FLOOR if floor is None else floor
    cap = config.PRIOR_MAX_SINGLE_SHARE if max_single_share is None else max_single_share
    if len(entities) == 1:
        return _cap_and_redistribute({entities[0].entity_id: 1.0}, cap)

    fames = {e.entity_id: fame_score(e.popularity, e.vote_count) for e in entities}
    lo = min(fames.values())
    hi = max(fames.values())
    span = hi - lo
    if span <= 0:
        # All equal -> uniform.
        n = len(fames)
        return _cap_and_redistribute({k: 1.0 / n for k in fames}, cap)

    weights = {k: ((f - lo) / span + fl) ** g for k, f in fames.items()}
    total = sum(weights.values())
    shares = {k: w / total for k, w in weights.items()}
    return _cap_and_redistribute(shares, cap)
