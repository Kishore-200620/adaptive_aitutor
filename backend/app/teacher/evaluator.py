from app.teacher.state import TeacherState
from app.ai.groq import groq_service


class EvaluationResult:
    def __init__(
        self,
        correctness: str,
        score: float,
        feedback: str,
        misconception: str | None = None,
    ):
        self.correctness = correctness
        self.score = score
        self.feedback = feedback
        self.misconception = misconception

    def summary(self):
        return {
            "correctness": self.correctness,
            "score": self.score,
            "feedback": self.feedback,
            "misconception": self.misconception,
        }


class AnswerEvaluator:

    def evaluate(
        self,
        state: TeacherState,
        answer: str,
    ) -> EvaluationResult:

        prompt = f"""
You are an expert AI teacher evaluating a student's answer.

Topic: {state.topic}
Concept: {state.current_concept}
Language: {state.language}

Question:
{state.last_question}

Student answer:
{answer}

Evaluate the answer.

Return exactly in this format:

CORRECTNESS: <correct, partial, or incorrect>
SCORE: <number from 0 to 1>
FEEDBACK: <short helpful feedback>
MISCONCEPTION: <misconception or NONE>

Rules:
- Correct means the student understands the concept.
- Partial means the student understands some of it but has gaps.
- Incorrect means the student's understanding is wrong.
- Identify a specific misconception when possible.
- Do not be harsh.
- Write FEEDBACK entirely in {state.language}.
- Write MISCONCEPTION entirely in {state.language}.
- Keep the feedback short, clear, supportive, and appropriate for the learner.
- Do not translate the labels CORRECTNESS, SCORE, FEEDBACK, or MISCONCEPTION.
- Keep CORRECTNESS exactly as correct, partial, or incorrect.
- Keep SCORE as a numeric value from 0 to 1.
"""

        response = groq_service.generate(prompt)

        return self._parse_response(
            response,
            state,
            answer,
        )

    def _parse_response(
        self,
        response: str,
        state: TeacherState,
        answer: str,
    ) -> EvaluationResult:

        lines = {}

        for line in response.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                lines[key.strip().upper()] = value.strip()

        correctness = lines.get(
            "CORRECTNESS",
            "incorrect",
        ).lower()

        try:
            score = float(
                lines.get(
                    "SCORE",
                    "0",
                )
            )
        except ValueError:
            score = 0.0

        score = max(
            0.0,
            min(1.0, score),
        )

        feedback = lines.get(
            "FEEDBACK",
            "Let's review this concept together.",
        )

        misconception = lines.get(
            "MISCONCEPTION"
        )

        if misconception == "NONE":
            misconception = None

        state.last_answer = answer
        state.last_evaluation = correctness
        state.update_mastery(score)

        return EvaluationResult(
            correctness=correctness,
            score=score,
            feedback=feedback,
            misconception=misconception,
        )