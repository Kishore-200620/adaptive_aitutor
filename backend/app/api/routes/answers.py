from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.session import TeachingSession
from app.models.concept import Concept
from app.teacher.engine import TeacherEngine
from app.teacher.state import TeacherState
from app.services.learning_service import LearningService

from app.models.lesson import Lesson
from app.rag.retriever import retrieve_relevant_chunks

router = APIRouter(
    prefix="/lessons",
    tags=["Lessons"],
)


class AnswerRequest(BaseModel):
    session_id: int
    state: dict
    answer: str


teacher_engine = TeacherEngine()
learning_service = LearningService()


@router.post("/answer")
def submit_answer(
    request: AnswerRequest,
    db: Session = Depends(get_db),
):

    # 1. Load persistent teaching session
    session = db.get(
        TeachingSession,
        request.session_id,
    )

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Teaching session not found",
        )

    lesson = db.get(
        Lesson,
        session.lesson_id,
    )

    if lesson is None:
        raise HTTPException(
            status_code=404,
            detail="Lesson not found",
        )

    # 2. Reconstruct TeacherState
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

    # 3. Evaluate student's answer
    result = teacher_engine.answer(
        state,
        request.answer,
    )

    evaluation = result["evaluation"]

    # 4. Find current database concept
    concept = (
        db.query(Concept)
        .filter(
            Concept.lesson_id == session.lesson_id,
            Concept.title == state.current_concept,
        )
        .first()
    )

    if concept is None:
        raise HTTPException(
            status_code=404,
            detail="Current concept not found",
        )

    # 5. Save attempt
    learning_service.save_attempt(
        db=db,
        session=session,
        concept=concept,
        question=state.last_question or "",
        student_answer=request.answer,
        is_correct=evaluation.correctness == "correct",
        evaluation=evaluation.feedback,
        misconception=evaluation.misconception,
    )

    # 6. Persist mastery
    learning_service.update_concept_mastery(
        db=db,
        concept=concept,
        mastery_score=evaluation.score,
    )

    # 7. Continue teaching loop
    teaching_context = None

    if lesson.document_id is not None:

        if state.needs_reteaching:
            context_query = state.current_concept or state.topic

        else:
            next_concept = teacher_engine.graph.get_next_concept(state)
            context_query = next_concept or state.topic

        teaching_context = retrieve_relevant_chunks(
            db=db,
            question=context_query,
            document_id=lesson.document_id,
            limit=5,
        )

    next_step = teacher_engine.next_step(
        state,
        teaching_context=teaching_context,
    )
    # 8. Update persistent session
    if next_step["action"] == "completed":

        learning_service.update_session(
            db=db,
            session=session,
            concept_id=None,
            step="completed",
            status="completed",
        )

    elif next_step["concept"]:

        next_concept = (
            db.query(Concept)
            .filter(
                Concept.lesson_id == session.lesson_id,
                Concept.title == next_step["concept"],
            )
            .first()
        )

        if next_concept:

            learning_service.update_session(
                db=db,
                session=session,
                concept_id=next_concept.id,
                step="question",
            )

    return {
        "session_id": session.id,
        "evaluation": evaluation.summary(),
        "action": next_step["action"],
        "concept": next_step["concept"],
        "teaching": next_step["teaching"],
        "question": next_step["question"],
        "state": state.summary(),
    }