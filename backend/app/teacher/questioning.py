from app.teacher.state import TeacherState


class QuestioningEngine:

    QUESTION_TEMPLATES = {
        "English": "Can you explain what {concept} means in your own words?",
        "Tamil": "{concept} என்றால் என்ன என்பதை உங்கள் சொந்த வார்த்தைகளில் விளக்க முடியுமா?",
        "Hindi": "{concept} का अर्थ अपने शब्दों में समझा सकते हैं?",
    }

    def generate_question(
        self,
        state: TeacherState,
        concept: str,
    ) -> str:

        template = self.QUESTION_TEMPLATES.get(
            state.language,
            self.QUESTION_TEMPLATES["English"],
        )

        return template.format(concept=concept)

    def record_question(
        self,
        state: TeacherState,
        question: str,
    ):
        state.last_question = question
        state.current_phase = "questioning"