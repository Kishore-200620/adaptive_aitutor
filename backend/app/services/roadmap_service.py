import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.concept import Concept
from app.models.lesson import Lesson
from app.models.progress import StudentConceptProgress
from app.services.memory_service import MemoryService

logger = logging.getLogger("eduva.roadmap")

class RoadmapService:

    @staticmethod
    def get_student_progress(db: Session, student_id: int, concept_id: int) -> StudentConceptProgress:
        """Get or create the progress record for a student on a specific concept."""
        progress = db.query(StudentConceptProgress).filter(
            StudentConceptProgress.student_id == student_id,
            StudentConceptProgress.concept_id == concept_id
        ).first()

        if not progress:
            progress = StudentConceptProgress(
                student_id=student_id,
                concept_id=concept_id,
                status="not_started"
            )
            db.add(progress)
            db.commit()
            db.refresh(progress)

        return progress

    @staticmethod
    def evaluate_concept_completion(
        db: Session,
        student_id: int,
        concept: Concept,
        mastery_score: float
    ) -> Dict[str, Any]:
        """
        Evaluate if a concept is complete based on:
        - Authoritative mastery score
        - Unresolved misconceptions from learner memory
        """
        result = {
            "concept_key": concept.title,
            "concept_id": concept.id,
            "status": "incomplete",
            "reason": ""
        }

        # 1. Authoritative mastery check (reuse the 0.8 pedagogical threshold)
        mastery_sufficient = mastery_score >= 0.8

        # 2. Check unresolved relevant misconceptions via memory service
        memories = MemoryService.get_relevant_memory_for_concept(db, student_id, concept.title)
        unresolved_misconceptions = [m for m in memories if m.memory_type == "misconception" and m.confidence > 0.5]

        if mastery_sufficient and not unresolved_misconceptions:
            result["status"] = "complete"
            result["reason"] = "Current mastery meets completion criteria and no unresolved misconceptions found."
            
            # Update durable progress
            progress = RoadmapService.get_student_progress(db, student_id, concept.id)
            progress.status = "completed"
            progress.mastery_snapshot = mastery_score
            progress.completed_at = datetime.utcnow()
            db.commit()

        elif unresolved_misconceptions:
            result["status"] = "needs_reinforcement"
            result["reason"] = f"Learner has unresolved misconceptions blocking completion."
            
            # Update durable progress
            progress = RoadmapService.get_student_progress(db, student_id, concept.id)
            progress.status = "needs_reinforcement"
            progress.mastery_snapshot = mastery_score
            db.commit()
            
        else:
            result["status"] = "incomplete"
            result["reason"] = "Mastery score is insufficient for completion."

        return result

    @staticmethod
    def get_next_concept(
        db: Session,
        student_id: int,
        lesson_id: int,
        current_concept: Optional[Concept] = None
    ) -> Optional[Concept]:
        """
        Deterministic selection of the next logical concept in the curriculum sequence.
        Returns None if the curriculum is fully complete.
        """
        concepts = db.query(Concept).filter(
            Concept.lesson_id == lesson_id
        ).order_by(Concept.order_index).all()
        
        if not concepts:
            return None

        for concept in concepts:
            progress = RoadmapService.get_student_progress(db, student_id, concept.id)
            
            # If a concept needs reinforcement, we must reinforce it before progressing further
            if progress.status == "needs_reinforcement":
                # Ensure it's active
                progress.status = "active"
                db.commit()
                return concept
                
            # If a concept is not complete, this is our next curriculum step
            if progress.status != "completed":
                # If current concept is complete but the next one hasn't been started, mark active
                if progress.status == "not_started":
                    progress.status = "active"
                    db.commit()
                return concept

        return None
        
    @staticmethod
    def get_learning_roadmap(db: Session, student_id: int, lesson_id: int) -> Dict[str, Any]:
        """Returns the bounded progression state for the student in this lesson."""
        lesson = db.get(Lesson, lesson_id)
        concepts = db.query(Concept).filter(
            Concept.lesson_id == lesson_id
        ).order_by(Concept.order_index).all()
        
        roadmap_items = []
        for c in concepts:
            progress = RoadmapService.get_student_progress(db, student_id, c.id)
            roadmap_items.append({
                "concept_id": c.id,
                "concept_title": c.title,
                "status": progress.status,
                "mastery_snapshot": progress.mastery_snapshot
            })
            
        return {
            "lesson_id": lesson_id,
            "topic": lesson.topic if lesson else "",
            "items": roadmap_items
        }

    @staticmethod
    def format_roadmap_context(
        db: Session,
        student_id: int,
        lesson_id: int,
        current_concept: Concept
    ) -> str:
        """Formats bounded roadmap information for the TeacherEngine context."""
        roadmap = RoadmapService.get_learning_roadmap(db, student_id, lesson_id)
        
        items = roadmap["items"]
        current_item = next((item for item in items if item["concept_id"] == current_concept.id), None)
        
        # Find immediate next step (the first one after the current that isn't completed)
        next_step = None
        found_current = False
        for item in items:
            if found_current and item["status"] != "completed":
                next_step = item
                break
            if item["concept_id"] == current_concept.id:
                found_current = True
                
        context = "LEARNING ROADMAP:\n"
        context += "Use this as structured progression guidance.\n"
        context += "Current learner evidence takes priority.\n\n"
        
        if current_item:
            context += f"Current concept: {current_item['concept_title']}\n"
            context += f"Completion: {current_item['status']}\n\n"
            
        if next_step:
            context += f"Suggested next concept: {next_step['concept_title']}\n"
        else:
            context += "Suggested next concept: None (End of topic)\n"
            
        return context
