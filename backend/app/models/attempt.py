from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    session_id: Mapped[int] = mapped_column(
        ForeignKey("teaching_sessions.id"),
        index=True,
    )

    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id"),
        index=True,
    )

    question: Mapped[str] = mapped_column(
        Text,
    )

    student_answer: Mapped[str] = mapped_column(
        Text,
    )

    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    evaluation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    misconception: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )