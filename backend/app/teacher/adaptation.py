from app.teacher.state import TeacherState


class AdaptationEngine:

    def adapt(self, state: TeacherState, roadmap_status: str) -> None:

        # Select teaching strategy based on mastery
        if state.mastery_score < 0.4:
            state.teaching_strategy = "analogy_and_example"

        elif state.mastery_score < 0.7:
            state.teaching_strategy = "guided_explanation"

        else:
            state.teaching_strategy = "direct_explanation"

        # Student has mastered the current concept
        if roadmap_status == "complete":

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
                
            state.needs_reteaching = False

            return

        # Any score below mastery threshold or having unresolved misconceptions requires
        # additional teaching/practice.
        state.needs_reteaching = True
        state.current_phase = "reteaching"

        if (
            state.current_concept
            and state.current_concept not in state.concepts_struggling
        ):
            state.concepts_struggling.append(
                state.current_concept
            )