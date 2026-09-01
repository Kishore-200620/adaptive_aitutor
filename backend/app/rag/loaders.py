from pathlib import Path

from pypdf import PdfReader
from docx import Document
from pptx import Presentation


def load_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)

    pages = []

    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)

    return "\n\n".join(pages)


def load_docx(file_path: str) -> str:
    document = Document(file_path)

    paragraphs = []

    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            paragraphs.append(paragraph.text.strip())

    return "\n\n".join(paragraphs)


def load_pptx(file_path: str) -> str:
    presentation = Presentation(file_path)

    slides = []

    for slide in presentation.slides:
        texts = []

        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                texts.append(shape.text.strip())

        if texts:
            slides.append("\n".join(texts))

    return "\n\n".join(slides)


def load_document(file_path: str) -> str:
    extension = Path(file_path).suffix.lower()

    if extension == ".pdf":
        return load_pdf(file_path)

    if extension == ".docx":
        return load_docx(file_path)

    if extension == ".pptx":
        return load_pptx(file_path)

    raise ValueError(f"Unsupported file type: {extension}")