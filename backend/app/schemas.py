"""API request/response schemas. Note what is deliberately ABSENT from client-
facing payloads: valid answer lists and rarity data are never sent before
submission (R10)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class PromptPublic(BaseModel):
    index: int
    text: str  # text only — no answers, no accepted types leaked as hints


class DailyPublic(BaseModel):
    date: str
    number: int
    mode: str
    prompt_count: int
    seconds_per_prompt: int
    max_score: int
    prompts: list[PromptPublic]


class StartRunRequest(BaseModel):
    anon_token: str = Field(min_length=1, max_length=128)
    mode: str = "daily"
    date: str | None = None  # defaults to today (Eastern)


class StartRunResponse(BaseModel):
    run_id: str
    run_token: str  # per-run signed token (R50)
    mode: str
    date: str | None
    prompt_count: int
    seconds_per_prompt: int
    current_index: int
    already_completed: bool = False


class AnswerRequest(BaseModel):
    run_token: str
    prompt_index: int
    raw_input: str = Field(default="", max_length=200)
    timed_out: bool = False


class AnswerResponse(BaseModel):
    valid: bool
    tier: int
    tier_name: str
    points: int
    canonical_title: str | None
    total_score: int
    next_index: int
    done: bool
    reason: str | None = None  # e.g. "duplicate", "timeout", "no_match"


class SubmissionResult(BaseModel):
    prompt_index: int
    prompt_text: str
    raw_input: str
    valid: bool
    tier: int
    tier_name: str
    points: int
    canonical_title: str | None
    global_percentage: float  # live stat (R22)


class ShareCard(BaseModel):
    number: int
    total_score: int
    max_score: int
    grid: str
    location_name: str
    location_emoji: str
    streak: int
    text: str  # ready-to-copy multiline share text


class RunResult(BaseModel):
    run_id: str
    mode: str
    date: str | None
    total_score: int
    max_score: int
    location_key: str
    location_name: str
    outfit: str
    streak: int
    status: str
    submissions: list[SubmissionResult]
    share: ShareCard


class CompleteResponse(BaseModel):
    total_score: int
    streak: int
    freezes: int
    location_name: str
