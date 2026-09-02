from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.services.assessment_service import AssessmentService
from app.models.session import TeachingSession


router = APIRouter(
    prefix="/assessments",
    tags=["Assessments"],
)


assessment_service = AssessmentService()


@router.post("/{session_id}")
def create_assessment(
    session_id: int,
    db: Session = Depends(get_db),
):
    session = db.get(TeachingSession, session_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Teaching session not found",
        )

    if session.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="Assessment can only be created for a completed session",
        )

    try:
        assessment = assessment_service.create_assessment(
            db=db,
            session_id=session_id,
        )

        return {
            "assessment_id": assessment.id,
            "session_id": assessment.session_id,
            "score": assessment.score,
            "total_questions": assessment.total_questions,
            "strong_areas": assessment.strong_areas,
            "weak_areas": assessment.weak_areas,
            "recommendations": assessment.recommendations,
            "next_topic": assessment.next_topic,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )