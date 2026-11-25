"""Database tables (SQLAlchemy) and the connection."""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    """The current time in UTC."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base class for all tables."""


class Conversation(Base):
    """One conversation of one user."""

    __tablename__ = "conversations"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(default=utc_now)
    last_turn_at: Mapped[datetime] = mapped_column(default=utc_now)


class Turn(Base):
    """One customer message and the bot's reply. All text is redacted before it gets here."""

    __tablename__ = "turns"

    request_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, index=True)
    user_id: Mapped[str] = mapped_column(String(64))
    conversation_id: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(20))  # live | simulation | sample

    redacted_message: Mapped[str]
    retrieval_query: Mapped[str]
    retrieved: Mapped[list] = mapped_column(JSON)  # chunk ids, ranks and scores
    context: Mapped[dict] = mapped_column(JSON)  # article id -> text the model was shown
    top_score: Mapped[float | None]

    answer: Mapped[str]
    model_reply: Mapped[str | None]  # raw model output, redacted
    behavior: Mapped[str] = mapped_column(String(10))
    cited_article_ids: Mapped[list] = mapped_column(JSON)
    confidence: Mapped[float]
    escalate: Mapped[bool]
    escalation_reasons: Mapped[list] = mapped_column(JSON)
    guardrail_events: Mapped[list] = mapped_column(JSON)

    prompt_version: Mapped[str] = mapped_column(String(20))
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(80))
    variant: Mapped[str] = mapped_column(String(40))
    kb_fingerprint: Mapped[str] = mapped_column(String(32))

    latency_ms: Mapped[float]
    llm_latency_ms: Mapped[float | None]
    llm_wait_ms: Mapped[float | None]
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    llm_cached: Mapped[bool | None]


class Feedback(Base):
    """Thumbs up or down for one turn. A later rating replaces an earlier one."""

    __tablename__ = "feedback"

    request_id: Mapped[str] = mapped_column(ForeignKey("turns.request_id"), primary_key=True)
    rating: Mapped[str] = mapped_column(String(4))  # up | down
    comment: Mapped[str | None]  # redacted
    updated_at: Mapped[datetime] = mapped_column(default=utc_now)


class FailureSignal(Base):
    """A reason a turn may be worth a human look (DESIGN.md section 7)."""

    __tablename__ = "failure_signals"
    __table_args__ = (UniqueConstraint("request_id", "signal", "detail"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("turns.request_id"), index=True)
    signal: Mapped[str] = mapped_column(String(30), index=True)
    detail: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class LiveJudgment(Base):
    """The LLM judge's faithfulness verdict on a sampled turn."""

    __tablename__ = "live_judgments"

    request_id: Mapped[str] = mapped_column(ForeignKey("turns.request_id"), primary_key=True)
    judge_model: Mapped[str] = mapped_column(String(80), primary_key=True)
    rubric_version: Mapped[str] = mapped_column(String(20), primary_key=True)
    faithful: Mapped[bool]
    reason: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


def create_database(path: Path) -> Engine:
    """Open (or create) the SQLite database and make sure all tables exist.

    There is no migration tool yet: changing a table means deleting the local database.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", connect_args={"timeout": 30})

    @event.listens_for(engine, "connect")
    def configure_connection(connection, _record) -> None:
        cursor = connection.cursor()
        # WAL lets reports read while the API is writing.
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine
