from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.teacher.engine import TeacherEngine
from app.teacher.state import TeacherState
from app.services.learning_service import LearningService


router = APIRouter(
    prefix="/lessons",
    tags=["Lessons"],
)


class StartLessonRequest(BaseModel):
    student_id: int
    topic: str


class NextStepRequest(BaseModel):
    state: dict


teacher_engine = TeacherEngine()
learning_service = LearningService()


@router.post("/start")
def start_lesson(
    request: StartLessonRequest,
    db: Session = Depends(get_db),
):

    # 1. Create persistent lesson + concepts + session
    lesson, concepts, session = learning_service.create_lesson_session(
        db=db,
        student_id=request.student_id,
        topic=request.topic,
    )

    # 2. Start AI Teacher
    result = teacher_engine.start(
        student_id=request.student_id,
        topic=request.topic,
    )

    # 3. Keep database session aligned with TeacherState
    if concepts:
        learning_service.update_session(
            db=db,
            session=session,
            concept_id=concepts[0].id,
            step="question",
        )

    return {
        "session_id": session.id,
        "lesson_id": lesson.id,
        "student_id": request.student_id,
        "topic": request.topic,
        "concept": result["state"].current_concept,
        "teaching": result["teaching"],
        "question": result["question"],
        "state": result["state"].summary(),
    }


@router.post("/next")
def next_step(
    request: NextStepRequest,
):

    state_data = request.state

    state = TeacherState(
        student_id=state_data["student_id"],
        topic=state_data["topic"],
        current_concept=state_data["current_concept"],
        mastery_score=state_data["mastery_score"],
        difficulty_level=state_data["difficulty_level"],
        teaching_strategy=state_data["teaching_strategy"],
        current_phase=state_data["current_phase"],
        last_question=state_data["last_question"],
        last_answer=state_data.get("last_answer"),
        last_evaluation=state_data.get("last_evaluation"),
        misconceptions=state_data["misconceptions"],
        concepts_completed=state_data["concepts_completed"],
        concepts_struggling=state_data["concepts_struggling"],
        needs_reteaching=state_data["needs_reteaching"],
        attempt_count=state_data["attempt_count"],
    )

    result = teacher_engine.next_step(state)

    return {
        "action": result["action"],
        "concept": result["concept"],
        "teaching": result["teaching"],
        "question": result["question"],
        "state": state.summary(),
    }