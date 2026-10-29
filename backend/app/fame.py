"""Fame-ladder locations/ranks (R33, R34) and share-card emoji grid (R28)."""
from __future__ import annotations

from dataclasses import dataclass

from .config import TIER_EMOJI


@dataclass(frozen=True)
class Location:
    key: str
    name: str
    emoji: str
    min_score: int
    outfit: str


# Ordered low -> high. 700 is its own band (Walk of Fame).
LOCATIONS: list[Location] = [
    Location("bus_stop", "Bus Stop", "🚏", 0, "hoodie_duffel"),
    Location("audition_line", "Audition Line", "🎬", 100, "hoodie"),
    Location("backlot", "Backlot", "🎞️", 200, "jacket"),
    Location("trailer", "Your Own Trailer", "🚐", 300, "jacket"),
    Location("red_carpet", "Premiere Red Carpet", "📍", 400, "suit"),
    Location("awards_stage", "Awards Stage", "🏆", 500, "suit"),
    Location("mansion", "Hollywood Hills Mansion", "🏔️", 600, "tux"),
    Location("walk_of_fame", "Walk of Fame", "⭐", 700, "tux_star"),
]


def location_for_score(score: int) -> Location:
    """Highest location whose min_score the score meets or exceeds."""
    result = LOCATIONS[0]
    for loc in LOCATIONS:
        if score >= loc.min_score:
            result = loc
    return result


def emoji_grid(tiers: list[int]) -> str:
    """Spoiler-free per-prompt emoji row colored by tier (R28). 0 => invalid."""
    return "".join(TIER_EMOJI.get(t, TIER_EMOJI[0]) for t in tiers)
