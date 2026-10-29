"""Rarity blend and tier mapping (R18, R19).

Pure functions, DB-free, so the scoring math is unit-testable in isolation.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import TIER_TABLE, Settings


@dataclass(frozen=True)
class TierResult:
    tier: int
    name: str
    points: int
    share: float


def prior_weight(total_submissions: int, settings: Settings) -> int:
    """Linear decay from start down to floor as real data accumulates (Q4 default)."""
    return max(settings.prior_weight_floor, settings.prior_weight_start - total_submissions)


def rarity_share(
    prior_share: float,
    observed_count: int,
    total_submissions: int,
    settings: Settings,
) -> float:
    """Bayesian blend of prior and observed share (R18).

        share = (w * prior_share + observed_count) / (w + total_submissions)

    At total=0 this returns prior_share exactly, so cold-start players are scored
    purely on the TMDB-derived prior.
    """
    w = prior_weight(total_submissions, settings)
    denom = w + total_submissions
    if denom <= 0:
        return prior_share
    return (w * prior_share + observed_count) / denom


def tier_for_share(share: float, never_submitted: bool = False) -> TierResult:
    """Map a rarity share to a tier using the configurable TIER_TABLE (R19).

    A valid-but-never-submitted answer is a Lost Reel regardless of prior (R19).
    """
    if never_submitted:
        t = TIER_TABLE[0]  # Lost Reel
        return TierResult(tier=t[0], name=t[1], points=t[2], share=share)
    # TIER_TABLE is ordered rarest -> most common; first upper-bound the share
    # falls under wins.
    for tier_num, name, points, max_share in TIER_TABLE:
        if share < max_share:
            return TierResult(tier=tier_num, name=name, points=points, share=share)
    # Fallback (shouldn't hit because Popcorn bound is > 1).
    t = TIER_TABLE[-1]
    return TierResult(tier=t[0], name=t[1], points=t[2], share=share)


def score_answer(
    prior_share: float,
    observed_count: int,
    total_submissions: int,
    settings: Settings,
) -> TierResult:
    """Full scoring for one valid answer: blend then map to tier.

    observed_count is the count BEFORE this submission is recorded, so the score
    reflects state at submit time and is then locked (R17).
    """
    never = observed_count == 0 and total_submissions >= 0 and prior_share <= 0.0
    share = rarity_share(prior_share, observed_count, total_submissions, settings)
    # If it has genuinely never been submitted AND has no meaningful prior, Lost Reel.
    if observed_count == 0 and prior_share <= 1e-9:
        return tier_for_share(share, never_submitted=True)
    return tier_for_share(share)
