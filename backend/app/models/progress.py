from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base

class StudentConceptProgress(Base):
    __tablename__ = "student_concept_progress"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        index=True,
    )
    
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id"),
        index=True,
    )
    
    status: Mapped[str] = mapped_column(
        String(50),
        default="not_started",
        index=True
    )
    
    mastery_snapshot: Mapped[float | None] = mapped_column(
        Float,
        nullable=True
    )
    
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    metadata_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )
