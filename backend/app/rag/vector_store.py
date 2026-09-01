from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk


def save_chunks(
    db: Session,
    document_id: int,
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    if len(chunks) != len(embeddings):
        raise ValueError("Chunks and embeddings must have the same length")

    for index, (content, embedding) in enumerate(zip(chunks, embeddings)):
        chunk = DocumentChunk(
            document_id=document_id,
            chunk_index=index,
            content=content,
            embedding=embedding,
        )

        db.add(chunk)

    db.commit()


def search_similar_chunks(
    db: Session,
    query_embedding: list[float],
    document_id: int | None = None,
    limit: int = 5,
) -> list[DocumentChunk]:

    distance = DocumentChunk.embedding.cosine_distance(query_embedding)

    statement = select(DocumentChunk).order_by(distance)

    if document_id is not None:
        statement = statement.where(
            DocumentChunk.document_id == document_id
        )

    statement = statement.limit(limit)

    return list(db.scalars(statement).all())