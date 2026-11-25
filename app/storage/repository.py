"""Reading and writing the database."""

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.storage.db import Conversation, FailureSignal, Feedback, LiveJudgment, Turn, utc_now


class Repository:
    """All database access goes through here."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def save_turn(self, turn: Turn, signals: list[tuple[str, str]]) -> None:
        """Store a turn, its conversation and its failure signals in one transaction."""
        with Session(self.engine) as session, session.begin():
            key = (turn.user_id, turn.conversation_id)
            conversation = session.get(Conversation, key)
            if conversation is None:
                session.add(Conversation(user_id=key[0], conversation_id=key[1]))
            else:
                conversation.last_turn_at = utc_now()
            session.add(turn)
            session.flush()  # the turn must exist before rows that point to it
            session.add_all(
                FailureSignal(request_id=turn.request_id, signal=name, detail=detail)
                for name, detail in signals
            )

    def save_feedback(
        self, request_id: str, user_id: str, rating: str, comment: str | None
    ) -> Turn | None:
        """Store a rating. Returns None if this user has no such turn."""
        with Session(self.engine, expire_on_commit=False) as session, session.begin():
            turn = session.get(Turn, request_id)
            if turn is None or turn.user_id != user_id:
                return None
            session.merge(
                Feedback(
                    request_id=request_id, rating=rating, comment=comment, updated_at=utc_now()
                )
            )
            session.execute(
                delete(FailureSignal).where(
                    FailureSignal.request_id == request_id,
                    FailureSignal.signal == "negative_feedback",
                )
            )
            if rating == "down":
                session.add(FailureSignal(request_id=request_id, signal="negative_feedback"))
            return turn

    def save_judgment(self, judgment: LiveJudgment) -> None:
        """Store a faithfulness verdict, adding a failure signal if it says 'unsupported'."""
        with Session(self.engine) as session, session.begin():
            session.merge(judgment)
            if not judgment.faithful:
                detail = judgment.reason[:200]
                exists = session.scalar(
                    select(FailureSignal.id).where(
                        FailureSignal.request_id == judgment.request_id,
                        FailureSignal.signal == "low_faithfulness",
                    )
                )
                if exists is None:
                    session.add(
                        FailureSignal(
                            request_id=judgment.request_id,
                            signal="low_faithfulness",
                            detail=detail,
                        )
                    )

    def turns(self, source: str | None = None) -> Sequence[Turn]:
        """Stored turns, oldest first."""
        query = select(Turn).order_by(Turn.created_at, Turn.request_id)
        if source:
            query = query.where(Turn.source == source)
        with Session(self.engine) as session:
            return session.scalars(query).all()

    def signals(self) -> Sequence[FailureSignal]:
        """All failure signals."""
        with Session(self.engine) as session:
            return session.scalars(select(FailureSignal).order_by(FailureSignal.id)).all()

    def judged_request_ids(self, judge_model: str, rubric_version: str) -> set[str]:
        """Turns already judged with this judge and rubric."""
        query = select(LiveJudgment.request_id).where(
            LiveJudgment.judge_model == judge_model,
            LiveJudgment.rubric_version == rubric_version,
        )
        with Session(self.engine) as session:
            return set(session.scalars(query))
