from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class DocumentVisual(Base):
    """
    Represents a visual element (image, figure, table, diagram, etc.)
    extracted from a PDF document.

    Phase 40: Visual extraction and metadata persistence.
    Phase 41 (NOT YET): Concept-relevant visual retrieval.
    """

    __tablename__ = "document_visuals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    page_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="1-based page number in the source PDF",
    )

    visual_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="unknown",
        comment="Controlled vocabulary: image, figure, diagram, chart, table, illustration, page_region, unknown",
    )

    asset_path: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Relative path under static/documents/{doc_id}/ or None for non-image visuals",
    )

    asset_url: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Public URL path e.g. /static/documents/{doc_id}/Image1.jpg",
    )

    caption: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Caption text associated with this visual, or None if absent",
    )

    # Bounding box stored as JSON [x0, y0, x1, y1] in PDF user-space units
    # nullable — not all visuals have reliable bbox info via pypdf
    bbox: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Bounding box as {x0, y0, x1, y1} in PDF page units, or None",
    )

    width: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Pixel width of extracted image (if available)",
    )

    height: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Pixel height of extracted image (if available)",
    )

    image_format: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Image format e.g. JPEG, PNG, JPEG2000 (if available)",
    )

    # Index within images on the same page (for images); -1 for non-image visuals
    image_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=-1,
    )

    analysis_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        comment="pending | complete | failed | skipped",
    )

    # Extra provider metadata as JSON dict
    metadata_json: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Extensible metadata for future phases",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    # Relationship back to Document
    document = relationship("Document", back_populates="visuals")

    def to_dict(self) -> dict:
        """Return a safe, frontend-friendly representation. Does NOT expose raw file paths."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "page_number": self.page_number,
            "visual_type": self.visual_type,
            "asset_url": self.asset_url,
            "caption": self.caption,
            "bbox": self.bbox,
            "width": self.width,
            "height": self.height,
            "image_format": self.image_format,
            "image_index": self.image_index,
            "analysis_status": self.analysis_status,
        }
