from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(100))

    education_level: Mapped[str] = mapped_column(
        String(50),
        default="beginner",
    )

    preferred_language: Mapped[str] = mapped_column(
        String(50),
        default="English",
    )

    learning_goal: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    teaching_style: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )