from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.attempt import Attempt
from app.models.concept import Concept
from app.models.lesson import Lesson
from app.models.session import TeachingSession


class AssessmentService:

    def create_assessment(
        self,
        db: Session,
        session_id: int,
    ) -> Assessment:

        session = db.get(TeachingSession, session_id)

        if session is None:
            raise ValueError("Teaching session not found")

        lesson = db.get(Lesson, session.lesson_id)

        if lesson is None:
            raise ValueError("Lesson not found")

        concepts = (
            db.query(Concept)
            .filter(Concept.lesson_id == session.lesson_id)
            .order_by(Concept.order_index)
            .all()
        )

        if not concepts:
            raise ValueError("No concepts found for this lesson")

        attempts_count = (
            db.query(Attempt)
            .filter(Attempt.session_id == session_id)
            .count()
        )

        strong_areas = []
        weak_areas = []

        for concept in concepts:

            if concept.mastery_score >= 0.8:
                strong_areas.append(concept.title)
            else:
                weak_areas.append(concept.title)

        average_mastery = (
            sum(concept.mastery_score for concept in concepts)
            / len(concepts)
        )

        score = round(average_mastery * 100)

        if weak_areas:

            recommendations = (
                "Review the weak concepts and complete additional "
                "practice before moving to more advanced material."
            )

            next_topic = None

        else:

            recommendations = (
                "Strong understanding demonstrated. "
                "The learner can continue to the next topic."
            )

            next_topic = (
                f"Continue to the next topic related to "
                f"{lesson.topic}"
            )

        assessment = Assessment(
            session_id=session_id,
            score=score,
            total_questions=attempts_count,
            strong_areas=", ".join(strong_areas) or None,
            weak_areas=", ".join(weak_areas) or None,
            recommendations=recommendations,
            next_topic=next_topic,
        )

        db.add(assessment)
        db.commit()
        db.refresh(assessment)

        return assessment