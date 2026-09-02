from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from uuid import uuid4

from app.avatar.jobs import create_job
from app.avatar.runner import generate_avatar_background
from sqlalchemy.orm import Session
from app.rag.retriever import retrieve_relevant_chunks
from app.database.connection import get_db
from app.teacher.engine import TeacherEngine
from app.teacher.state import TeacherState
from app.services.learning_service import LearningService
from app.voice.tts import TTSService
from app.models.student import Student

router = APIRouter(
    prefix="/lessons",
    tags=["Lessons"],
)


class StartLessonRequest(BaseModel):
    student_id: int
    topic: str
    document_id: int | None = None
    language: str | None = None


class NextStepRequest(BaseModel):
    state: dict


teacher_engine = TeacherEngine()
learning_service = LearningService()
tts_service = TTSService()


def extract_speech_text(teaching: str) -> str:
    if not teaching:
        return ""

    text = teaching

    if "EXPLANATION:" in text:
        text = text.split("EXPLANATION:", 1)[1]

    if "QUESTION:" in text:
        text = text.split("QUESTION:", 1)[0]

    return text.strip()

@router.post("/start")
async def start_lesson(
    request: StartLessonRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):

    student = db.get(Student, request.student_id)

    if student is None:
        raise HTTPException(
            status_code=404,
            detail="Student not found",
        )

    language = request.language or student.preferred_language

    # 1. Create persistent lesson + concepts + session
    lesson, concepts, session = learning_service.create_lesson_session(
    db=db,
    student_id=request.student_id,
    topic=request.topic,
    document_id=request.document_id,
    language=language,
)

    # 2. Start AI Teacher
    teaching_context = None

    if request.document_id is not None:
        teaching_context = retrieve_relevant_chunks(
            db=db,
            question=request.topic,
            document_id=request.document_id,
            limit=5,
        )

    result = teacher_engine.start(
        student_id=request.student_id,
        topic=request.topic,
        teaching_context=teaching_context,
        language=language,
    )
    audio_filename = f"lesson_{session.id}_teacher.mp3"

    speech_text = extract_speech_text(result["teaching"])

    audio_path = await tts_service.generate_speech(
    text=speech_text,
    language=language,
    filename=audio_filename,
    )
    avatar_job_id = str(uuid4())

    create_job(avatar_job_id)

    avatar_filename = f"lesson_{session.id}_teacher.mp4"

    background_tasks.add_task(
        generate_avatar_background,
        avatar_job_id,
        str(audio_path),
        avatar_filename,
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
    "audio_url": f"/voice/audio/{audio_filename}",
    "avatar_job_id": avatar_job_id,
    "avatar_status_url": f"/avatar/status/{avatar_job_id}",
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
        language=state_data.get("language", "English"),
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