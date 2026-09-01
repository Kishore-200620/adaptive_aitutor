from sqlalchemy.orm import Session

from app.rag.embeddings import generate_embedding
from app.rag.vector_store import search_similar_chunks


def retrieve_relevant_chunks(
    db: Session,
    question: str,
    document_id: int | None = None,
    limit: int = 5,
) -> list[str]:
    query_embedding = generate_embedding(question)

    chunks = search_similar_chunks(
        db=db,
        query_embedding=query_embedding,
        document_id=document_id,
        limit=limit,
    )

    return [chunk.content for chunk in chunks]