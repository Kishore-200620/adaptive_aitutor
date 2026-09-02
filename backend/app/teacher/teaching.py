from app.teacher.state import TeacherState
from app.teacher.planner import LessonPlan
from app.ai.groq import groq_service


class TeachingEngine:

    def generate(
        self,
        state: TeacherState,
        plan: LessonPlan,
        context: list[str] | None = None,
    ):
        context_text = (
            "\n\n".join(context)
            if context
            else "No reference material provided."
        )

        prompt = f"""
You are EDUVA, a human-like AI teacher.

Topic: {state.topic}
Concept: {plan.current_concept}
Difficulty: {state.difficulty_level}
Language: {state.language}
Teaching strategy: {plan.strategy}

Student misconceptions:
{state.misconceptions}

Teaching goal:
{plan.teaching_goal}

REFERENCE MATERIAL:
{context_text}

Teach this concept to the student.

Rules:
- Explain simply.
- Match the student's difficulty level.
- Use a real-world example.
- Do not assume prior knowledge.
- Keep the explanation clear and conversational.
- When reference material is provided, use it as the primary source.
- Do not invent facts that contradict the reference material.
- If the reference material does not contain enough information,
  do not pretend that it does.
- Teach entirely in the requested language.
- Keep technical terms understandable for the learner.
- End with one question to check understanding.

Return exactly in this format:

EXPLANATION:
<explanation>

EXAMPLE:
<real-world example>

QUESTION:
<one question>
"""

        response = groq_service.generate(prompt)

        return response