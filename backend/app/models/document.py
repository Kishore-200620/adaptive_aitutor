from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id"),
        index=True,
    )

    filename: Mapped[str] = mapped_column(
        String(255),
    )

    file_type: Mapped[str] = mapped_column(
        String(50),
    )

    file_path: Mapped[str] = mapped_column(
        Text,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="uploaded",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )