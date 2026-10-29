"""ORM models mirroring the handoff data model (§8).

Entity types: movie, show, person, character. Prompts are typed via
accepted_entity_types (Q1 default). Submissions lock tier/points at submit
time (R17). answer_counts/rejected_answers drive observed rarity (R21) and the
admin review queue (R43).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    tmdb_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type: Mapped[str] = mapped_column(String, index=True)  # movie|show|person|character
    canonical_title: Mapped[str] = mapped_column(String, index=True)
    normalized_title: Mapped[str] = mapped_column(String, index=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    popularity: Mapped[float] = mapped_column(Float, default=0.0)
    vote_count: Mapped[int] = mapped_column(Integer, default=0)
    genre_ids: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String, default="seed")  # tmdb|fixture|seed

    aliases: Mapped[list["Alias"]] = relationship(back_populates="entity", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("tmdb_id", "type", name="uq_entity_tmdb"),)


class Alias(Base):
    __tablename__ = "aliases"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    alias_normalized: Mapped[str] = mapped_column(String, index=True)

    entity: Mapped[Entity] = relationship(back_populates="aliases")

    __table_args__ = (UniqueConstraint("entity_id", "alias_normalized", name="uq_alias"),)


class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    text: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String, default="general")
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String, default="published")  # draft|published
    tags: Mapped[list] = mapped_column(JSON, default=list)
    # Q1 default: which entity types are valid answers for this prompt.
    accepted_entity_types: Mapped[list] = mapped_column(JSON, default=lambda: ["movie", "show"])

    answers: Mapped[list["PromptAnswer"]] = relationship(back_populates="prompt", cascade="all, delete-orphan")


class PromptAnswer(Base):
    __tablename__ = "prompt_answers"

    prompt_id: Mapped[str] = mapped_column(ForeignKey("prompts.id"), primary_key=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), primary_key=True)
    prior_share: Mapped[float] = mapped_column(Float, default=0.0)

    prompt: Mapped[Prompt] = relationship(back_populates="answers")
    entity: Mapped[Entity] = relationship()


class Puzzle(Base):
    __tablename__ = "puzzles"

    date: Mapped[str] = mapped_column(String, primary_key=True)  # YYYY-MM-DD (Eastern)
    mode: Mapped[str] = mapped_column(String, default="daily", primary_key=True)
    prompt_ids: Mapped[list] = mapped_column(JSON)  # ordered list of 7 prompt ids
    number: Mapped[int] = mapped_column(Integer, default=1)  # "Cold Open #N"


class Player(Base):
    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    anon_token: Mapped[str] = mapped_column(String, unique=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    last_completed_date: Mapped[str | None] = mapped_column(String, nullable=True)
    freezes: Mapped[int] = mapped_column(Integer, default=0)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), index=True)
    puzzle_date: Mapped[str | None] = mapped_column(String, nullable=True)
    pack_id: Mapped[str | None] = mapped_column(String, nullable=True)
    mode: Mapped[str] = mapped_column(String, default="daily")
    total_score: Mapped[int] = mapped_column(Integer, default=0)
    current_index: Mapped[int] = mapped_column(Integer, default=0)  # next prompt to answer
    status: Mapped[str] = mapped_column(String, default="in_progress")  # in_progress|complete
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    submissions: Mapped[list["Submission"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    prompt_id: Mapped[str] = mapped_column(ForeignKey("prompts.id"))
    prompt_index: Mapped[int] = mapped_column(Integer)
    raw_input: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
    tier: Mapped[int] = mapped_column(Integer, default=0)
    points: Mapped[int] = mapped_column(Integer, default=0)
    share_at_submit: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    run: Mapped["Run"] = relationship(back_populates="submissions")


class AnswerCount(Base):
    __tablename__ = "answer_counts"

    prompt_id: Mapped[str] = mapped_column(ForeignKey("prompts.id"), primary_key=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class PromptTotal(Base):
    """Total valid submissions per prompt, denominator for observed share (R18)."""

    __tablename__ = "prompt_totals"

    prompt_id: Mapped[str] = mapped_column(ForeignKey("prompts.id"), primary_key=True)
    total: Mapped[int] = mapped_column(Integer, default=0)


class RejectedAnswer(Base):
    __tablename__ = "rejected_answers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    prompt_id: Mapped[str] = mapped_column(ForeignKey("prompts.id"), index=True)
    normalized_input: Mapped[str] = mapped_column(String, index=True)
    count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String, default="pending")  # pending|promoted|dismissed

    __table_args__ = (UniqueConstraint("prompt_id", "normalized_input", name="uq_rejected"),)
