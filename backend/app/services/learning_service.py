from datetime import datetime

from sqlalchemy.orm import Session

from app.models.lesson import Lesson
from app.models.concept import Concept
from app.models.session import TeachingSession
from app.models.attempt import Attempt
from app.teacher.graph import ConceptGraph


class LearningService:
    """
    Handles persistence of the AI Teacher's learning state.
    """

    def __init__(self):
        self.graph = ConceptGraph()

    def create_lesson_session(
        self,
        db: Session,
        student_id: int,
        topic: str,
        document_id: int | None = None,
        difficulty: str = "beginner",
        language: str = "English",
    ):
        # 1. Create lesson
        lesson = Lesson(
            student_id=student_id,
            document_id=document_id,
            title=f"{topic} Lesson",
            topic=topic,
            difficulty=difficulty,
            language=language,
            status="active",
        )

        db.add(lesson)
        db.flush()

        # 2. Create concepts from the existing concept graph
        concept_names = self.graph.get_concepts(topic)

        concepts = []

        for index, concept_name in enumerate(concept_names):
            concept = Concept(
                lesson_id=lesson.id,
                title=concept_name,
                description=None,
                order_index=index,
                difficulty=difficulty,
                mastery_score=0.0,
            )

            db.add(concept)
            concepts.append(concept)

        db.flush()

        # 3. First concept
        current_concept = concepts[0] if concepts else None

        # 4. Create teaching session
        session = TeachingSession(
            student_id=student_id,
            lesson_id=lesson.id,
            current_concept_id=(
                current_concept.id
                if current_concept
                else None
            ),
            status="active",
            current_step="explain",
        )

        db.add(session)
        db.commit()

        db.refresh(lesson)
        db.refresh(session)

        return lesson, concepts, session

    def save_attempt(
        self,
        db: Session,
        session: TeachingSession,
        concept: Concept,
        question: str,
        student_answer: str,
        is_correct: bool,
        evaluation: str,
        misconception: str | None,
    ):
        attempt = Attempt(
            session_id=session.id,
            concept_id=concept.id,
            question=question,
            student_answer=student_answer,
            is_correct=is_correct,
            evaluation=evaluation,
            misconception=misconception,
        )

        db.add(attempt)

        db.commit()
        db.refresh(attempt)

        return attempt

    def update_concept_mastery(
        self,
        db: Session,
        concept: Concept,
        mastery_score: float,
    ):
        concept.mastery_score = max(
            0.0,
            min(1.0, mastery_score),
        )

        db.commit()
        db.refresh(concept)

        return concept

    def update_session(
        self,
        db: Session,
        session: TeachingSession,
        concept_id: int | None,
        step: str,
        status: str = "active",
    ):
        session.current_concept_id = concept_id
        session.current_step = step
        session.status = status

        if status == "completed":
            session.completed_at = datetime.utcnow()

        db.commit()
        db.refresh(session)

        return session