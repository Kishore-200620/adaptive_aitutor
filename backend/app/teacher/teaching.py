from app.teacher.state import TeacherState
from app.teacher.planner import LessonPlan
from app.ai.groq import groq_service


class TeachingEngine:

    def generate(
        self,
        state: TeacherState,
        plan: LessonPlan,
    ):
        prompt = f"""
You are EDUVA, a human-like AI teacher.

Topic: {state.topic}
Concept: {plan.current_concept}
Difficulty: {state.difficulty_level}
Teaching strategy: {plan.strategy}

Student misconceptions:
{state.misconceptions}

Teaching goal:
{plan.teaching_goal}

Teach this concept to the student.

Rules:
- Explain simply.
- Match the student's difficulty level.
- Use a real-world example.
- Do not assume prior knowledge.
- Keep the explanation clear and conversational.
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