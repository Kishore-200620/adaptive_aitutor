from app.teacher.state import TeacherState


class ConceptGraph:

    def get_concepts(self, topic: str) -> list[str]:
        """
        Return the ordered concepts for a topic.
        """

        topic_lower = topic.lower().strip()

        if topic_lower in {"newton laws", "newton's laws", "newton laws of motion"}:
            return [
                "Force",
                "Newton's First Law",
                "Newton's Second Law",
                "Newton's Third Law",
                "Applications of Newton's Laws",
            ]

        return [topic]

    def get_next_concept(
        self,
        state: TeacherState,
    ) -> str | None:
        """
        Return the next concept after the current concept from the planned curriculum.
        """

        if not state.planned_concepts:
            return None

        if state.current_concept is None:
            return state.planned_concepts[0]

        next_index = state.current_concept_index + 1

        if next_index >= len(state.planned_concepts):
            return None

        return state.planned_concepts[next_index]