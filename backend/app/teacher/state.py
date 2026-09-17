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
    planned_concepts: List[str] = field(default_factory=list)
    current_concept_index: int = 0
    current_concept: Optional[str] = None

    # Student understanding
    mastery_score: float = 0.0
    difficulty_level: str = "beginner"

    # Teaching state
    teaching_strategy: str = "direct_explanation"
    current_phase: str = "introduction"

    # Phase 38: Teaching Cursor
    concept_steps_total: int = 2
    concept_steps_current: int = 1
    concept_history: List[str] = field(default_factory=list)
    teaching_cursor: Optional[dict] = None

    # Previous interaction
    last_question: Optional[str] = None
    last_answer: Optional[str] = None
    # Stored as a dict: {correctness, score, feedback, misconception} or None
    last_evaluation: Optional[dict] = None

    # Detected problems
    misconceptions: List[str] = field(default_factory=list)

    # Learning progress
    concepts_completed: List[str] = field(default_factory=list)
    concepts_struggling: List[str] = field(default_factory=list)

    # Lesson control
    needs_reteaching: bool = False
    attempt_count: int = 0
    assessment_active: bool = False

    # Phase 37: conversational clarification context
    recent_clarifications: List[dict] = field(default_factory=list)

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
            "planned_concepts": self.planned_concepts,
            "current_concept_index": self.current_concept_index,
            "current_concept": self.current_concept,
            "mastery_score": self.mastery_score,
            "difficulty_level": self.difficulty_level,
            "teaching_strategy": self.teaching_strategy,
            "current_phase": self.current_phase,
            "last_question": self.last_question,
            "last_answer": self.last_answer,
            # last_evaluation is stored as dict or None — always serialize as dict
            "last_evaluation": self.last_evaluation if isinstance(self.last_evaluation, dict) else None,
            "misconceptions": self.misconceptions,
            "concepts_completed": self.concepts_completed,
            "concepts_struggling": self.concepts_struggling,
            "needs_reteaching": self.needs_reteaching,
            "attempt_count": self.attempt_count,
            "assessment_active": self.assessment_active,
            "recent_clarifications": self.recent_clarifications,
            "concept_steps_total": self.concept_steps_total,
            "concept_steps_current": self.concept_steps_current,
            "concept_history": self.concept_history,
            "teaching_cursor": self.get_or_create_cursor(),
        }

    def get_or_create_cursor(self) -> dict:
        """
        Returns the canonical teaching cursor. Derives it from current state 
        if it does not exist (for backward compatibility).
        """
        if self.teaching_cursor is not None:
            return self.teaching_cursor
            
        cursor = {
            "concept_index": self.current_concept_index,
            "concept_name": self.current_concept,
            "step": self.concept_steps_current,
            "total_steps": self.concept_steps_total,
            "phase": self.current_phase,
            "next_expected_action": "answer" if self.assessment_active else "continue" if self.concept_steps_current < self.concept_steps_total else "clarification",
            "awaiting_student_input": self.assessment_active or (self.concept_steps_current < self.concept_steps_total),
            "awaiting_assessment_answer": self.assessment_active,
            "in_reteach": self.needs_reteaching,
            "interrupted_by_clarification": False,
            "resume_cursor": None
        }
        self.teaching_cursor = cursor
        return cursor
        
    def sync_cursor(self) -> None:
        """Synchronizes the canonical cursor with the current state fields."""
        cursor = {
            "concept_index": self.current_concept_index,
            "concept_name": self.current_concept,
            "step": self.concept_steps_current,
            "total_steps": self.concept_steps_total,
            "phase": self.current_phase,
            "next_expected_action": "answer" if self.assessment_active else "continue" if self.concept_steps_current < self.concept_steps_total else "clarification",
            "awaiting_student_input": self.assessment_active or (self.concept_steps_current < self.concept_steps_total),
            "awaiting_assessment_answer": self.assessment_active,
            "in_reteach": self.needs_reteaching,
            "interrupted_by_clarification": False,
            "resume_cursor": None
        }
        self.teaching_cursor = cursor

    def update_cursor(self, updates: dict) -> None:
        """Updates specific fields in the canonical teaching cursor."""
        cursor = self.get_or_create_cursor()
        cursor.update(updates)
        self.teaching_cursor = cursor
        
    def pause_cursor_for_clarification(self) -> None:
        """Preserves current position before answering a clarification."""
        cursor = self.get_or_create_cursor()
        if not cursor.get("interrupted_by_clarification"):
            # Store copy of current state to resume
            resume_state = cursor.copy()
            # Mark as interrupted
            cursor["interrupted_by_clarification"] = True
            cursor["resume_cursor"] = resume_state
            self.teaching_cursor = cursor

    def resume_cursor_after_clarification(self) -> None:
        """Restores position after a clarification is resolved."""
        cursor = self.get_or_create_cursor()
        if cursor.get("interrupted_by_clarification") and cursor.get("resume_cursor"):
            # Restore to the pre-clarification state
            self.teaching_cursor = cursor["resume_cursor"]