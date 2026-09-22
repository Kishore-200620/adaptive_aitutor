from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class SessionEvent(Base):
    __tablename__ = "session_events"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence_number", name="uq_session_sequence"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    session_id: Mapped[int] = mapped_column(
        ForeignKey("teaching_sessions.id"),
        index=True,
    )

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        index=True,
    )

    lesson_id: Mapped[int | None] = mapped_column(
        ForeignKey("lessons.id"),
        nullable=True,
        index=True,
    )

    concept_id: Mapped[int | None] = mapped_column(
        ForeignKey("concepts.id"),
        nullable=True,
        index=True,
    )

    sequence_number: Mapped[int] = mapped_column(
        Integer,
    )

    event_type: Mapped[str] = mapped_column(
        String(50),
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(20),
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True,
    )
