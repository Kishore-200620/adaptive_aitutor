from app.database.connection import SessionLocal
from app.models.student import Student
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.rag.embeddings import generate_embedding
from app.rag.vector_store import save_chunks, search_similar_chunks


def test_vector_retrieval():
    db = SessionLocal()

    student = None
    document = None

    try:
        student = Student(
            name="RAG Test Student",
        )

        db.add(student)
        db.commit()
        db.refresh(student)

        document = Document(
            student_id=student.id,
            filename="rag_test.pdf",
            file_type="pdf",
            file_path="test/rag_test.pdf",
            status="processed",
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        chunks = [
            "Newton's first law states that an object remains at rest or in uniform motion unless acted upon by an external force.",
            "Photosynthesis is the process by which green plants convert light energy into chemical energy.",
            "The water cycle describes the continuous movement of water through evaporation, condensation, and precipitation.",
        ]

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

        query = "What does Newton's first law say?"

        query_embedding = generate_embedding(query)

        results = search_similar_chunks(
            db=db,
            query_embedding=query_embedding,
            document_id=document.id,
            limit=2,
        )

        assert len(results) > 0
        assert "Newton's first law" in results[0].content

        print("\nVECTOR RETRIEVAL SUCCESSFUL")
        print(f"Results returned: {len(results)}")
        print(f"Best match: {results[0].content}")

    finally:
        if document is not None:
            db.query(DocumentChunk).filter(
                DocumentChunk.document_id == document.id
            ).delete()

            db.delete(document)

        if student is not None:
            db.delete(student)

        db.commit()
        db.close()