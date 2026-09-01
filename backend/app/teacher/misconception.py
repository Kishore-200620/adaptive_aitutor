from app.teacher.state import TeacherState


class MisconceptionEngine:

    def process(
        self,
        state: TeacherState,
        misconception: str | None,
    ) -> None:

        if not misconception:
            return

        state.add_misconception(misconception)

        if (
            state.current_concept
            and state.current_concept not in state.concepts_struggling
        ):
            state.concepts_struggling.append(
                state.current_concept
            )

        state.mark_for_reteaching()