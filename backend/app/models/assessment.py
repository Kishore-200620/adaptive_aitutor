from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    session_id: Mapped[int] = mapped_column(
        ForeignKey("teaching_sessions.id"),
        index=True,
    )

    score: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    total_questions: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    strong_areas: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    weak_areas: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    recommendations: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    next_topic: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )