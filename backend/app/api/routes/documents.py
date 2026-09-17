from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.document import Document
from app.models.document_visual import DocumentVisual
from app.models.student import Student
from app.services.document_processor import process_document


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


UPLOAD_DIR = Path("storage/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    student_id: int = Form(...),
    db: Session = Depends(get_db),
):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(
            status_code=400,
            detail=f"Student {student_id} not found"
        )
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported",
        )

    extension = Path(file.filename or "").suffix.lower()

    if extension != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported",
        )

    filename = f"{uuid4()}.pdf"
    file_path = UPLOAD_DIR / filename

    contents = await file.read()

    with open(file_path, "wb") as output_file:
        output_file.write(contents)

    document = Document(
        student_id=student_id,
        filename=file.filename or "document.pdf",
        file_type="pdf",
        file_path=str(file_path),
        status="uploaded",
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    try:
        processing_result = process_document(
            db=db,
            document_id=document.id,
        )

        return {
            "message": "Document uploaded and processed successfully",
            "document_id": document.id,
            "filename": document.filename,
            "status": processing_result["status"],
            "chunks_created": processing_result["chunks_created"],
            "visuals_extracted": processing_result.get("visuals_extracted", 0),
            "visuals_failed": processing_result.get("visuals_failed", False),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Document processing failed: {str(exc)}",
        )


@router.get("/{document_id}/visuals")
def get_document_visuals(
    document_id: int,
    db: Session = Depends(get_db),
):
    """
    Phase 40: Return visual metadata for a document.

    Returns a list of visual elements (images, figures, tables, etc.)
    detected in the PDF. Does NOT expose raw filesystem paths.
    """
    document = db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    visuals = (
        db.query(DocumentVisual)
        .filter(DocumentVisual.document_id == document_id)
        .order_by(DocumentVisual.page_number, DocumentVisual.image_index)
        .all()
    )

    return {
        "document_id": document_id,
        "filename": document.filename,
        "visual_count": len(visuals),
        "visuals": [v.to_dict() for v in visuals],
    }