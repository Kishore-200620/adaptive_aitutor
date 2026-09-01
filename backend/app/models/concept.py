from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class Concept(Base):
    __tablename__ = "concepts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    lesson_id: Mapped[int] = mapped_column(
        ForeignKey("lessons.id"),
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    order_index: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    difficulty: Mapped[str] = mapped_column(
        String(50),
        default="beginner",
    )

    mastery_score: Mapped[float] = mapped_column(
        default=0.0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )