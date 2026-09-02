from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.document import Document
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
    db: Session = Depends(get_db),
):
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
        student_id=2,
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
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Document processing failed: {str(exc)}",
        )