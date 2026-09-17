"""
Document processing service.

Pipeline:
  1. Text extraction     (existing, unchanged)
  2. Chunking            (existing, unchanged)
  3. Embedding           (existing, unchanged)
  4. Chunk persistence   (existing, unchanged)
  5. Visual extraction   (Phase 40 addition — non-fatal if it fails)
  6. Visual persistence  (Phase 40 addition — non-fatal if it fails)
"""
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_visual import DocumentVisual
from app.rag.loaders import load_document
from app.rag.chunker import chunk_text
from app.rag.embeddings import generate_embedding
from app.rag.vector_store import save_chunks

logger = logging.getLogger("eduva.document_processor")


def process_document(
    db: Session,
    document_id: int,
) -> dict:
    """
    Process a document through the full pipeline.

    Returns a dict with status, chunks_created, visuals_extracted.
    The 'visuals_extracted' key will be 0 if visual extraction fails or
    is not applicable — the document will still be marked 'processed'.
    """
    document = db.get(Document, document_id)

    if document is None:
        raise ValueError("Document not found")

    document.status = "processing"
    db.commit()

    # -----------------------------------------------------------------------
    # Phase 1-4: Existing text pipeline (DO NOT MODIFY)
    # -----------------------------------------------------------------------
    try:
        text = load_document(document.file_path, document.id)

        chunks = chunk_text(text)

        embeddings = [
            generate_embedding(chunk)
            for chunk in chunks
        ]

        save_chunks(
            db=db,
            document_id=document.id,
            chunks=chunks,
            embeddings=embeddings,
        )

    except Exception:
        document.status = "failed"
        db.commit()
        raise

    # -----------------------------------------------------------------------
    # Phase 40: Visual extraction pipeline (non-fatal)
    # -----------------------------------------------------------------------
    visuals_extracted = 0
    visuals_failed = False

    if document.file_type == "pdf":
        try:
            visuals_extracted = _extract_and_persist_visuals(db, document)
        except Exception as exc:
            logger.error(
                f"[Phase40] Visual extraction failed for document {document.id}: {exc}"
            )
            visuals_failed = True
            # Visual failure is non-fatal — document is still usable
    else:
        logger.debug(
            f"[Phase40] Skipping visual extraction for non-PDF document {document.id} "
            f"(type={document.file_type})"
        )

    # -----------------------------------------------------------------------
    # Finalize
    # -----------------------------------------------------------------------
    document.status = "processed"
    db.commit()

    return {
        "document_id": document.id,
        "chunks_created": len(chunks),
        "status": document.status,
        "visuals_extracted": visuals_extracted,
        "visuals_failed": visuals_failed,
    }


def _extract_and_persist_visuals(db: Session, document: Document) -> int:
    """
    Run PDF visual extraction and save DocumentVisual records.

    Returns the number of visuals successfully persisted.
    Raises on unrecoverable errors (caller handles non-fatal logic).
    """
    from app.rag.visual_extractor import PDFVisualExtractor

    # Determine which images are already on disk for this document
    # to avoid duplicate asset creation
    asset_dir = Path(f"static/documents/{document.id}")
    existing_names: set[str] = set()
    if asset_dir.exists():
        existing_names = {p.name for p in asset_dir.iterdir() if p.is_file()}

    # Also check existing DocumentVisual records to avoid duplicate DB rows
    existing_asset_urls: set[str] = {
        v.asset_url for v in document.visuals if v.asset_url is not None
    }

    extractor = PDFVisualExtractor()
    extracted = extractor.extract_visuals(
        file_path=document.file_path,
        document_id=document.id,
        existing_image_names=existing_names,
    )

    saved_count = 0
    for visual in extracted:
        # Skip if we already have this URL persisted (idempotency guard)
        if visual.asset_url and visual.asset_url in existing_asset_urls:
            logger.debug(f"[Phase40] Skipping duplicate visual: {visual.asset_url}")
            continue

        try:
            db_visual = DocumentVisual(
                document_id=document.id,
                page_number=visual.page_number,
                visual_type=visual.visual_type,
                asset_path=visual.asset_path,
                asset_url=visual.asset_url,
                caption=visual.caption,
                bbox=None,  # pypdf does not expose per-image bbox reliably
                width=visual.width,
                height=visual.height,
                image_format=visual.image_format,
                image_index=visual.image_index,
                analysis_status="complete",
                metadata_json=visual.metadata or {},
            )
            db.add(db_visual)
            saved_count += 1
            if visual.asset_url:
                existing_asset_urls.add(visual.asset_url)
        except Exception as exc:
            logger.warning(f"[Phase40] Failed to persist visual record: {exc}")
            continue

    db.commit()
    logger.info(
        f"[Phase40] Persisted {saved_count}/{len(extracted)} visuals "
        f"for document {document.id}"
    )
    return saved_count