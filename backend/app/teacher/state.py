from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TeacherState:
    """
    Represents the current teaching state of EDUVA for one student.
    """

    student_id: int

    # Learning context
    topic: str
    language: str = "English"
    current_concept: Optional[str] = None

    # Student understanding
    mastery_score: float = 0.0
    difficulty_level: str = "beginner"

    # Teaching state
    teaching_strategy: str = "direct_explanation"
    current_phase: str = "introduction"

    # Previous interaction
    last_question: Optional[str] = None
    last_answer: Optional[str] = None
    last_evaluation: Optional[str] = None

    # Detected problems
    misconceptions: List[str] = field(default_factory=list)

    # Learning progress
    concepts_completed: List[str] = field(default_factory=list)
    concepts_struggling: List[str] = field(default_factory=list)

    # Lesson control
    needs_reteaching: bool = False
    attempt_count: int = 0

    def update_mastery(self, score: float) -> None:
        """
        Update the student's mastery score.

        Score must be between 0 and 1.
        """
        self.mastery_score = max(0.0, min(1.0, score))

    def add_misconception(self, misconception: str) -> None:
        """
        Add a misconception if it is not already recorded.
        """
        if misconception and misconception not in self.misconceptions:
            self.misconceptions.append(misconception)

    def mark_for_reteaching(self) -> None:
        """
        Mark the current concept for re-teaching.
        """
        self.needs_reteaching = True
        self.current_phase = "reteaching"

    def mark_understood(self) -> None:
        """
        Mark the current concept as understood.
        """
        self.needs_reteaching = False
        self.current_phase = "mastered"

    def increment_attempt(self) -> None:
        """
        Record another student attempt.
        """
        self.attempt_count += 1

    def summary(self) -> dict:
        """
        Return a serializable representation of the current state.
        """
        return {
            "student_id": self.student_id,
            "topic": self.topic,
            "language": self.language,
            "current_concept": self.current_concept,
            "mastery_score": self.mastery_score,
            "difficulty_level": self.difficulty_level,
            "teaching_strategy": self.teaching_strategy,
            "current_phase": self.current_phase,
            "last_question": self.last_question,
            "last_answer": self.last_answer,
            
            "last_evaluation": self.last_evaluation,
            "misconceptions": self.misconceptions,
            "concepts_completed": self.concepts_completed,
            "concepts_struggling": self.concepts_struggling,
            "needs_reteaching": self.needs_reteaching,
            "attempt_count": self.attempt_count,
        }