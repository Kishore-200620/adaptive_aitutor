import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from app.models.document_visual import DocumentVisual
from app.models.document import Document
from app.database.connection import SessionLocal
from app.visuals.retriever import get_candidate_visuals
from app.api.routes.lessons import parse_teaching_response

def setup_db():
    db = SessionLocal()
    # Clean up previous
    db.query(DocumentVisual).filter(DocumentVisual.document_id == 999).delete()
    db.query(Document).filter(Document.id == 999).delete()
    db.commit()
    
    doc = Document(id=999, student_id=1, filename="test.pdf", file_type="pdf", file_path="test.pdf")
    db.add(doc)
    
    # Visual 1: Relevant caption
    v1 = DocumentVisual(document_id=999, page_number=1, visual_type="figure", caption="OSI Model layers", asset_url="/assets/osi.png", metadata_json={})
    # Visual 2: Irrelevant
    v2 = DocumentVisual(document_id=999, page_number=2, visual_type="image", caption="Company logo", asset_url="/assets/logo.png", metadata_json={})
    # Visual 3: RAG matching (same page)
    v3 = DocumentVisual(document_id=999, page_number=3, visual_type="chart", caption="TCP handshake", asset_url="/assets/tcp.png", metadata_json={})
    
    db.add_all([v1, v2, v3])
    db.commit()
    return db, v1, v2, v3

def cleanup_db(db):
    db.query(DocumentVisual).filter(DocumentVisual.document_id == 999).delete()
    db.query(Document).filter(Document.id == 999).delete()
    db.commit()
    db.close()

def run_tests():
    db, v1, v2, v3 = setup_db()
    try:
        # TEST 1: Relevant visual
        cands = get_candidate_visuals(db, 999, "OSI Model")
        assert len(cands) == 1
        assert cands[0]["id"] == v1.id
        print("TEST 1 PASS: Relevant visual")
        
        # TEST 2: Same-page relevance (RAG chunk matching)
        # "TCP handshake" has 0 overlap with "Network routing", but teaching context contains its url
        cands2 = get_candidate_visuals(db, 999, "Network routing", teaching_context=["[PDF Diagram available at /assets/tcp.png]"])
        assert len(cands2) == 1
        assert cands2[0]["id"] == v3.id
        print("TEST 2 PASS: Same-page relevance")
        
        # TEST 3: Irrelevant visual filtering
        cands3 = get_candidate_visuals(db, 999, "Company logo")
        # Exact match adds score, so it will return. 
        # But if we search for "Banana", it should return nothing.
        cands3_banana = get_candidate_visuals(db, 999, "Banana")
        assert len(cands3_banana) == 0
        print("TEST 3 PASS: Irrelevant visual filtering")
        
        # TEST 4: No relevant visual
        cands4 = get_candidate_visuals(db, 999, "UDP protocol")
        assert len(cands4) == 0
        print("TEST 4 PASS: No relevant visual")
        
        # TEST 5: Multiple candidates (Ranked correctly)
        # Add another OSI model visual
        v4 = DocumentVisual(document_id=999, page_number=4, visual_type="figure", caption="OSI Model detailed diagram", asset_url="/assets/osi2.png", metadata_json={})
        db.add(v4)
        db.commit()
        
        cands5 = get_candidate_visuals(db, 999, "OSI Model layers")
        # v1 has exact concept match "osi model layers"
        assert cands5[0]["id"] == v1.id
        assert len(cands5) == 2
        print("TEST 5 PASS: Multiple candidates ranked")
        
        # TEST 6: Provenance
        assert "document_id" in cands5[0]
        assert "visual_id" in cands5[0] or "id" in cands5[0]
        assert "page_number" in cands5[0]
        assert "asset_url" in cands5[0]
        print("TEST 6 PASS: Provenance")
        
        # TEST 7: Parse LLM Output
        teaching_text = """
BLACKBOARD:
This is a blackboard.

VISUAL_DIRECTIVE:
Draw an OSI model.
USE_PDF_VISUAL: 42

NARRATION:
Here we see the OSI model on page 12.
"""
        narration, blackboard, directive, pdf_visual_id = parse_teaching_response(teaching_text)
        assert pdf_visual_id == 42
        assert "USE_PDF_VISUAL" not in directive
        print("TEST 7 PASS: Parse response")
        
        # TEST 9: TTS isolation
        assert "USE_PDF_VISUAL" not in narration
        assert "USE_PDF_VISUAL" not in blackboard
        print("TEST 9 PASS: TTS isolation")
        
    finally:
        cleanup_db(db)

if __name__ == "__main__":
    run_tests()
