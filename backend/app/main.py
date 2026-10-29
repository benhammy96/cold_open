"""FastAPI application wiring routes to the service layer.

Client-facing contract keeps answers/rarity server-side (R9, R10, R50).
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import service
from .config import get_settings
from .db import get_db
from .fame import emoji_grid, location_for_score
from .models import Entity, Player, Prompt, Run
from .ratelimit import allow
from .schemas import (
    AnswerRequest,
    AnswerResponse,
    CompleteResponse,
    DailyPublic,
    PromptPublic,
    RunResult,
    ShareCard,
    StartRunRequest,
    StartRunResponse,
    SubmissionResult,
)
from .tokens import sign_run, verify_run

settings = get_settings()
app = FastAPI(title="Cold Open API", version="0.1.0")

# Dev CORS: the Vite dev server also proxies /api, but allow direct calls too.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/daily", response_model=DailyPublic)
def get_daily(date: str | None = None, db: Session = Depends(get_db)) -> DailyPublic:
    date_str = date or service.today_str(settings)
    puzzle = service.get_puzzle(db, date_str, "daily")
    if puzzle is None:
        raise HTTPException(status_code=404, detail=f"No daily puzzle for {date_str}")
    prompts = service.load_prompts(db, puzzle.prompt_ids)
    return DailyPublic(
        date=puzzle.date,
        number=puzzle.number,
        mode="daily",
        prompt_count=len(prompts),
        seconds_per_prompt=settings.seconds_per_prompt,
        max_score=settings.max_daily_score,
        prompts=[PromptPublic(index=i, text=p.text) for i, p in enumerate(prompts)],
    )


@app.post("/api/runs", response_model=StartRunResponse)
def start_run(body: StartRunRequest, db: Session = Depends(get_db)) -> StartRunResponse:
    try:
        res = service.start_run(db, settings, body.anon_token, body.mode, body.date)
    except service.ServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    db.commit()
    return StartRunResponse(
        run_id=res.run.id,
        run_token=sign_run(res.run.id),
        mode=res.run.mode,
        date=res.run.puzzle_date,
        prompt_count=res.prompt_count,
        seconds_per_prompt=settings.seconds_per_prompt,
        current_index=res.run.current_index,
        already_completed=res.already_completed,
    )


def _run_from_token(db: Session, run_token: str) -> Run:
    run_id = verify_run(run_token)
    if run_id is None:
        raise HTTPException(status_code=401, detail="Invalid run token")
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.post("/api/runs/{run_id}/answer", response_model=AnswerResponse)
def submit_answer(run_id: str, body: AnswerRequest, request: Request, db: Session = Depends(get_db)) -> AnswerResponse:
    run = _run_from_token(db, body.run_token)
    if run.id != run_id:
        raise HTTPException(status_code=400, detail="Run id mismatch")

    # Rate limit per run and per client IP (R51).
    client_ip = request.client.host if request.client else "unknown"
    if not allow(f"run:{run.id}", settings.rate_limit_per_minute) or not allow(
        f"ip:{client_ip}", settings.rate_limit_per_minute * 4
    ):
        raise HTTPException(status_code=429, detail="Too many requests")

    try:
        outcome = service.submit_answer(
            db, settings, run, body.prompt_index, body.raw_input, body.timed_out
        )
    except service.ServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    db.commit()
    return AnswerResponse(
        valid=outcome.valid,
        tier=outcome.tier,
        tier_name=outcome.tier_name,
        points=outcome.points,
        canonical_title=outcome.canonical_title,
        total_score=outcome.total_score,
        next_index=outcome.next_index,
        done=outcome.done,
        reason=outcome.reason,
    )


@app.post("/api/runs/{run_id}/complete", response_model=CompleteResponse)
def complete_run(run_id: str, body: dict, db: Session = Depends(get_db)) -> CompleteResponse:
    run_token = body.get("run_token", "")
    run = _run_from_token(db, run_token)
    if run.id != run_id:
        raise HTTPException(status_code=400, detail="Run id mismatch")
    player = service.complete_run(db, settings, run)
    db.commit()
    loc = location_for_score(run.total_score)
    return CompleteResponse(
        total_score=run.total_score,
        streak=player.streak,
        freezes=player.freezes,
        location_name=loc.name,
    )


@app.get("/api/runs/{run_id}/result", response_model=RunResult)
def get_result(run_id: str, run_token: str, db: Session = Depends(get_db)) -> RunResult:
    run = _run_from_token(db, run_token)
    if run.id != run_id:
        raise HTTPException(status_code=400, detail="Run id mismatch")

    puzzle = service.get_puzzle(db, run.puzzle_date, run.mode)
    prompts = service.load_prompts(db, puzzle.prompt_ids) if puzzle else []
    subs = sorted(run.submissions, key=lambda s: s.prompt_index)

    tier_list: list[int] = []
    sub_results: list[SubmissionResult] = []
    for s in subs:
        prompt = prompts[s.prompt_index] if s.prompt_index < len(prompts) else db.get(Prompt, s.prompt_id)
        tier_list.append(s.tier)
        sub_results.append(
            SubmissionResult(
                prompt_index=s.prompt_index,
                prompt_text=prompt.text if prompt else "",
                raw_input=s.raw_input,
                valid=s.entity_id is not None,
                tier=s.tier,
                tier_name=_tier_name(s.tier),
                points=s.points,
                canonical_title=_entity_title(db, s.entity_id),
                global_percentage=service.global_percentage(db, s.prompt_id, s.entity_id),
            )
        )

    loc = location_for_score(run.total_score)
    player = db.get(Player, run.player_id)
    streak = player.streak if player else 0
    grid = emoji_grid(tier_list)
    share_text = (
        f"Cold Open #{puzzle.number if puzzle else 0}  {run.total_score}/{settings.max_daily_score}\n"
        f"{grid}\n{loc.emoji} {loc.name}\n🔥 Streak: {streak}"
    )
    share = ShareCard(
        number=puzzle.number if puzzle else 0,
        total_score=run.total_score,
        max_score=settings.max_daily_score,
        grid=grid,
        location_name=loc.name,
        location_emoji=loc.emoji,
        streak=streak,
        text=share_text,
    )
    return RunResult(
        run_id=run.id,
        mode=run.mode,
        date=run.puzzle_date,
        total_score=run.total_score,
        max_score=settings.max_daily_score,
        location_key=loc.key,
        location_name=loc.name,
        outfit=loc.outfit,
        streak=streak,
        status=run.status,
        submissions=sub_results,
        share=share,
    )


def _entity_title(db: Session, entity_id: str | None) -> str | None:
    if entity_id is None:
        return None
    ent = db.get(Entity, entity_id)
    return ent.canonical_title if ent else None


def _tier_name(tier: int) -> str:
    from .config import TIER_TABLE

    if tier == 0:
        return "No Match"
    for t in TIER_TABLE:
        if t[0] == tier:
            return t[1]
    return "No Match"
