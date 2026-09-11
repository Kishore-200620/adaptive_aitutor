from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from uuid import uuid4


from sqlalchemy.orm import Session
from app.rag.retriever import retrieve_relevant_chunks
from app.database.connection import get_db
from app.teacher.engine import TeacherEngine
from app.teacher.state import TeacherState
from app.services.learning_service import LearningService
from app.voice.tts import TTSService
from app.models.student import Student
from app.models.session import TeachingSession
from app.models.lesson import Lesson
from app.visuals.orchestrator import PresentationOrchestrator

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
    session_id: int
    state: dict

class ChangeLanguageRequest(BaseModel):
    language: str


teacher_engine = TeacherEngine()
learning_service = LearningService()
tts_service = TTSService()
orchestrator = PresentationOrchestrator()

def parse_teaching_response(teaching: str) -> tuple[str, str, str]:
    if not teaching:
        return "", "", ""
        
    narration = ""
    blackboard = ""
    directive = ""
    
    text = teaching
    
    if "QUESTION:" in text:
        text = text.split("QUESTION:", 1)[0]
        
    if "VISUAL_DIRECTIVE:" in text:
        parts = text.split("VISUAL_DIRECTIVE:", 1)
        text = parts[0]
        directive = parts[1].strip()
        
    if "BLACKBOARD:" in text:
        parts = text.split("BLACKBOARD:", 1)
        text = parts[0]
        blackboard = parts[1].strip()
        
    if "NARRATION:" in text:
        narration = text.split("NARRATION:", 1)[1].strip()
    else:
        narration = text.strip()
        
    return narration, blackboard, directive

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

    # 1. Plan Curriculum first so DB concepts match exactly
    planned_concepts = teacher_engine.planner._get_concepts(request.topic)

    # 2. Create persistent lesson + concepts + session
    lesson, concepts, session = learning_service.create_lesson_session(
        db=db,
        student_id=request.student_id,
        topic=request.topic,
        planned_concepts=planned_concepts,
        document_id=request.document_id,
        language=language,
    )

    # 3. Start AI Teacher
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
        planned_concepts=planned_concepts,
    )
    
    # Ensure the engine uses the DB's synced planned concepts!
    result["state"].planned_concepts = planned_concepts
    if not result["state"].current_concept:
        result["state"].current_concept = planned_concepts[0]
    audio_filename = f"lesson_{session.id}_teacher.mp3"

    narration, blackboard, directive = parse_teaching_response(result["teaching"])
    presentation = await orchestrator.orchestrate(
        teacher_state=result["state"],
        narration=narration,
        blackboard_content=blackboard,
        visual_directive=directive
    )

    audio_path = None
    if presentation.voice.enabled and presentation.voice.narration:
        audio_path = await tts_service.generate_speech(
            text=presentation.voice.narration,
            language=language,
            filename=audio_filename,
        )

    audio_url = f"/voice/audio/{audio_filename}" if audio_path else None

    # 3. Keep database session aligned with TeacherState
    if concepts:
        state_data = {
            "current_concept": result["state"].current_concept,
            "mastery_score": result["state"].mastery_score,
            "difficulty_level": result["state"].difficulty_level,
            "teaching_strategy": result["state"].teaching_strategy,
            "current_phase": result["state"].current_phase,
            "last_question": result["state"].last_question,
            "last_answer": result["state"].last_answer,
            "last_evaluation": result["state"].last_evaluation,
            "misconceptions": result["state"].misconceptions,
            "concepts_struggling": result["state"].concepts_struggling,
            "concepts_completed": result["state"].concepts_completed,
            "needs_reteaching": result["state"].needs_reteaching,
            "attempt_count": result["state"].attempt_count,
            "assessment_active": result["state"].assessment_active,
            "recent_clarifications": result["state"].recent_clarifications,
            "planned_concepts": result["state"].planned_concepts,
            "current_concept_index": result["state"].current_concept_index,
            "concept_steps_total": result["state"].concept_steps_total,
            "concept_steps_current": result["state"].concept_steps_current,
            "concept_history": result["state"].concept_history,
            "teaching": result["teaching"],
            "presentation": presentation.model_dump(),
            "audio_url": audio_url
        }
        learning_service.update_session(
            db=db,
            session=session,
            concept_id=concepts[0].id,
            step="question",
            state_data=state_data
        )

    return {
        "session_id": session.id,
        "lesson_id": lesson.id,
        "student_id": request.student_id,
        "topic": request.topic,
        "action": "teaching",
        "concept": result["state"].current_concept,
        "teaching": result["teaching"],
        "question": result["question"],
        "presentation": presentation.model_dump(),
        "audio_url": audio_url,
        "state": result["state"].summary(),
    }

from fastapi.responses import StreamingResponse
import json
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eduva.stream")
logger.setLevel(logging.INFO)

@router.post("/start/stream")
async def start_lesson_stream(
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
    
    logger.info("[EDUVA][Latency] REQUEST_START")
    start_time = time.time()
    logger.info(f"[EDUVA][Stream] start_lesson_stream request_start for {request.topic}")

    # 1. Plan Curriculum first so DB concepts match exactly
    logger.info("[EDUVA][Latency] PLANNER_START")
    planned_concepts = teacher_engine.planner._get_concepts(request.topic)
    logger.info("[EDUVA][Latency] PLANNER_COMPLETE")
    
    # 2. Create persistent lesson + concepts + session
    lesson, concepts, session = learning_service.create_lesson_session(
        db=db,
        student_id=request.student_id,
        topic=request.topic,
        planned_concepts=planned_concepts,
        document_id=request.document_id,
        language=language,
    )

    # 3. Start AI Teacher
    teaching_context = None
    if request.document_id is not None:
        logger.info("[EDUVA][Latency] RAG_START")
        rag_start = time.time()
        teaching_context = retrieve_relevant_chunks(
            db=db,
            question=request.topic,
            document_id=request.document_id,
            limit=5,
        )
        rag_time = time.time() - rag_start
        logger.info(f"[EDUVA][Latency] RAG_COMPLETE in {rag_time:.2f}s")
        logger.info(f"[EDUVA][RAG] retrieval latency: {rag_time:.2f}s")

    async def event_generator():
        try:
            # We need to construct the state before streaming to get the presentation
            pre_state = TeacherState(
                student_id=request.student_id,
                topic=request.topic,
                language=language,
            )
            pre_state.planned_concepts = planned_concepts
            pre_state.current_concept = planned_concepts[0] if planned_concepts else request.topic
            
            # Compute a partial presentation (just for video) before stream
            partial_presentation = await orchestrator.orchestrate(
                teacher_state=pre_state,
                narration="",
                blackboard_content="",
                visual_directive=None
            )
            # Yield early presentation event so UI can mount video immediately
            yield f"data: {json.dumps({'type': 'presentation', 'data': partial_presentation.model_dump()})}\n\n"
            
            gen = await teacher_engine.start_stream(
                student_id=request.student_id,
                topic=request.topic,
                teaching_context=teaching_context,
                language=language,
                planned_concepts=planned_concepts,
            )
            
            final_data = None
            teaching_text = ""
            
            logger.info("[EDUVA][Latency] LLM_START")
            llm_start = time.time()
            first_token = True
            
            async for event in gen:
                if event["type"] == "teaching_chunk":
                    if first_token:
                        logger.info(f"[EDUVA][Latency] LLM_FIRST_TOKEN in {time.time() - llm_start:.2f}s")
                        first_token = False
                    teaching_text += event["content"]
                    yield f"data: {json.dumps({'type': 'teaching_chunk', 'content': event['content']})}\n\n"
                elif event["type"] == "complete":
                    final_data = event["data"]
                    
            llm_time = time.time() - llm_start
            logger.info(f"[EDUVA][Latency] LLM_COMPLETE in {llm_time:.2f}s")
            logger.info(f"[EDUVA][Groq] Full generation latency: {llm_time:.2f}s")
            
            logger.info("[EDUVA][Latency] TTS_START")
            tts_start = time.time()
            
            narration, blackboard, directive = parse_teaching_response(teaching_text)
            presentation = await orchestrator.orchestrate(
                teacher_state=final_data["state"],
                narration=narration,
                blackboard_content=blackboard,
                visual_directive=directive
            )
            
            audio_filename = f"lesson_{session.id}_teacher.mp3"
            audio_path = None
            if presentation.voice.enabled and presentation.voice.narration:
                audio_path = await tts_service.generate_speech(
                    text=presentation.voice.narration,
                    language=language,
                    filename=audio_filename,
                )
            
            tts_time = time.time() - tts_start
            logger.info(f"[EDUVA][Latency] TTS_COMPLETE in {tts_time:.2f}s")
            logger.info(f"[EDUVA][TTS] generation latency: {tts_time:.2f}s")
            
            audio_url = f"/voice/audio/{audio_filename}" if audio_path else None
            
            logger.info("[EDUVA][Latency] DB_START")
            db_start = time.time()
            if concepts:
                state_data = {
                    "current_concept": final_data["state"].current_concept,
                    "mastery_score": final_data["state"].mastery_score,
                    "difficulty_level": final_data["state"].difficulty_level,
                    "teaching_strategy": final_data["state"].teaching_strategy,
                    "current_phase": final_data["state"].current_phase,
                    "last_question": final_data["state"].last_question,
                    "last_answer": final_data["state"].last_answer,
                    "last_evaluation": final_data["state"].last_evaluation,
                    "misconceptions": final_data["state"].misconceptions,
                    "concepts_struggling": final_data["state"].concepts_struggling,
                    "concepts_completed": final_data["state"].concepts_completed,
                    "needs_reteaching": final_data["state"].needs_reteaching,
                    "attempt_count": final_data["state"].attempt_count,
                    "assessment_active": final_data["state"].assessment_active,
                    "recent_clarifications": final_data["state"].recent_clarifications,
                    "planned_concepts": final_data["state"].planned_concepts,
                    "current_concept_index": final_data["state"].current_concept_index,
                    "concept_steps_total": final_data["state"].concept_steps_total,
                    "concept_steps_current": final_data["state"].concept_steps_current,
                    "concept_history": final_data["state"].concept_history,
                    "teaching": teaching_text,
                    "presentation": presentation.model_dump(),
                    "audio_url": audio_url
                }
                learning_service.update_session(
                    db=db,
                    session=session,
                    concept_id=concepts[0].id,
                    step="question",
                    state_data=state_data
                )
            
            final_response = {
                "session_id": session.id,
                "lesson_id": lesson.id,
                "student_id": request.student_id,
                "topic": request.topic,
                "action": "teaching",
                "concept": final_data["state"].current_concept,
                "teaching": teaching_text,
                "question": final_data["question"],
                "presentation": presentation.model_dump(),
                "audio_url": audio_url,
                "state": final_data["state"].summary(),
            }
            
            db_time = time.time() - db_start
            logger.info(f"[EDUVA][Latency] DB_COMPLETE in {db_time:.2f}s")
            logger.info(f"[EDUVA][DB] Persistence latency: {db_time:.2f}s")
            
            logger.info(f"[EDUVA][Latency] SSE_COMPLETE in {time.time() - start_time:.2f}s")
            logger.info(f"[EDUVA][Stream] response_complete in {time.time() - start_time:.2f}s")
            
            yield f"data: {json.dumps({'type': 'complete', 'data': final_response})}\n\n"
        except Exception as e:
            logger.error(f"[EDUVA][Stream] Error in start_lesson_stream: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/next")
def next_step(
    request: NextStepRequest,
    db: Session = Depends(get_db),
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
        needs_reteaching=state_data.get("needs_reteaching", False),
        attempt_count=state_data.get("attempt_count", 0),
        assessment_active=state_data.get("assessment_active", False),
        recent_clarifications=state_data.get("recent_clarifications", []),
        planned_concepts=state_data.get("planned_concepts", []),
        current_concept_index=state_data.get("current_concept_index", 0),
        concept_steps_total=state_data.get("concept_steps_total", 2),
        concept_steps_current=state_data.get("concept_steps_current", 1),
        concept_history=state_data.get("concept_history", []),
    )

    result = teacher_engine.next_step(state)

    session = db.get(TeachingSession, request.session_id)
    if session:
        # Note: next_step doesn't generate audio/avatar in the current route, only answer() and start() do.
        # But we still persist the teaching content so the client can resume correctly.
        persist_state = {
            "current_concept": state.current_concept,
            "mastery_score": state.mastery_score,
            "difficulty_level": state.difficulty_level,
            "teaching_strategy": state.teaching_strategy,
            "current_phase": state.current_phase,
            "last_question": result["question"] or state.last_question,
            "last_answer": state.last_answer,
            "last_evaluation": state.last_evaluation,
            "misconceptions": state.misconceptions,
            "concepts_struggling": state.concepts_struggling,
            "concepts_completed": state.concepts_completed,
            "needs_reteaching": state.needs_reteaching,
            "attempt_count": state.attempt_count,
            "assessment_active": state.assessment_active,
            "recent_clarifications": state.recent_clarifications,
            "planned_concepts": state.planned_concepts,
            "current_concept_index": state.current_concept_index,
            "concept_steps_total": state.concept_steps_total,
            "concept_steps_current": state.concept_steps_current,
            "concept_history": state.concept_history,
            "teaching": result["teaching"],
            "visual": result.get("visual").model_dump() if hasattr(result.get("visual"), "model_dump") else (result.get("visual").dict() if hasattr(result.get("visual"), "dict") else result.get("visual")),
            # Preserve existing avatar/audio since next_step does not generate new ones here
            "audio_url": session.state_data.get("audio_url") if session.state_data else None,
        }
        
        # update current concept mapping
        from app.models.concept import Concept
        concept_obj = None
        if result["concept"]:
            concept_obj = db.query(Concept).filter(Concept.lesson_id == session.lesson_id, Concept.title == result["concept"]).first()
            
        learning_service.update_session(
            db=db,
            session=session,
            concept_id=concept_obj.id if concept_obj else None,
            step="completed" if result["action"] == "completed" else "explain",
            status="completed" if result["action"] == "completed" else "active",
            state_data=persist_state
        )

    return {
        "action": result["action"],
        "concept": result["concept"],
        "teaching": result["teaching"],
        "question": result["question"],
        "visual": result.get("visual"),
        "state": state.summary(),
    }


@router.get("/session/{session_id}")
def recover_session(
    session_id: int,
    db: Session = Depends(get_db),
):
    session = db.get(TeachingSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Teaching session not found")
        
    lesson = db.get(Lesson, session.lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")

    state_data = session.state_data or {}
    
    # Reconstruct TeacherState dict as expected by frontend
    recovered_state = {
        "student_id": session.student_id,
        "topic": lesson.topic,
        "language": lesson.language,
        "current_concept": state_data.get("current_concept"),
        "mastery_score": state_data.get("mastery_score", 0.0),
        "difficulty_level": state_data.get("difficulty_level", "beginner"),
        "teaching_strategy": state_data.get("teaching_strategy", "direct_explanation"),
        "current_phase": state_data.get("current_phase", "introduction"),
        "last_question": state_data.get("last_question"),
        "last_answer": state_data.get("last_answer"),
        "last_evaluation": state_data.get("last_evaluation"),
        "misconceptions": state_data.get("misconceptions", []),
        "concepts_completed": state_data.get("concepts_completed", []),
        "concepts_struggling": state_data.get("concepts_struggling", []),
        "needs_reteaching": state_data.get("needs_reteaching", False),
        "attempt_count": state_data.get("attempt_count", 0),
        "assessment_active": state_data.get("assessment_active", False),
        "recent_clarifications": state_data.get("recent_clarifications", []),
        "planned_concepts": state_data.get("planned_concepts", []),
        "current_concept_index": state_data.get("current_concept_index", 0),
        "concept_steps_total": state_data.get("concept_steps_total", 2),
        "concept_steps_current": state_data.get("concept_steps_current", 1),
        "concept_history": state_data.get("concept_history", []),
    }

    action = "completed" if session.status == "completed" else "teaching"
    
    return {
        "session_id": session.id,
        "lesson_id": lesson.id,
        "student_id": session.student_id,
        "topic": lesson.topic,
        "action": action,
        "concept": state_data.get("current_concept"),
        "teaching": state_data.get("teaching", ""),
        "question": state_data.get("last_question"),
        "visual": state_data.get("visual"),
        "audio_url": state_data.get("audio_url"),
        "state": recovered_state,
    }

@router.get("/sessions/{student_id}")
def get_student_sessions(
    student_id: int,
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(TeachingSession)
        .filter(TeachingSession.student_id == student_id)
        .order_by(TeachingSession.started_at.desc())
        .limit(10)
        .all()
    )
    
    result = []
    for s in sessions:
        lesson = db.get(Lesson, s.lesson_id)
        if not lesson:
            continue
        
        concept = None
        if s.state_data and "current_concept" in s.state_data:
            concept = s.state_data["current_concept"]
            
        result.append({
            "session_id": s.id,
            "topic": lesson.topic,
            "concept": concept,
            "last_updated": s.started_at.isoformat(),
        })
        
    return result

@router.post("/session/{session_id}/language")
async def change_language(
    session_id: int,
    request: ChangeLanguageRequest,
    db: Session = Depends(get_db),
):
    session = db.get(TeachingSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Teaching session not found")
        
    lesson = db.get(Lesson, session.lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")

    state_data = session.state_data or {}
    
    # 1. Update language
    lesson.language = request.language
    db.commit()
    
    # 2. Translate current teaching content if it exists
    teaching_content = state_data.get("teaching")
    if teaching_content:
        translated_teaching = teacher_engine.teaching.translate(teaching_content, request.language)
        state_data["teaching"] = translated_teaching
        
        # 3. Generate new audio
        speech_text = extract_speech_text(translated_teaching)
        audio_filename = f"lesson_{session.id}_teacher_{request.language}.mp3"
        
        audio_path = await tts_service.generate_speech(
            text=speech_text,
            language=request.language,
            filename=audio_filename,
        )
        
        state_data["audio_url"] = f"/voice/audio/{audio_filename}"
        
        # Update session in db
        session.state_data = state_data
        db.commit()

    return recover_session(session_id, db)