from pathlib import Path

from app.rag.loaders import load_document


TEST_FILE = Path("storage/uploads/test.pdf")


def test_pdf_loader():
    text = load_document(str(TEST_FILE))

    assert isinstance(text, str)
    assert len(text.strip()) > 0

    print("\nPDF TEXT EXTRACTION SUCCESSFUL")
    print(f"Extracted characters: {len(text)}")