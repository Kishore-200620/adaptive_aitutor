from typing import Any, List, Optional
import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.event import SessionEvent
from app.models.session import TeachingSession
from app.services.memory_service import MemoryService

logger = logging.getLogger("eduva.events")

class EventService:
    @staticmethod
    def log_event(
        db: Session,
        session_id: int,
        student_id: int,
        event_type: str,
        source: str,
        payload: dict[str, Any],
        lesson_id: Optional[int] = None,
        concept_id: Optional[int] = None,
    ) -> Optional[SessionEvent]:
        """
        Safely logs a session event. Uses a row-level lock (FOR UPDATE) on the 
        TeachingSession to calculate a race-safe sequence_number.
        """
        try:
            # 1. Lock the session row to prevent race conditions
            # SQLite does not support FOR UPDATE in the same way Postgres does without proper isolation, 
            # but SQLAlchemy handles it or ignores it gracefully depending on dialect. 
            # We use with_for_update() to signal intent.
            session_row = db.query(TeachingSession).with_for_update().filter(TeachingSession.id == session_id).first()
            
            if not session_row:
                logger.error(f"[EventService] Could not lock session {session_id} to log event {event_type}.")
                return None

            # 2. Get max sequence_number
            max_seq = db.query(SessionEvent.sequence_number).filter(
                SessionEvent.session_id == session_id
            ).order_by(SessionEvent.sequence_number.desc()).limit(1).scalar()
            
            max_seq = max_seq or 0
            next_seq = max_seq + 1

            # 3. Create the event
            new_event = SessionEvent(
                session_id=session_id,
                student_id=student_id,
                lesson_id=lesson_id,
                concept_id=concept_id,
                sequence_number=next_seq,
                event_type=event_type,
                source=source,
                payload=payload
            )
            
            db.add(new_event)
            db.commit()
            
            logger.info(f"[EventService] Logged {event_type} (seq {next_seq}) for session {session_id}")
            
            # Fire Phase 43 memory extraction synchronously, but wrapped in try/except to isolate failures
            try:
                MemoryService.extract_memory_from_event(db, new_event)
            except Exception as e:
                logger.error(f"[EventService] Memory extraction failed for event {new_event.id}: {e}")
                
            return new_event
            
        except Exception as e:
            # Do NOT break the main flow. Just log the error.
            logger.error(f"[EventService] Failed to log event {event_type} for session {session_id}: {e}")
            return None

    @staticmethod
    def get_session_events(
        db: Session,
        session_id: int,
        limit: int = 100,
        offset: int = 0
    ) -> List[SessionEvent]:
        """
        Retrieves events for a session, strictly ordered by sequence_number ascending.
        """
        return db.query(SessionEvent).filter(
            SessionEvent.session_id == session_id
        ).order_by(
            SessionEvent.sequence_number.asc()
        ).limit(limit).offset(offset).all()
