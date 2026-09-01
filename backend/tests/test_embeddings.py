from app.rag.embeddings import generate_embedding


def test_generate_embedding():
    text = "Newton's first law describes inertia."

    embedding = generate_embedding(text)

    assert isinstance(embedding, list)
    assert len(embedding) == 384
    assert all(isinstance(value, float) for value in embedding)

    print("\nEMBEDDING SUCCESSFUL")
    print(f"Vector dimensions: {len(embedding)}")