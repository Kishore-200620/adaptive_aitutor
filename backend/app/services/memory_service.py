import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, update

from app.models.event import SessionEvent
from app.models.memory import LearnerMemory
from app.models.concept import Concept

logger = logging.getLogger("eduva.memory")


class MemoryService:

    @staticmethod
    def normalize_concept_key(concept_name: str) -> str:
        """
        Normalizes a concept name for cross-lesson identity.
        e.g., 'Resistors ' -> 'resistors'
        """
        if not concept_name:
            return ""
        return concept_name.lower().strip()

    @staticmethod
    def _get_concept_key_from_event(db: Session, event: SessionEvent) -> Optional[str]:
        # Try to extract from payload if present
        if event.payload and "concept" in event.payload:
            return MemoryService.normalize_concept_key(event.payload["concept"])

        # Otherwise look up the concept_id if provided
        if event.concept_id:
            concept = db.get(Concept, event.concept_id)
            if concept:
                return MemoryService.normalize_concept_key(concept.title)
                
        return None

    @staticmethod
    def extract_memory_from_event(db: Session, event: SessionEvent) -> None:
        """
        Derives long-term memory from a verified structured event.
        Called synchronously after EventService.log_event() commits successfully.
        Exceptions must be caught by the caller to avoid breaking teaching.
        """
        if not event.student_id:
            return

        concept_key = MemoryService._get_concept_key_from_event(db, event)

        if event.event_type == "misconception_detected":
            misconception_text = event.payload.get("misconception")
            if misconception_text:
                MemoryService._handle_misconception_detected(db, event, concept_key, misconception_text)

        elif event.event_type == "mastery_updated":
            score = event.payload.get("score")
            if score is not None:
                MemoryService._handle_mastery_updated(db, event, concept_key, float(score))

        elif event.event_type == "student_question":
            # Just an example for preference detection if they ask for visuals, 
            # we could track it, but we'll stick to mastery/misconception for Phase 43 primarily 
            # to avoid over-inferring as instructed.
            pass

    @staticmethod
    def _handle_misconception_detected(db: Session, event: SessionEvent, concept_key: str, misconception_text: str):
        """
        Upsert a misconception memory for the student.
        """
        # Deduplication Rule: Same student, memory_type, concept_key, and exact content.
        existing_memory = db.query(LearnerMemory).filter(
            LearnerMemory.student_id == event.student_id,
            LearnerMemory.memory_type == "misconception",
            LearnerMemory.concept_key == concept_key,
            LearnerMemory.content == misconception_text
        ).first()

        if existing_memory:
            # Update existing
            existing_memory.evidence_count += 1
            existing_memory.confidence = min(0.95, existing_memory.confidence + 0.15)
            existing_memory.last_observed_at = datetime.utcnow()
            existing_memory.source_event_id = event.id
            db.commit()
            logger.info(f"[MemoryService] Updated misconception for student {event.student_id}: '{misconception_text}'")
        else:
            # Create new
            new_memory = LearnerMemory(
                student_id=event.student_id,
                concept_id=event.concept_id,
                concept_key=concept_key,
                memory_type="misconception",
                content=misconception_text,
                confidence=0.5,
                evidence_count=1,
                source_event_id=event.id
            )
            db.add(new_memory)
            db.commit()
            logger.info(f"[MemoryService] Created new misconception for student {event.student_id}: '{misconception_text}'")

    @staticmethod
    def _handle_mastery_updated(db: Session, event: SessionEvent, concept_key: str, score: float):
        """
        Upsert a concept mastery memory, and handle contradiction of old misconceptions.
        """
        if not concept_key:
            return

        # 1. Update or create mastery memory
        existing_mastery = db.query(LearnerMemory).filter(
            LearnerMemory.student_id == event.student_id,
            LearnerMemory.memory_type == "concept_mastery",
            LearnerMemory.concept_key == concept_key
        ).first()

        if existing_mastery:
            existing_mastery.evidence_count += 1
            # Maintain confidence but update metadata with the true mastery score
            existing_mastery.confidence = min(0.95, existing_mastery.confidence + 0.05)
            existing_mastery.last_observed_at = datetime.utcnow()
            existing_mastery.source_event_id = event.id
            if existing_mastery.metadata_json is None:
                existing_mastery.metadata_json = {}
            existing_mastery.metadata_json["mastery_score"] = score
            db.commit()
        else:
            new_mastery = LearnerMemory(
                student_id=event.student_id,
                concept_id=event.concept_id,
                concept_key=concept_key,
                memory_type="concept_mastery",
                content=f"Mastery for {concept_key}",
                confidence=0.5,
                evidence_count=1,
                source_event_id=event.id,
                metadata_json={"mastery_score": score}
            )
            db.add(new_mastery)
            db.commit()

        # 2. Contradiction handling: if score is high, reduce confidence in past misconceptions
        if score >= 0.8:
            misconceptions = db.query(LearnerMemory).filter(
                LearnerMemory.student_id == event.student_id,
                LearnerMemory.memory_type == "misconception",
                LearnerMemory.concept_key == concept_key
            ).all()

            for mem in misconceptions:
                if mem.confidence > 0:
                    mem.confidence = max(0.0, mem.confidence - 0.2)
                    mem.updated_at = datetime.utcnow()
            db.commit()

    @staticmethod
    def get_student_memory(db: Session, student_id: int) -> List[LearnerMemory]:
        return db.query(LearnerMemory).filter(LearnerMemory.student_id == student_id).all()

    @staticmethod
    def get_relevant_memory_for_concept(db: Session, student_id: int, concept_name: str, limit: int = 5) -> List[LearnerMemory]:
        """
        Retrieves top relevant memories for a concept, sorted by confidence.
        """
        concept_key = MemoryService.normalize_concept_key(concept_name)
        
        memories = db.query(LearnerMemory).filter(
            LearnerMemory.student_id == student_id,
            LearnerMemory.concept_key == concept_key,
            LearnerMemory.confidence > 0.3  # only return confident/relevant memories
        ).order_by(LearnerMemory.confidence.desc()).limit(limit).all()

        return memories

    @staticmethod
    def format_memory_context(memories: List[LearnerMemory]) -> str:
        if not memories:
            return ""
        
        context = "LONG-TERM LEARNER MEMORY:\n"
        context += "Use this as contextual guidance. Verify it against current learner evidence. Current evidence overrides historical memory.\n"
        for mem in memories:
            context += f"- [{mem.memory_type}] {mem.content} (confidence: {mem.confidence:.2f})\n"
        
        return context
