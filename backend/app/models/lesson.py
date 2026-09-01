from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        index=True,
    )

    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
    )

    topic: Mapped[str] = mapped_column(
        String(255),
    )

    objective: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    difficulty: Mapped[str] = mapped_column(
        String(50),
        default="beginner",
    )

    language: Mapped[str] = mapped_column(
        String(50),
        default="English",
    )

    duration_minutes: Mapped[int] = mapped_column(
        default=20,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="planned",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )