from app.teacher.state import TeacherState


class AdaptationEngine:

    def adapt(self, state: TeacherState) -> None:

        # Very low mastery
        if state.mastery_score < 0.4:
            state.teaching_strategy = "analogy_and_example"

        # Partial understanding
        elif state.mastery_score < 0.8:
            state.teaching_strategy = "guided_explanation"

        # Strong understanding
        else:
            state.teaching_strategy = "direct_explanation"

        # Student has mastered the current concept
        if state.mastery_score >= 0.8:
            state.mark_understood()

            if (
                state.current_concept
                and state.current_concept not in state.concepts_completed
            ):
                state.concepts_completed.append(
                    state.current_concept
                )

            if state.current_concept in state.concepts_struggling:
                state.concepts_struggling.remove(
                    state.current_concept
                )

        # Student has not mastered the concept yet
        else:
            state.needs_reteaching = True
            state.current_phase = "reteaching"