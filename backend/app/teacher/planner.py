import json
from dataclasses import dataclass, field
from typing import List

from app.teacher.state import TeacherState
from app.ai.groq import groq_service


@dataclass
class LessonPlan:
    """
    Represents the teaching plan generated for a student.
    """

    topic: str
    concepts: List[str] = field(default_factory=list)

    current_concept: str | None = None

    difficulty_level: str = "beginner"

    teaching_goal: str = ""

    needs_reteaching: bool = False

    strategy: str = "direct_explanation"

    def summary(self) -> dict:
        return {
            "topic": self.topic,
            "concepts": self.concepts,
            "current_concept": self.current_concept,
            "difficulty_level": self.difficulty_level,
            "teaching_goal": self.teaching_goal,
            "needs_reteaching": self.needs_reteaching,
            "strategy": self.strategy,
        }


class LessonPlanner:
    """
    Creates a lesson plan from the student's current TeacherState.
    """

    def create_plan(self, state: TeacherState) -> LessonPlan:

        if not state.planned_concepts:
            state.planned_concepts = self._get_concepts(state.topic)
            state.current_concept_index = 0

        concepts = state.planned_concepts

        current_concept = state.current_concept

        if current_concept is None and concepts:
            current_concept = concepts[state.current_concept_index]

        strategy = self._select_strategy(state)

        teaching_goal = self._create_goal(
            state=state,
            current_concept=current_concept,
        )

        return LessonPlan(
            topic=state.topic,
            concepts=concepts,
            current_concept=current_concept,
            difficulty_level=state.difficulty_level,
            teaching_goal=teaching_goal,
            needs_reteaching=state.needs_reteaching,
            strategy=strategy,
        )

    def _get_concepts(self, topic: str) -> List[str]:
        """
        Generates an ordered curriculum of 3-5 subtopics using the LLM.
        """
        prompt = f"""
You are an expert curriculum designer.
Generate an ordered list of 3-5 subtopics to teach the topic: "{topic}".
The subtopics must form a logical pedagogical progression.
Return ONLY a valid JSON object with a "subtopics" array of strings. Do not include any markdown or other text.
Example format:
{{
  "subtopics": [
    "Subtopic 1",
    "Subtopic 2",
    "Subtopic 3"
  ]
}}
"""
        try:
            response = groq_service.generate(prompt, expected_format="json")
            # Clean up potential markdown formatting if the LLM ignores the instruction
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            
            data = json.loads(cleaned.strip())
            subtopics = data.get("subtopics", [])
            
            if isinstance(subtopics, list) and len(subtopics) > 0:
                # Filter out empty or duplicate strings
                seen = set()
                valid = []
                for s in subtopics:
                    if isinstance(s, str) and s.strip() and s.strip() not in seen:
                        seen.add(s.strip())
                        valid.append(s.strip())
                if valid:
                    return valid[:7] # Bound to a max of 7 to be safe
        except Exception:
            pass
            
        # Fallback to a hardcoded logic or single topic if LLM fails
        topic_lower = topic.lower()
        if "newton" in topic_lower:
            return [
                "Force",
                "Newton's First Law",
                "Newton's Second Law",
                "Newton's Third Law",
                "Applications of Newton's Laws",
            ]

        return [topic]

    def _select_strategy(self, state: TeacherState) -> str:
        """
        Select an initial teaching strategy based on learner state.
        """

        if state.needs_reteaching:
            return "analogy_and_example"

        if state.mastery_score < 0.4:
            return "simple_explanation"

        if state.mastery_score < 0.7:
            return "explanation_with_example"

        return "conceptual_explanation"

    def _create_goal(
        self,
        state: TeacherState,
        current_concept: str | None,
    ) -> str:

        if current_concept is None:
            return f"Introduce the topic {state.topic}."

        if state.needs_reteaching:
            return (
                f"Re-teach {current_concept} using a simpler explanation, "
                f"analogy, and example to address the student's misconception."
            )

        return (
            f"Help the student understand {current_concept} "
            f"and prepare them to answer a question about it."
        )