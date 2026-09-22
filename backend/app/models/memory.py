from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base


class LearnerMemory(Base):
    __tablename__ = "learner_memories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        index=True,
    )

    concept_id: Mapped[int | None] = mapped_column(
        ForeignKey("concepts.id"),
        nullable=True,
        index=True,
    )

    concept_key: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    memory_type: Mapped[str] = mapped_column(
        String(50),
        index=True,
    )

    content: Mapped[str] = mapped_column(
        Text,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        default=0.5,
    )

    evidence_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
    )

    source_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("session_events.id"),
        nullable=True,
    )

    first_observed_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
    )

    last_observed_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
    )

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    metadata_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
