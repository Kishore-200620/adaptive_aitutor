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
        Return the next concept after the current concept.
        """

        concepts = self.get_concepts(state.topic)

        if state.current_concept is None:
            return concepts[0] if concepts else None

        try:
            current_index = concepts.index(state.current_concept)
        except ValueError:
            raise ValueError(
                f"Unknown concept '{state.current_concept}' "
                f"for topic '{state.topic}'"
            )
        next_index = current_index + 1

        if next_index >= len(concepts):
            return None

        return concepts[next_index]