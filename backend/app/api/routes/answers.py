from fastapi import APIRouter
from pydantic import BaseModel

from app.teacher.engine import TeacherEngine
from app.teacher.state import TeacherState


router = APIRouter(
    prefix="/lessons",
    tags=["Lessons"],
)


class AnswerRequest(BaseModel):
    state: dict
    answer: str


teacher_engine = TeacherEngine()


@router.post("/answer")
def submit_answer(request: AnswerRequest):

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

    # 1. Evaluate the student's answer
    result = teacher_engine.answer(
        state,
        request.answer,
    )

    # 2. Automatically continue the teaching loop
    next_step = teacher_engine.next_step(state)

    return {
        "evaluation": result["evaluation"].summary(),

        "action": next_step["action"],

        "concept": next_step["concept"],

        "teaching": next_step["teaching"],

        "question": next_step["question"],

        "state": state.summary(),
    }