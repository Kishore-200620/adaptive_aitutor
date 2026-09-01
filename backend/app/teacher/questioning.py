from app.teacher.state import TeacherState


class QuestioningEngine:

    def generate_question(
        self,
        state: TeacherState,
        concept: str,
    ) -> str:

        return (
            f"Can you explain what {concept} means "
            f"in your own words?"
        )

    def record_question(
        self,
        state: TeacherState,
        question: str,
    ) -> None:

        state.last_question = question
        state.current_phase = "questioning"