import logging
import re
from sqlalchemy.orm import Session
from app.models.document_visual import DocumentVisual

logger = logging.getLogger("eduva.visual_retriever")

def get_candidate_visuals(
    db: Session,
    document_id: int,
    concept: str,
    limit: int = 5,
    teaching_context: list[str] | None = None
) -> list[dict]:
    """
    Retrieve candidate PDF visuals relevant to the current concept.
    Returns a list of dictionaries (safe for passing to LLM context).
    """
    if not document_id or not concept:
        return []

    # 1. Parse explicit page numbers from teaching context
    context_page_numbers = set()
    if teaching_context:
        for chunk in teaching_context:
            # We injected [PAGE X] in the loaders
            matches = re.findall(r'\[PAGE\s+(\d+)\]', chunk, re.IGNORECASE)
            for m in matches:
                try:
                    context_page_numbers.add(int(m))
                except ValueError:
                    pass

    # 2. Scope the query to the current document
    query = db.query(DocumentVisual).filter(
        DocumentVisual.document_id == document_id,
        DocumentVisual.asset_url != None
    )

    visuals = query.all()
    if not visuals:
        return []

    concept_lower = concept.lower()
    concept_words = set(w for w in concept_lower.replace('-', ' ').split() if len(w) > 2)

    scored_visuals = []

    for v in visuals:
        score = 0
        caption_lower = (v.caption or "").lower()
        type_lower = (v.visual_type or "").lower()

        # A. Page match (PRIMARY ASSOCIATION) (+100)
        # Only visuals on the extracted pages get this huge boost.
        if v.page_number in context_page_numbers:
            score += 100

        # B. Exact concept match (+50)
        if concept_lower in caption_lower:
            score += 50

        # C. Token overlap (+10 per word)
        caption_words = set(w for w in caption_lower.replace('-', ' ').split() if len(w) > 2)
        overlap = concept_words.intersection(caption_words)
        score += len(overlap) * 10

        # D. Type match (+5)
        if type_lower in concept_lower:
            score += 5

        # We allow visuals without captions to be selected if they match the page number.
        if score > 0:
            scored_visuals.append((score, v))

    # Sort by score descending
    scored_visuals.sort(key=lambda x: x[0], reverse=True)

    candidates = []
    for score, v in scored_visuals[:limit]:
        candidates.append(v.to_dict())

    return candidates
