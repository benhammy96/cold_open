"""Run lifecycle + answer handling service.

Ties together matching (R14), scoring (R17-R21), run state (R7, R8, R13),
streaks (R26, R27), and share-card data (R28, R34). The API layer stays thin.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import matching, scoring
from .config import Settings
from .fame import emoji_grid, location_for_score
from .models import (
    Alias,
    AnswerCount,
    Entity,
    Player,
    Prompt,
    PromptAnswer,
    PromptTotal,
    Puzzle,
    RejectedAnswer,
    Run,
    Submission,
)


class ServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def today_str(settings: Settings) -> str:
    return datetime.now(settings.tz).date().isoformat()


# ---------- players ----------

def get_or_create_player(db: Session, anon_token: str) -> Player:
    player = db.scalar(select(Player).where(Player.anon_token == anon_token))
    if player is None:
        player = Player(anon_token=anon_token, streak=0, freezes=0)
        db.add(player)
        db.flush()
    return player


# ---------- puzzles ----------

def get_puzzle(db: Session, date_str: str, mode: str = "daily") -> Puzzle | None:
    return db.scalar(
        select(Puzzle).where(Puzzle.date == date_str, Puzzle.mode == mode)
    )


def load_prompts(db: Session, prompt_ids: list[str]) -> list[Prompt]:
    found = {p.id: p for p in db.scalars(select(Prompt).where(Prompt.id.in_(prompt_ids)))}
    return [found[pid] for pid in prompt_ids if pid in found]


# ---------- run lifecycle ----------

@dataclass
class StartResult:
    run: Run
    already_completed: bool
    prompt_count: int


def start_run(db: Session, settings: Settings, anon_token: str, mode: str, date_str: str | None) -> StartResult:
    player = get_or_create_player(db, anon_token)
    date_str = date_str or today_str(settings)

    puzzle = get_puzzle(db, date_str, mode)
    if puzzle is None:
        raise ServiceError(f"No {mode} puzzle for {date_str}", status_code=404)

    # One attempt per player per daily date (R8). Return the existing run if any.
    existing = db.scalar(
        select(Run).where(
            Run.player_id == player.id,
            Run.puzzle_date == date_str,
            Run.mode == mode,
        )
    )
    if existing is not None:
        return StartResult(
            run=existing,
            already_completed=existing.status == "complete",
            prompt_count=len(puzzle.prompt_ids),
        )

    run = Run(
        player_id=player.id,
        puzzle_date=date_str,
        mode=mode,
        current_index=0,
        status="in_progress",
    )
    db.add(run)
    db.flush()
    return StartResult(run=run, already_completed=False, prompt_count=len(puzzle.prompt_ids))


def _candidate_map(db: Session, prompt: Prompt) -> tuple[dict[str, str], dict[str, PromptAnswer]]:
    """Build {normalized_form: entity_id} for all valid answers of a prompt, plus
    an entity_id -> PromptAnswer index. Only entities whose type is accepted (R16).
    """
    answers = db.scalars(
        select(PromptAnswer).where(PromptAnswer.prompt_id == prompt.id)
    ).all()
    by_entity: dict[str, PromptAnswer] = {}
    norm_to_entity: dict[str, str] = {}
    accepted = set(prompt.accepted_entity_types or [])
    for pa in answers:
        ent = pa.entity
        if accepted and ent.type not in accepted:
            continue
        by_entity[ent.id] = pa
        norm_to_entity[ent.normalized_title] = ent.id
        for alias in ent.aliases:
            norm_to_entity[alias.alias_normalized] = ent.id
    return norm_to_entity, by_entity


@dataclass
class AnswerOutcome:
    valid: bool
    tier: int
    tier_name: str
    points: int
    canonical_title: str | None
    total_score: int
    next_index: int
    done: bool
    reason: str | None = None


def submit_answer(
    db: Session,
    settings: Settings,
    run: Run,
    prompt_index: int,
    raw_input: str,
    timed_out: bool,
) -> AnswerOutcome:
    if run.status == "complete":
        raise ServiceError("Run already complete", status_code=409)

    puzzle = get_puzzle(db, run.puzzle_date, run.mode)
    if puzzle is None:
        raise ServiceError("Puzzle missing", status_code=404)
    prompt_ids = puzzle.prompt_ids

    # Enforce sequential answering at the run's current index (R7: in-progress
    # prompt forfeited on resume; client can't jump around).
    if prompt_index != run.current_index:
        raise ServiceError(
            f"Expected prompt_index {run.current_index}, got {prompt_index}", status_code=409
        )
    if prompt_index >= len(prompt_ids):
        raise ServiceError("Prompt index out of range", status_code=400)

    prompt = db.get(Prompt, prompt_ids[prompt_index])
    normalized = matching.normalize(raw_input)

    # Default: invalid / zero.
    outcome_entity_id: str | None = None
    tier = 0
    tier_name = "No Match"
    points = 0
    share_at_submit = 0.0
    canonical_title: str | None = None
    reason: str | None = None

    if timed_out or not normalized:
        reason = "timeout" if timed_out else "empty"
    else:
        norm_to_entity, by_entity = _candidate_map(db, prompt)
        entity_id = norm_to_entity.get(normalized)
        if entity_id is None:
            entity_id = matching.best_fuzzy_match(
                normalized, norm_to_entity, settings.fuzzy_max_distance
            )

        if entity_id is None:
            reason = "no_match"
            _log_rejected(db, prompt.id, normalized)
        elif _already_used(db, run.id, entity_id):
            # Same canonical entity twice in one run -> invalid (R13).
            reason = "duplicate"
        else:
            pa = by_entity[entity_id]
            total = _prompt_total(db, prompt.id)
            observed = _answer_count(db, prompt.id, entity_id)
            result = scoring.score_answer(pa.prior_share, observed, total, settings)
            outcome_entity_id = entity_id
            tier = result.tier
            tier_name = result.name
            points = result.points
            share_at_submit = result.share
            canonical_title = pa.entity.canonical_title
            # Record observed data AFTER scoring so this submission doesn't score
            # against itself (R17/R21).
            _increment_counts(db, prompt.id, entity_id)

    sub = Submission(
        run_id=run.id,
        prompt_id=prompt.id,
        prompt_index=prompt_index,
        raw_input=raw_input[:200],
        entity_id=outcome_entity_id,
        tier=tier,
        points=points,
        share_at_submit=share_at_submit,
    )
    db.add(sub)

    run.total_score += points
    run.current_index += 1
    done = run.current_index >= len(prompt_ids)
    db.flush()

    return AnswerOutcome(
        valid=outcome_entity_id is not None,
        tier=tier,
        tier_name=tier_name if outcome_entity_id is not None else "No Match",
        points=points,
        canonical_title=canonical_title,
        total_score=run.total_score,
        next_index=run.current_index,
        done=done,
        reason=reason,
    )


def complete_run(db: Session, settings: Settings, run: Run) -> Player:
    if run.status != "complete":
        run.status = "complete"
        run.completed_at = datetime.now(timezone.utc)
        if run.mode == "daily":
            _update_streak(db, settings, run)
        db.flush()
    return db.get(Player, run.player_id)


# ---------- streaks (R26, R27) ----------

def _update_streak(db: Session, settings: Settings, run: Run) -> None:
    player = db.get(Player, run.player_id)
    completed = date.fromisoformat(run.puzzle_date)
    last = date.fromisoformat(player.last_completed_date) if player.last_completed_date else None

    if last == completed:
        return  # already counted this date
    if last == completed - timedelta(days=1):
        player.streak += 1
    elif last is not None and completed > last + timedelta(days=1):
        # Missed one or more days. Spend a freeze to bridge a single-day gap.
        if completed == last + timedelta(days=2) and player.freezes > 0:
            player.freezes -= 1
            player.streak += 1
        else:
            player.streak = 1
    else:
        player.streak = 1

    player.last_completed_date = run.puzzle_date
    # One freeze token per completed 7-day streak (R26).
    if player.streak > 0 and player.streak % 7 == 0:
        player.freezes += 1


# ---------- observed-rarity bookkeeping ----------

def _answer_count(db: Session, prompt_id: str, entity_id: str) -> int:
    row = db.get(AnswerCount, (prompt_id, entity_id))
    return row.count if row else 0


def _prompt_total(db: Session, prompt_id: str) -> int:
    row = db.get(PromptTotal, prompt_id)
    return row.total if row else 0


def _increment_counts(db: Session, prompt_id: str, entity_id: str) -> None:
    ac = db.get(AnswerCount, (prompt_id, entity_id))
    if ac is None:
        ac = AnswerCount(prompt_id=prompt_id, entity_id=entity_id, count=0)
        db.add(ac)
    ac.count += 1
    pt = db.get(PromptTotal, prompt_id)
    if pt is None:
        pt = PromptTotal(prompt_id=prompt_id, total=0)
        db.add(pt)
    pt.total += 1


def _already_used(db: Session, run_id: str, entity_id: str) -> bool:
    return db.scalar(
        select(Submission.id).where(
            Submission.run_id == run_id, Submission.entity_id == entity_id
        )
    ) is not None


def _log_rejected(db: Session, prompt_id: str, normalized: str) -> None:
    row = db.scalar(
        select(RejectedAnswer).where(
            RejectedAnswer.prompt_id == prompt_id,
            RejectedAnswer.normalized_input == normalized,
        )
    )
    if row is None:
        db.add(RejectedAnswer(prompt_id=prompt_id, normalized_input=normalized, count=1))
    else:
        row.count += 1


# ---------- results / share card ----------

def global_percentage(db: Session, prompt_id: str, entity_id: str | None) -> float:
    if entity_id is None:
        return 0.0
    total = _prompt_total(db, prompt_id)
    if total <= 0:
        return 0.0
    return round(100.0 * _answer_count(db, prompt_id, entity_id) / total, 1)
