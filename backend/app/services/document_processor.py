from sqlalchemy.orm import Session

from app.models.document import Document
from app.rag.loaders import load_document
from app.rag.chunker import chunk_text
from app.rag.embeddings import generate_embedding
from app.rag.vector_store import save_chunks


def process_document(
    db: Session,
    document_id: int,
):
    document = db.get(Document, document_id)

    if document is None:
        raise ValueError("Document not found")

    document.status = "processing"
    db.commit()

    try:
        text = load_document(document.file_path)

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

        document.status = "processed"
        db.commit()

        return {
            "document_id": document.id,
            "chunks_created": len(chunks),
            "status": document.status,
        }

    except Exception:
        document.status = "failed"
        db.commit()
        raise