"""Runtime configuration.

Tier thresholds and rarity-blend parameters live in config, not code (R19, R18).
Everything here can be overridden via environment variables prefixed with COLDOPEN_.
"""
from __future__ import annotations

from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COLDOPEN_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./cold_open.db"

    # Daily reset timezone (R2). Puzzle id is the calendar date in this zone.
    daily_timezone: str = "America/New_York"

    # Gameplay (R1, R3, R20).
    prompts_per_daily: int = 7
    seconds_per_prompt: int = 25
    max_daily_score: int = 700

    # Rarity blend (R18, Q4 default). prior_weight = max(floor, start - total_submissions).
    prior_weight_start: int = 200
    prior_weight_floor: int = 20

    # Fuzzy matching: max normalized edit distance to accept (R14, conservative).
    fuzzy_max_distance: int = 1

    # Rate limiting (R51): max answer submissions per run per window.
    rate_limit_per_minute: int = 60

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.daily_timezone)


# Tier table (R19). share is the UPPER bound (exclusive) that maps to the tier,
# evaluated from rarest to most common. "Lost Reel" also covers never-submitted.
# Each entry: (tier_number, name, points, max_share_exclusive).
TIER_TABLE: list[tuple[int, str, int, float]] = [
    (6, "Lost Reel", 100, 0.001),     # < 0.1%  (or never submitted -> handled explicitly)
    (5, "Deep Cut", 80, 0.01),        # 0.1% - 1%
    (4, "Cult Classic", 60, 0.05),    # 1% - 5%
    (3, "Marquee", 40, 0.10),         # 5% - 10%
    (2, "Matinee", 25, 0.20),         # 10% - 20%
    (1, "Popcorn", 10, 1.0001),       # >= 20%
]

# Prior-share derivation (Task 2). Converts popularity + vote_count into an
# expected submission share per entity, computed WITHIN a prompt's answer set.
#   fame = log1p(popularity)*POP_WEIGHT + log1p(vote_count)*VOTE_WEIGHT
# normalized to 0..1 within the set, then a power curve distributes share.
PRIOR_POP_WEIGHT: float = 1.0
PRIOR_VOTE_WEIGHT: float = 1.2
# gamma > 1 concentrates share on the famous end (steeper popularity curve);
# gamma = 1 is linear in normalized fame. 5.0 keeps the most obvious answer in a
# large set at Popcorn/Matinee while the long tail reaches Deep Cut / Lost Reel,
# tuned against realistic power-law popularity data.
PRIOR_GAMMA: float = 5.0
# A small floor so the least-famous answer still gets a non-zero share (its
# weight is floor**gamma rather than 0), keeping it valid-but-rare.
PRIOR_FLOOR: float = 0.02
# §4 quality rule: cap any single answer's expected share. Excess is redistributed.
PRIOR_MAX_SINGLE_SHARE: float = 0.40

# Emoji per tier for the spoiler-free share grid (R28).
TIER_EMOJI: dict[int, str] = {
    0: "⬛",   # invalid / timed out
    1: "🟫",   # Popcorn
    2: "🟨",   # Matinee
    3: "🟧",   # Marquee
    4: "🟥",   # Cult Classic
    5: "🟦",   # Deep Cut
    6: "🟪",   # Lost Reel
}


@lru_cache
def get_settings() -> Settings:
    return Settings()
