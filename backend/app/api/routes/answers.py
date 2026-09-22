from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from uuid import uuid4
import asyncio
from typing import Optional

from app.database.connection import get_db
from app.models.session import TeachingSession
from app.models.concept import Concept
from app.teacher.engine import TeacherEngine
from app.teacher.state import TeacherState
from app.services.learning_service import LearningService
from app.visuals.orchestrator import PresentationOrchestrator
from app.voice.tts import tts_service, start_background_speech
from app.voice.chunker import NarrationStreamer, TextChunker
from app.models.lesson import Lesson
from app.models.student import Student
from app.rag.retriever import retrieve_relevant_chunks
from app.services.event_service import EventService
from app.services.memory_service import MemoryService
from app.services.roadmap_service import RoadmapService

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

orchestrator = PresentationOrchestrator()

def parse_teaching_response(teaching: str) -> tuple[str, str, str, int | None]:
    if not teaching:
        return "", "", "", None
        
    import re
    
    narration = ""
    blackboard = ""
    directive = ""
    pdf_visual_id = None
    
    # Safely extract sections using regex.
    # We look for the section header (allowing optional markdown ** or *), capture everything until the next known section header or EOF.
    bb_match = re.search(r'\*?\*?BLACKBOARD:\*?\*?\s*(.*?)(?=^[\s\*]*(?:BLACKBOARD|VISUAL_DIRECTIVE|NARRATION|QUESTION):|$)', teaching, re.DOTALL | re.IGNORECASE | re.MULTILINE)
    if bb_match:
        blackboard = bb_match.group(1).strip()
        
    vd_match = re.search(r'\*?\*?VISUAL_DIRECTIVE:\*?\*?\s*(.*?)(?=^[\s\*]*(?:BLACKBOARD|VISUAL_DIRECTIVE|NARRATION|QUESTION):|$)', teaching, re.DOTALL | re.IGNORECASE | re.MULTILINE)
    if vd_match:
        directive = vd_match.group(1).strip()
        
    # Check for PDF Visual override globally anywhere in the teaching response
    pdf_match = re.search(r'USE_PDF_VISUAL:\s*\[?(?:ID\s*)?(\d+)\]?', teaching, re.IGNORECASE)
    if pdf_match:
        pdf_visual_id = int(pdf_match.group(1))
        # Remove the directive to avoid unwanted image generation, and scrub from blackboard
        directive = re.sub(r'USE_PDF_VISUAL:\s*\[?(?:ID\s*)?\d+\]?', '', directive, flags=re.IGNORECASE).strip()
        blackboard = re.sub(r'USE_PDF_VISUAL:\s*\[?(?:ID\s*)?\d+\]?', '', blackboard, flags=re.IGNORECASE).strip()
        
    narr_match = re.search(r'\*?\*?NARRATION:\*?\*?\s*(.*?)(?=^[\s\*]*(?:BLACKBOARD|VISUAL_DIRECTIVE|NARRATION|QUESTION):|$)', teaching, re.DOTALL | re.IGNORECASE | re.MULTILINE)
    if narr_match:
        narration = narr_match.group(1).strip()
        narration = re.sub(r'USE_PDF_VISUAL:\s*\[?(?:ID\s*)?\d+\]?', '', narration, flags=re.IGNORECASE).strip()
    else:
        # If no explicit NARRATION, and no blackboard found either, use full text
        if not blackboard:
            blackboard = teaching.strip()
            
        clean_text = re.sub(r'#+\s*', '', teaching)
        clean_text = re.sub(r'\*\*(.*?)\*\*', r'\1', clean_text)
        clean_text = re.sub(r'\*(.*?)\*', r'\1', clean_text)
        sentences = re.split(r'(?<=[.!?])\s+', clean_text.strip())
        narration = ' '.join(sentences[:3]) if len(sentences) > 3 else clean_text.strip()
        
    return narration, blackboard, directive, pdf_visual_id


@router.post("/answer")
async def submit_answer(
    request: AnswerRequest,
    background_tasks: BackgroundTasks,
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
        assessment_active=state_data.get("assessment_active", False),
        recent_clarifications=state_data.get("recent_clarifications", []),
        concept_steps_total=state_data.get("concept_steps_total", 2),
        concept_steps_current=state_data.get("concept_steps_current", 1),
        concept_history=state_data.get("concept_history", []),
        planned_concepts=state_data.get("planned_concepts", []),
        current_concept_index=state_data.get("current_concept_index", 0),
        teaching_cursor=state_data.get("teaching_cursor", None),
    )

    intent_task = asyncio.create_task(teacher_engine.classify_intent(state, request.answer))

    current_concept_title = state.current_concept or lesson.topic
    memories = MemoryService.get_relevant_memory_for_concept(db, state.student_id, current_concept_title)
    learner_memory_context = MemoryService.format_memory_context(memories)

    concept = (
        db.query(Concept)
        .filter(
            Concept.lesson_id == session.lesson_id,
            Concept.title == current_concept_title,
        )
        .first()
    )

    interaction_type = await intent_task

    # Log student message based on intent
    if interaction_type == "clarification":
        EventService.log_event(db, session.id, state.student_id, "student_question", "student", {"text": request.answer}, session.lesson_id, session.current_concept_id)
        EventService.log_event(db, session.id, state.student_id, "clarification_requested", "student", {}, session.lesson_id, session.current_concept_id)
    elif interaction_type in ("continue", "continue_step"):
        EventService.log_event(db, session.id, state.student_id, "student_message", "student", {"text": request.answer}, session.lesson_id, session.current_concept_id)
    else:
        # assessment
        EventService.log_event(db, session.id, state.student_id, "answer_submitted", "student", {"text": request.answer}, session.lesson_id, session.current_concept_id)

    if interaction_type == "continue":
        state.recent_clarifications = []
        if state.assessment_active:
            return {
                "session_id": session.id,
                "evaluation": None,
                "action": "assessment_reminder",
                "concept": state.current_concept,
                "teaching": f"NARRATION: Please answer the understanding-check question before we continue.\n\nQUESTION: {state.last_question}",
                "question": state.last_question,
                "presentation": None,
                "audio_url": None,
                "state": state.summary(),
                "interaction_type": "assessment",
                "assessment_active": True,
            }
        elif state.concept_steps_current < state.concept_steps_total:
            interaction_type = "continue_step"
        else:
            interaction_type = "clarification"

    if interaction_type == "clarification":
        # Path A: Clarification
        # Retrieve context for clarification if document exists
        teaching_context = None
        if lesson.document_id is not None:
            context_query = state.current_concept or state.topic
            teaching_context = await retrieve_relevant_chunks(
                db=db,
                question=context_query,
                document_id=lesson.document_id,
                limit=5,
            )
            
        clarification_text = teacher_engine.clarify(state, request.answer, teaching_context)
        narration, blackboard, directive, pdf_visual_id = parse_teaching_response(clarification_text)
        def pdf_visual_cb(subject: str) -> Optional[dict]:
            if not session.document_id: return None
            from app.visuals.retriever import get_candidate_visuals
            cands = get_candidate_visuals(db=db, document_id=session.document_id, concept=subject)
            return cands[0] if cands else None

        presentation = await orchestrator.orchestrate(
            teacher_state=state,
            narration=narration,
            blackboard_content=blackboard,
            visual_directive=directive,
            teaching_context=teaching_context,
            fetch_pdf_visual_cb=pdf_visual_cb
        )
        presentation_dict = presentation.model_dump()
        
        audio_url = None
        if presentation.voice.enabled and presentation.voice.narration:
            audio_filename = f"lesson_{session.id}_clarification_{uuid4().hex[:8]}.mp3"
            tts_service.job_status[audio_filename] = "pending"
            start_background_speech(
                text=presentation.voice.narration,
                language=state.language,
                filename=audio_filename,
            )
            audio_url = f"/voice/audio/{audio_filename}"

        state.recent_clarifications.append({"role": "user", "content": request.answer})
        state.recent_clarifications.append({"role": "assistant", "content": clarification_text})
        
        MAX_RECENT_CLARIFICATIONS = 6
        state.recent_clarifications = state.recent_clarifications[-MAX_RECENT_CLARIFICATIONS:]
        
        learning_service.update_session(
            db=db,
            session=session,
            concept_id=session.current_concept_id,
            step=session.current_step or "clarification",
            state_data=state.summary()
        )
        
        EventService.log_event(
            db, session.id, state.student_id, "clarification_answered", "teacher", 
            {"text": clarification_text, "concept": state.current_concept}, 
            session.lesson_id, session.current_concept_id
        )
        if presentation and presentation.blackboard and presentation.blackboard.enabled and presentation.blackboard.visual_url:
            EventService.log_event(
                db, session.id, state.student_id, "visual_presented", "system", 
                {
                    "visual_source": presentation.blackboard.visual_source,
                    "visual_type": presentation.blackboard.visual_type,
                    "visual_url": presentation.blackboard.visual_url,
                    "concept": state.current_concept
                }, session.lesson_id, session.current_concept_id
            )

        return {
            "session_id": session.id,
            "evaluation": None,
            "action": "clarification",
            "concept": state.current_concept,
            "teaching": clarification_text,
            "question": state.last_question,
            "presentation": presentation_dict,
            "audio_url": audio_url,
            "state": state.summary(),
            "interaction_type": "clarification",
            "assessment_active": state.assessment_active,
        }

    if interaction_type == "continue_step":
        # Path C: Continue Step
        result = teacher_engine.continue_step(state, teaching_context=None, learner_memory_context=learner_memory_context)
        
        narration, blackboard, directive, pdf_visual_id = parse_teaching_response(result["teaching"])
        presentation = await orchestrator.orchestrate(
            teacher_state=state,
            narration=narration,
            blackboard_content=blackboard,
            visual_directive=directive,
            teaching_context=None
        )
        presentation_dict = presentation.model_dump()
        
        audio_url = None
        if presentation.voice.enabled and presentation.voice.narration:
            audio_filename = f"lesson_{session.id}_continue_{uuid4().hex[:8]}.mp3"
            tts_service.job_status[audio_filename] = "pending"
            start_background_speech(
                text=presentation.voice.narration,
                language=state.language,
                filename=audio_filename,
            )
            audio_url = f"/voice/audio/{audio_filename}"
                
        learning_service.update_session(
            db=db,
            session=session,
            concept_id=session.current_concept_id,
            step="continue",
            state_data=state.summary()
        )
        
        EventService.log_event(
            db, session.id, state.student_id, "teacher_message", "teacher", 
            {"text": result["teaching"], "concept": state.current_concept}, 
            session.lesson_id, session.current_concept_id
        )
        if presentation and presentation.blackboard and presentation.blackboard.enabled and presentation.blackboard.visual_url:
            EventService.log_event(
                db, session.id, state.student_id, "visual_presented", "system", 
                {
                    "visual_source": presentation.blackboard.visual_source,
                    "visual_type": presentation.blackboard.visual_type,
                    "visual_url": presentation.blackboard.visual_url,
                    "concept": state.current_concept
                }, session.lesson_id, session.current_concept_id
            )
        
        return {
            "session_id": session.id,
            "evaluation": None,
            "action": "continue_step",
            "concept": state.current_concept,
            "teaching": result["teaching"],
            "question": state.last_question,
            "presentation": presentation_dict,
            "audio_url": audio_url,
            "state": state.summary(),
            "interaction_type": "continue_step",
            "assessment_active": state.assessment_active,
        }

    # Path B: Assessment Answer
    # 3. Evaluate student's answer
    result = await teacher_engine.answer(
        state,
        request.answer,
    )

    evaluation = result["evaluation"]

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
    
    EventService.log_event(
        db, session.id, state.student_id, "answer_evaluated", "system", 
        {"correctness": evaluation.correctness, "feedback": evaluation.feedback}, 
        session.lesson_id, concept.id
    )
    if evaluation.misconception:
        EventService.log_event(
            db, session.id, state.student_id, "misconception_detected", "system", 
            {"misconception": evaluation.misconception}, 
            session.lesson_id, concept.id
        )

    # 6. Persist mastery
    learning_service.update_concept_mastery(
        db=db,
        concept=concept,
        mastery_score=evaluation.score,
    )
    
    EventService.log_event(
        db, session.id, state.student_id, "mastery_updated", "system", 
        {"score": evaluation.score}, 
        session.lesson_id, concept.id
    )

    # 6b. Roadmap completion evaluation
    completion_eval = RoadmapService.evaluate_concept_completion(db, state.student_id, concept, state.mastery_score)
    roadmap_status = completion_eval["status"]
    
    # Update TeacherState Adaptation
    teacher_engine.adaptation.adapt(state, roadmap_status)

    next_concept_title = None
    if roadmap_status == "complete":
        next_db_concept = RoadmapService.get_next_concept(db, state.student_id, session.lesson_id, concept)
        if next_db_concept:
            next_concept_title = next_db_concept.title

    # 7. Continue teaching loop
    teaching_context = None

    if lesson.document_id is not None:

        if state.needs_reteaching:
            context_query = state.current_concept or state.topic

        else:
            context_query = next_concept_title or state.topic

        teaching_context = await retrieve_relevant_chunks(
            db=db,
            question=context_query,
            document_id=lesson.document_id,
            limit=5,
        )

    roadmap_context = RoadmapService.format_roadmap_context(db, state.student_id, session.lesson_id, concept)
    if teaching_context is None:
        teaching_context = [roadmap_context]
    else:
        teaching_context.insert(0, roadmap_context)

    next_step = teacher_engine.next_step(
        state,
        teaching_context=teaching_context,
        learner_memory_context=learner_memory_context,
        next_concept_title=next_concept_title,
    )

    audio_url = None
    presentation_dict = None

    if next_step["teaching"]:

        audio_filename = (
            f"lesson_{session.id}_attempt_{state.attempt_count}.mp3"
        )
        
        narration, blackboard, directive, pdf_visual_id = parse_teaching_response(next_step["teaching"])
        def pdf_visual_cb(subject: str) -> Optional[dict]:
            if not session.document_id: return None
            from app.visuals.retriever import get_candidate_visuals
            cands = get_candidate_visuals(db=db, document_id=session.document_id, concept=subject)
            return cands[0] if cands else None

        presentation = await orchestrator.orchestrate(
            teacher_state=state,
            narration=narration,
            blackboard_content=blackboard,
            visual_directive=directive,
            teaching_context=teaching_context,
            fetch_pdf_visual_cb=pdf_visual_cb
        )
        presentation_dict = presentation.model_dump()

        if presentation.voice.enabled and presentation.voice.narration:
            tts_service.job_status[audio_filename] = "pending"
            start_background_speech(
                text=presentation.voice.narration,
                language=state.language,
                filename=audio_filename,
            )
            audio_url = f"/voice/audio/{audio_filename}"

    # 8. Update persistent session
    
    persist_state = {
        "current_concept": next_step["concept"] or state.current_concept,
        "mastery_score": state.mastery_score,
        "difficulty_level": state.difficulty_level,
        "teaching_strategy": state.teaching_strategy,
        "current_phase": state.current_phase,
        "last_question": next_step["question"] or state.last_question,
        "last_answer": state.last_answer,
        "last_evaluation": state.last_evaluation,
        "misconceptions": state.misconceptions,
        "concepts_struggling": state.concepts_struggling,
        "concepts_completed": state.concepts_completed,
        "needs_reteaching": state.needs_reteaching,
        "attempt_count": state.attempt_count,
        "assessment_active": state.assessment_active,
        "concept_steps_total": state.concept_steps_total,
        "concept_steps_current": state.concept_steps_current,
        "concept_history": state.concept_history,
        "planned_concepts": state.planned_concepts,
        "current_concept_index": state.current_concept_index,
        "teaching": next_step["teaching"],
        "presentation": presentation_dict,
        "audio_url": audio_url,
    }

    if next_step["action"] == "completed":

        learning_service.update_session(
            db=db,
            session=session,
            concept_id=None,
            step="completed",
            status="completed",
            state_data=persist_state
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
                state_data=persist_state
            )
    else:
        # action == "completed" or no concept
        learning_service.update_session(
            db=db,
            session=session,
            concept_id=None,
            step="completed" if next_step["action"] == "completed" else "question",
            status="completed" if next_step["action"] == "completed" else "active",
            state_data=persist_state
        )
        
    EventService.log_event(
        db, session.id, state.student_id, "teacher_message", "teacher", 
        {"text": next_step["teaching"], "concept": next_step.get("concept", state.current_concept)}, 
        session.lesson_id, session.current_concept_id
    )
    
    if presentation_dict and presentation_dict.get("blackboard") and presentation_dict["blackboard"].get("enabled") and presentation_dict["blackboard"].get("visual_url"):
        EventService.log_event(
            db, session.id, state.student_id, "visual_presented", "system", 
            {
                "visual_source": presentation_dict["blackboard"].get("visual_source"),
                "visual_type": presentation_dict["blackboard"].get("visual_type"),
                "visual_url": presentation_dict["blackboard"].get("visual_url"),
                "concept": next_step.get("concept", state.current_concept)
            }, session.lesson_id, session.current_concept_id
        )
        
    if next_step.get("question"):
        EventService.log_event(
            db, session.id, state.student_id, "question_presented", "teacher", 
            {"text": next_step["question"]}, 
            session.lesson_id, session.current_concept_id
        )
        
    if next_step["action"] == "completed":
        EventService.log_event(db, session.id, state.student_id, "lesson_completed", "system", {}, session.lesson_id, session.current_concept_id)
        EventService.log_event(db, session.id, state.student_id, "session_completed", "system", {}, session.lesson_id, session.current_concept_id)

    return {
        "session_id": session.id,
        "evaluation": evaluation.summary(),
        "action": next_step["action"],
        "concept": next_step["concept"],
        "teaching": next_step["teaching"],
        "question": next_step["question"],
        "presentation": presentation_dict,
        "audio_url": audio_url,
        "state": state.summary(),
        "interaction_type": "assessment",
        "assessment_active": state.assessment_active,
    }

from fastapi.responses import StreamingResponse
import json
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eduva.stream")
logger.setLevel(logging.INFO)

@router.post("/answer/stream")
async def submit_answer_stream(
    request: AnswerRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    logger.info("[EDUVA][Latency] REQUEST_START")
    start_time = time.time()
    logger.info(f"[EDUVA][Stream] submit_answer_stream request_start for session {request.session_id}")

    session = db.get(TeachingSession, request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Teaching session not found")

    lesson = db.get(Lesson, session.lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
        
    student = db.get(Student, session.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

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
        assessment_active=state_data.get("assessment_active", False),
        recent_clarifications=state_data.get("recent_clarifications", []),
        concept_steps_total=state_data.get("concept_steps_total", 2),
        concept_steps_current=state_data.get("concept_steps_current", 1),
        concept_history=state_data.get("concept_history", []),
        planned_concepts=state_data.get("planned_concepts", []),
        current_concept_index=state_data.get("current_concept_index", 0),
        teaching_cursor=state_data.get("teaching_cursor", None),
    )

    language = state.language or student.preferred_language

    intent_task = asyncio.create_task(teacher_engine.classify_intent(state, request.answer))

    current_concept_title = state.current_concept or lesson.topic
    memories = MemoryService.get_relevant_memory_for_concept(db, state.student_id, current_concept_title)
    learner_memory_context = MemoryService.format_memory_context(memories)

    concept = (
        db.query(Concept)
        .filter(
            Concept.lesson_id == session.lesson_id,
            Concept.title == current_concept_title,
        )
        .first()
    )

    interaction_type = await intent_task
    
    # Log student message based on intent
    if interaction_type == "clarification":
        EventService.log_event(db, session.id, state.student_id, "student_question", "student", {"text": request.answer}, session.lesson_id, session.current_concept_id)
        EventService.log_event(db, session.id, state.student_id, "clarification_requested", "student", {}, session.lesson_id, session.current_concept_id)
    elif interaction_type in ("continue", "continue_step"):
        EventService.log_event(db, session.id, state.student_id, "student_message", "student", {"text": request.answer}, session.lesson_id, session.current_concept_id)
    else:
        # assessment
        EventService.log_event(db, session.id, state.student_id, "answer_submitted", "student", {"text": request.answer}, session.lesson_id, session.current_concept_id)

    if interaction_type == "continue":
        state.recent_clarifications = []
        if state.assessment_active:
            final_response = {
                "session_id": session.id,
                "evaluation": None,
                "action": "assessment_reminder",
                "concept": state.current_concept,
                "teaching": f"NARRATION: Please answer the understanding-check question before we continue.\n\nQUESTION: {state.last_question}",
                "question": state.last_question,
                "presentation": None,
                "audio_url": None,
                "state": state.summary(),
                "interaction_type": "assessment",
                "assessment_active": True,
            }
            async def fast_generator():
                yield f"data: {json.dumps({'type': 'complete', 'data': final_response})}\n\n"
            return StreamingResponse(fast_generator(), media_type="text/event-stream")
        elif state.concept_steps_current < state.concept_steps_total:
            interaction_type = "continue_step"
        else:
            interaction_type = "clarification"

    teaching_context = None
    if lesson.document_id is not None and interaction_type in ("clarification", "continue_step"):
        context_query = state.current_concept or state.topic
            
        logger.info("[EDUVA][Latency] RAG_START")
        rag_start = time.time()
        teaching_context = await retrieve_relevant_chunks(
            db=db,
            question=context_query,
            document_id=lesson.document_id,
            limit=5,
        )
        rag_time = time.time() - rag_start
        logger.info(f"[EDUVA][Latency] RAG_COMPLETE in {rag_time:.2f}s")
        logger.info(f"[EDUVA][RAG] retrieval latency: {rag_time:.2f}s")

    if interaction_type == "clarification":
        # Path A: Clarification
        async def event_generator():
            try:
                gen = await teacher_engine.clarify_stream(
                    state=state,
                    message=request.answer,
                    context=teaching_context,
                )
                
                final_data = None
                teaching_text = ""
                
                logger.info("[EDUVA][Latency] LLM_START (Clarification)")
                llm_start = time.time()
                first_token = True
                
                narration_streamer = NarrationStreamer()
                text_chunker = TextChunker()
                chunk_index = 0
                event_id = f"lesson_{session.id}_event_{uuid4().hex[:8]}"
                
                async for event in gen:
                    if event["type"] == "teaching_chunk":
                        if first_token:
                            logger.info(f"[EDUVA][Latency] LLM_FIRST_TOKEN in {time.time() - llm_start:.2f}s")
                            first_token = False
                        teaching_text += event["content"]
                        yield f"data: {json.dumps({'type': 'teaching_chunk', 'content': event['content']})}\n\n"
                        
                        # Streaming TTS chunking
                        new_narr = narration_streamer.feed(event["content"])
                        if new_narr:
                            chunks = text_chunker.feed(new_narr)
                            for chunk in chunks:
                                chunk_filename = f"{event_id}_{chunk_index}.mp3"
                                start_background_speech(chunk, language, chunk_filename)
                                unit_data = {
                                    'type': 'presentation_unit',
                                    'event_id': event_id,
                                    'chunk_id': f"{event_id}_chunk_{chunk_index}",
                                    'sequence': chunk_index,
                                    'text': chunk,
                                    'audio_url': f'/voice/audio/{chunk_filename}',
                                    'status': 'pending'
                                }
                                yield f"data: {json.dumps(unit_data)}\n\n"
                                chunk_index += 1
                                
                    elif event["type"] == "complete":
                        final_data = event["data"]
                        
                # Flush remaining chunks
                new_narr = narration_streamer.flush()
                if new_narr:
                    chunks = text_chunker.feed(new_narr)
                    chunks.extend(text_chunker.flush())
                else:
                    chunks = text_chunker.flush()
                    
                for chunk in chunks:
                    chunk_filename = f"{event_id}_{chunk_index}.mp3"
                    start_background_speech(chunk, language, chunk_filename)
                    unit_data = {
                        'type': 'presentation_unit',
                        'event_id': event_id,
                        'chunk_id': f"{event_id}_chunk_{chunk_index}",
                        'sequence': chunk_index,
                        'text': chunk,
                        'audio_url': f'/voice/audio/{chunk_filename}',
                        'status': 'pending'
                    }
                    yield f"data: {json.dumps(unit_data)}\n\n"
                    chunk_index += 1
                        
                llm_time = time.time() - llm_start
                logger.info(f"[EDUVA][Latency] LLM_COMPLETE in {llm_time:.2f}s")
                
                narration, blackboard, directive, pdf_visual_id = parse_teaching_response(teaching_text)
                def pdf_visual_cb(subject: str) -> Optional[dict]:
                    if not session.document_id: return None
                    from app.visuals.retriever import get_candidate_visuals
                    cands = get_candidate_visuals(db=db, document_id=session.document_id, concept=subject)
                    return cands[0] if cands else None

                presentation = await orchestrator.orchestrate(
                    teacher_state=state,
                    narration=narration,
                    blackboard_content=blackboard,
                    visual_directive=directive,
                    teaching_context=teaching_context,
                    fetch_pdf_visual_cb=pdf_visual_cb
                )
                presentation_dict = presentation.model_dump()
                
                audio_url = None # We stream chunks now, so final url is None
                
                final_response = {
                    "session_id": session.id,
                    "evaluation": None,
                    "action": "clarification",
                    "concept": state.current_concept,
                    "teaching": teaching_text,
                    "question": state.last_question,
                    "presentation": presentation_dict,
                    "audio_url": audio_url,
                    "state": state.summary(),
                    "interaction_type": "clarification",
                    "assessment_active": state.assessment_active,
                }
                
                state.recent_clarifications.append({"role": "user", "content": request.answer})
                state.recent_clarifications.append({"role": "assistant", "content": teaching_text})
                
                # Keep only the last MAX_RECENT_CLARIFICATIONS messages
                MAX_RECENT_CLARIFICATIONS = 6
                state.recent_clarifications = state.recent_clarifications[-MAX_RECENT_CLARIFICATIONS:]
                
                # Persist the state
                learning_service.update_session(
                    db=db,
                    session=session,
                    concept_id=session.current_concept_id,
                    step=session.current_step or "clarification",
                    state_data=state.summary()
                )
                
                # Log teacher clarification response
                EventService.log_event(
                    db, session.id, state.student_id, "clarification_answered", "teacher", 
                    {"text": teaching_text, "concept": state.current_concept}, 
                    session.lesson_id, session.current_concept_id
                )
                if presentation and presentation.blackboard and presentation.blackboard.enabled and presentation.blackboard.visual_url:
                    EventService.log_event(
                        db, session.id, state.student_id, "visual_presented", "system", 
                        {
                            "visual_source": presentation.blackboard.visual_source,
                            "visual_type": presentation.blackboard.visual_type,
                            "visual_url": presentation.blackboard.visual_url,
                            "concept": state.current_concept
                        }, session.lesson_id, session.current_concept_id
                    )
                
                logger.info(f"[EDUVA][Latency] SSE_COMPLETE in {time.time() - start_time:.2f}s")
                
                yield f"data: {json.dumps({'type': 'complete', 'data': final_response})}\n\n"
            except Exception as e:
                logger.error(f"[EDUVA][Stream] Error in submit_answer_stream (clarification): {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    if interaction_type == "continue_step":
        # Path C: Continue Step
        async def event_generator():
            try:
                gen = await teacher_engine.continue_step_stream(
                    state=state,
                    teaching_context=teaching_context,
                    learner_memory_context=learner_memory_context,
                )
                
                final_data = None
                teaching_text = ""
                
                logger.info("[EDUVA][Latency] LLM_START (Continue)")
                llm_start = time.time()
                first_token = True
                
                narration_streamer = NarrationStreamer()
                text_chunker = TextChunker()
                chunk_index = 0
                event_id = f"lesson_{session.id}_event_{uuid4().hex[:8]}"
                
                async for event in gen:
                    if event["type"] == "teaching_chunk":
                        if first_token:
                            logger.info(f"[EDUVA][Latency] LLM_FIRST_TOKEN in {time.time() - llm_start:.2f}s")
                            first_token = False
                        teaching_text += event["content"]
                        yield f"data: {json.dumps({'type': 'teaching_chunk', 'content': event['content']})}\n\n"
                        
                        # Streaming TTS chunking
                        new_narr = narration_streamer.feed(event["content"])
                        if new_narr:
                            chunks = text_chunker.feed(new_narr)
                            for chunk in chunks:
                                chunk_filename = f"lesson_{session.id}_continue_{uuid4().hex[:8]}_{chunk_index}.mp3"
                                start_background_speech(chunk, language, chunk_filename)
                                unit_data = {
                                    'type': 'presentation_unit',
                                    'event_id': event_id,
                                    'chunk_id': f"{event_id}_chunk_{chunk_index}",
                                    'sequence': chunk_index,
                                    'text': chunk,
                                    'audio_url': f'/voice/audio/{chunk_filename}',
                                    'status': 'pending'
                                }
                                yield f"data: {json.dumps(unit_data)}\n\n"
                                chunk_index += 1
                                
                    elif event["type"] == "complete":
                        final_data = event["data"]
                        
                # Flush remaining chunks
                new_narr = narration_streamer.flush()
                if new_narr:
                    chunks = text_chunker.feed(new_narr)
                    chunks.extend(text_chunker.flush())
                    for chunk in chunks:
                        chunk_filename = f"lesson_{session.id}_continue_{uuid4().hex[:8]}_{chunk_index}.mp3"
                        start_background_speech(chunk, language, chunk_filename)
                        unit_data = {
                            'type': 'presentation_unit',
                            'event_id': event_id,
                            'chunk_id': f"{event_id}_chunk_{chunk_index}",
                            'sequence': chunk_index,
                            'text': chunk,
                            'audio_url': f'/voice/audio/{chunk_filename}',
                            'status': 'pending'
                        }
                        yield f"data: {json.dumps(unit_data)}\n\n"
                        chunk_index += 1
                        
                llm_time = time.time() - llm_start
                logger.info(f"[EDUVA][Latency] LLM_COMPLETE in {llm_time:.2f}s")
                
                narration, blackboard, directive, pdf_visual_id = parse_teaching_response(teaching_text)
                def pdf_visual_cb(subject: str) -> Optional[dict]:
                    if not session.document_id: return None
                    from app.visuals.retriever import get_candidate_visuals
                    cands = get_candidate_visuals(db=db, document_id=session.document_id, concept=subject)
                    return cands[0] if cands else None

                presentation = await orchestrator.orchestrate(
                    teacher_state=state,
                    narration=narration,
                    blackboard_content=blackboard,
                    visual_directive=directive,
                    teaching_context=None,
                    fetch_pdf_visual_cb=pdf_visual_cb
                )
                presentation_dict = presentation.model_dump()
                
                audio_url = None
                
                final_response = {
                    "session_id": session.id,
                    "evaluation": None,
                    "action": "continue_step",
                    "concept": state.current_concept,
                    "teaching": teaching_text,
                    "question": state.last_question,
                    "presentation": presentation_dict,
                    "audio_url": audio_url,
                    "state": state.summary(),
                    "interaction_type": "continue_step",
                    "assessment_active": state.assessment_active,
                }
                
                # Persist the state
                learning_service.update_session(
                    db=db,
                    session=session,
                    concept_id=session.current_concept_id,
                    step=session.current_step or "continue",
                    state_data=state.summary()
                )
                
                # Log teacher message
                EventService.log_event(
                    db, session.id, state.student_id, "teacher_message", "teacher", 
                    {"text": teaching_text, "concept": state.current_concept}, 
                    session.lesson_id, session.current_concept_id
                )
                if presentation and presentation.blackboard and presentation.blackboard.enabled and presentation.blackboard.visual_url:
                    EventService.log_event(
                        db, session.id, state.student_id, "visual_presented", "system", 
                        {
                            "visual_source": presentation.blackboard.visual_source,
                            "visual_type": presentation.blackboard.visual_type,
                            "visual_url": presentation.blackboard.visual_url,
                            "concept": state.current_concept
                        }, session.lesson_id, session.current_concept_id
                    )
                
                logger.info(f"[EDUVA][Latency] SSE_COMPLETE in {time.time() - start_time:.2f}s")
                
                yield f"data: {json.dumps({'type': 'complete', 'data': final_response})}\n\n"
            except Exception as e:
                logger.error(f"[EDUVA][Stream] Error in submit_answer_stream (continue_step): {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    # Path B: Assessment Answer
    # 1. Update state based on answer
    logger.info("[EDUVA][Latency] TEACHING_PARSE_START (Evaluation)")
    eval_start = time.time()
    result = await teacher_engine.answer(state, request.answer)
    evaluation = result["evaluation"]
    logger.info("[EDUVA][Latency] TEACHING_PARSE_COMPLETE (Evaluation)")
    eval_time = time.time() - eval_start
    logger.info(f"[EDUVA][Latency] EVALUATION_COMPLETE in {eval_time:.2f}s")
    
    if evaluation.correctness == "retry_required":
        state.assessment_active = True
        state.attempt_count = max(0, state.attempt_count - 1)
        
        async def fast_fallback_generator():
            final_response = {
                "session_id": session.id,
                "evaluation": evaluation.summary(),
                "action": "assessment_retry",
                "concept": state.current_concept,
                "teaching": f"NARRATION: {evaluation.feedback}\n\nQUESTION: {state.last_question}",
                "question": state.last_question,
                "presentation": None,
                "audio_url": None,
                "state": state.summary(),
                "interaction_type": "assessment",
                "assessment_active": True,
            }
            yield f"data: {json.dumps({'type': 'teaching_chunk', 'content': evaluation.feedback})}\n\n"
            yield f"data: {json.dumps({'type': 'complete', 'data': final_response})}\n\n"
        
        return StreamingResponse(fast_fallback_generator(), media_type="text/event-stream")


    if concept is None:
        raise HTTPException(status_code=404, detail="Current concept not found")

    learning_service.save_attempt(
        db=db, session=session, concept=concept,
        question=state.last_question or "", student_answer=request.answer,
        is_correct=evaluation.correctness == "correct",
        evaluation=evaluation.feedback, misconception=evaluation.misconception,
    )
    
    EventService.log_event(
        db, session.id, state.student_id, "answer_evaluated", "system", 
        {"correctness": evaluation.correctness, "feedback": evaluation.feedback}, 
        session.lesson_id, concept.id
    )
    if evaluation.misconception:
        EventService.log_event(
            db, session.id, state.student_id, "misconception_detected", "system", 
            {"misconception": evaluation.misconception}, 
            session.lesson_id, concept.id
        )
    
    learning_service.update_concept_mastery(db=db, concept=concept, mastery_score=evaluation.score)
    EventService.log_event(
        db, session.id, state.student_id, "mastery_updated", "system", 
        {"score": evaluation.score}, 
        session.lesson_id, concept.id
    )

    # 6b. Roadmap completion evaluation
    completion_eval = RoadmapService.evaluate_concept_completion(db, state.student_id, concept, state.mastery_score)
    roadmap_status = completion_eval["status"]
    
    # Update TeacherState Adaptation
    teacher_engine.adaptation.adapt(state, roadmap_status)

    next_concept_title = None
    if roadmap_status == "complete":
        next_db_concept = RoadmapService.get_next_concept(db, state.student_id, session.lesson_id, concept)
        if next_db_concept:
            next_concept_title = next_db_concept.title

    if lesson.document_id is not None:
        if state.needs_reteaching:
            context_query = state.current_concept or state.topic
        else:
            context_query = next_concept_title or state.topic
            
        logger.info("[EDUVA][Latency] RAG_START (Assessment)")
        rag_start = time.time()
        teaching_context = await retrieve_relevant_chunks(
            db=db,
            question=context_query,
            document_id=lesson.document_id,
            limit=5,
        )
        rag_time = time.time() - rag_start
        logger.info(f"[EDUVA][Latency] RAG_COMPLETE in {rag_time:.2f}s")

    roadmap_context = RoadmapService.format_roadmap_context(db, state.student_id, session.lesson_id, concept)
    if teaching_context is None:
        teaching_context = [roadmap_context]
    else:
        teaching_context.insert(0, roadmap_context)

    async def event_generator():
        try:
            # Yield early presentation so new video can mount immediately if subtopic changed
            def pdf_visual_cb(subject: str) -> Optional[dict]:
                if not session.document_id: return None
                from app.visuals.retriever import get_candidate_visuals
                cands = get_candidate_visuals(db=db, document_id=session.document_id, concept=subject)
                return cands[0] if cands else None

            partial_presentation = await orchestrator.orchestrate(
                teacher_state=state,
                narration="",
                blackboard_content="",
                visual_directive=None,
                fetch_pdf_visual_cb=pdf_visual_cb
            )
            yield f"data: {json.dumps({'type': 'presentation', 'data': partial_presentation.model_dump()})}\n\n"

            gen = await teacher_engine.next_step_stream(
                state=state,
                teaching_context=teaching_context,
                learner_memory_context=learner_memory_context,
                next_concept_title=next_concept_title,
            )
            
            final_data = None
            teaching_text = ""
            
            logger.info("[EDUVA][Latency] LLM_START")
            llm_start = time.time()
            first_token = True
            
            narration_streamer = NarrationStreamer()
            text_chunker = TextChunker()
            chunk_index = 0
            
            async for event in gen:
                if event["type"] == "teaching_chunk":
                    if first_token:
                        logger.info(f"[EDUVA][Latency] LLM_FIRST_TOKEN in {time.time() - llm_start:.2f}s")
                        first_token = False
                    teaching_text += event["content"]
                    yield f"data: {json.dumps({'type': 'teaching_chunk', 'content': event['content']})}\n\n"
                    
                    # Streaming TTS chunking
                    new_narr = narration_streamer.feed(event["content"])
                    if new_narr:
                        chunks = text_chunker.feed(new_narr)
                        for chunk in chunks:
                            chunk_filename = f"lesson_{session.id}_answer_{state.attempt_count}_{uuid4().hex[:8]}_{chunk_index}.mp3"
                            start_background_speech(chunk, language, chunk_filename)
                            yield f"data: {json.dumps({'type': 'audio_chunk', 'url': f'/voice/audio/{chunk_filename}'})}\n\n"
                            chunk_index += 1
                            
                elif event["type"] == "complete":
                    final_data = event["data"]
                    
            # Flush remaining chunks
            new_narr = narration_streamer.flush()
            if new_narr:
                chunks = text_chunker.feed(new_narr)
                chunks.extend(text_chunker.flush())
                for chunk in chunks:
                    chunk_filename = f"lesson_{session.id}_answer_{state.attempt_count}_{uuid4().hex[:8]}_{chunk_index}.mp3"
                    start_background_speech(chunk, language, chunk_filename)
                    yield f"data: {json.dumps({'type': 'audio_chunk', 'url': f'/voice/audio/{chunk_filename}'})}\n\n"
                    chunk_index += 1
                    
            llm_time = time.time() - llm_start
            logger.info(f"[EDUVA][Latency] LLM_COMPLETE in {llm_time:.2f}s")
            logger.info(f"[EDUVA][Groq] Full generation latency: {llm_time:.2f}s")
            
            narration, blackboard, directive, pdf_visual_id = parse_teaching_response(teaching_text)
            def pdf_visual_cb(subject: str) -> Optional[dict]:
                if not session.document_id: return None
                from app.visuals.retriever import get_candidate_visuals
                cands = get_candidate_visuals(db=db, document_id=session.document_id, concept=subject)
                return cands[0] if cands else None

            presentation = await orchestrator.orchestrate(
                teacher_state=state,
                narration=narration,
                blackboard_content=blackboard,
                visual_directive=directive,
                teaching_context=teaching_context,
                fetch_pdf_visual_cb=pdf_visual_cb
            )
            presentation_dict = presentation.model_dump()
            
            audio_url = None
            
            logger.info("[EDUVA][Latency] DB_START")
            db_start = time.time()
            
            persist_state = {
                "current_concept": final_data["concept"] or state.current_concept,
                "mastery_score": state.mastery_score,
                "difficulty_level": state.difficulty_level,
                "teaching_strategy": state.teaching_strategy,
                "current_phase": state.current_phase,
                "last_question": final_data.get("question") or state.last_question,
                "last_answer": state.last_answer,
                "last_evaluation": state.last_evaluation,
                "misconceptions": state.misconceptions,
                "concepts_struggling": state.concepts_struggling,
                "concepts_completed": state.concepts_completed,
                "needs_reteaching": state.needs_reteaching,
                "attempt_count": state.attempt_count,
                "assessment_active": state.assessment_active,
                "concept_steps_total": state.concept_steps_total,
                "concept_steps_current": state.concept_steps_current,
                "concept_history": state.concept_history,
                "planned_concepts": state.planned_concepts,
                "current_concept_index": state.current_concept_index,
                "teaching": teaching_text,
                "presentation": presentation_dict,
                "audio_url": audio_url,
            }

            if final_data["action"] == "completed":
                learning_service.update_session(
                    db=db, session=session, concept_id=None,
                    step="completed", status="completed", state_data=persist_state
                )
            elif final_data["concept"]:
                next_concept_db = db.query(Concept).filter(
                    Concept.lesson_id == session.lesson_id,
                    Concept.title == final_data["concept"],
                ).first()
                if next_concept_db:
                    learning_service.update_session(
                        db=db, session=session, concept_id=next_concept_db.id,
                        step="question", state_data=persist_state
                    )
            else:
                learning_service.update_session(
                    db=db, session=session, concept_id=None,
                    step="completed" if final_data["action"] == "completed" else "question",
                    status="completed" if final_data["action"] == "completed" else "active",
                    state_data=persist_state
                )
                
            EventService.log_event(
                db, session.id, state.student_id, "teacher_message", "teacher", 
                {"text": teaching_text, "concept": final_data.get("concept", state.current_concept)}, 
                session.lesson_id, session.current_concept_id
            )
            
            if presentation and presentation.blackboard and presentation.blackboard.enabled and presentation.blackboard.visual_url:
                EventService.log_event(
                    db, session.id, state.student_id, "visual_presented", "system", 
                    {
                        "visual_source": presentation.blackboard.visual_source,
                        "visual_type": presentation.blackboard.visual_type,
                        "visual_url": presentation.blackboard.visual_url,
                        "concept": final_data.get("concept", state.current_concept)
                    }, session.lesson_id, session.current_concept_id
                )
                
            if final_data.get("question"):
                EventService.log_event(
                    db, session.id, state.student_id, "question_presented", "teacher", 
                    {"text": final_data["question"]}, 
                    session.lesson_id, session.current_concept_id
                )
                
            if final_data["action"] == "completed":
                EventService.log_event(db, session.id, state.student_id, "lesson_completed", "system", {}, session.lesson_id, session.current_concept_id)
                EventService.log_event(db, session.id, state.student_id, "session_completed", "system", {}, session.lesson_id, session.current_concept_id)
                
            db_time = time.time() - db_start
            logger.info(f"[EDUVA][Latency] DB_COMPLETE in {db_time:.2f}s")
            logger.info(f"[EDUVA][DB] Persistence latency: {db_time:.2f}s")
            
            final_response = {
                "session_id": session.id,
                "evaluation": evaluation.summary(),
                "action": final_data["action"],
                "concept": final_data["concept"],
                "teaching": teaching_text,
                "question": final_data.get("question", ""),
                "presentation": presentation_dict,
                "audio_url": audio_url,
                "state": state.summary(),
                "interaction_type": "assessment",
                "assessment_active": state.assessment_active,
            }
            
            logger.info(f"[EDUVA][Latency] SSE_COMPLETE in {time.time() - start_time:.2f}s")
            logger.info(f"[EDUVA][Stream] submit_answer_stream complete in {time.time() - start_time:.2f}s")
            
            yield f"data: {json.dumps({'type': 'complete', 'data': final_response})}\n\n"
        except Exception as e:
            logger.error(f"[EDUVA][Stream] Error in submit_answer_stream: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

