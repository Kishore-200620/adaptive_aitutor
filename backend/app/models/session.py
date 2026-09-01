from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class TeachingSession(Base):
    __tablename__ = "teaching_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        index=True,
    )

    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id"),
        index=True,
    )

    current_concept_id: Mapped[int | None] = mapped_column(
        ForeignKey("concepts.id"),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="active",
    )

    current_step: Mapped[str] = mapped_column(
        String(50),
        default="explain",
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )