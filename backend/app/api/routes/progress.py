from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.student import Student
from app.models.lesson import Lesson
from app.models.session import TeachingSession
from app.models.assessment import Assessment


router = APIRouter(
    prefix="/students",
    tags=["Progress"],
)


@router.get("/{student_id}/progress")
def get_student_progress(
    student_id: int,
    db: Session = Depends(get_db),
):

    student = db.get(Student, student_id)

    if student is None:
        raise HTTPException(
            status_code=404,
            detail="Student not found",
        )

    lessons = (
        db.query(Lesson)
        .filter(Lesson.student_id == student_id)
        .order_by(Lesson.id)
        .all()
    )

    sessions = (
        db.query(TeachingSession)
        .filter(TeachingSession.student_id == student_id)
        .order_by(TeachingSession.id)
        .all()
    )

    assessments = (
        db.query(Assessment)
        .join(
            TeachingSession,
            Assessment.session_id == TeachingSession.id,
        )
        .filter(TeachingSession.student_id == student_id)
        .order_by(Assessment.id)
        .all()
    )

    completed_sessions = [
        session
        for session in sessions
        if session.status == "completed"
    ]

    scores = [
        assessment.score
        for assessment in assessments
    ]

    average_score = (
        round(sum(scores) / len(scores), 2)
        if scores
        else 0
    )

    return {
        "student_id": student.id,
        "student_name": student.name,
        "total_lessons": len(lessons),
        "total_sessions": len(sessions),
        "completed_sessions": len(completed_sessions),
        "average_score": average_score,
        "assessments": [
            {
                "assessment_id": assessment.id,
                "session_id": assessment.session_id,
                "score": assessment.score,
                "total_questions": assessment.total_questions,
                "strong_areas": assessment.strong_areas,
                "weak_areas": assessment.weak_areas,
                "recommendations": assessment.recommendations,
                "next_topic": assessment.next_topic,
            }
            for assessment in assessments
        ],
    }