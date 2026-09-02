from app.schemas.teaching import VisualEvent


class VisualRouter:
    """
    Decides which visual representation should be used
    and prepares clean content for the frontend renderer.
    """

    def generate(self, teaching: str, concept: str) -> VisualEvent | None:
        if not teaching:
            return None

        # Extract the explanation
        explanation = teaching

        if "EXPLANATION:" in explanation:
            explanation = explanation.split("EXPLANATION:", 1)[1]

        # Extract the example
        example = ""

        if "EXAMPLE:" in explanation:
            explanation, example = explanation.split("EXAMPLE:", 1)

        # Remove the question from the example
        if "QUESTION:" in example:
            example = example.split("QUESTION:", 1)[0]

        explanation = explanation.strip()
        example = example.strip()

        # Build clean visual content
        content = explanation

        if example:
            content += f"\n\nExample:\n{example}"

        text = teaching.lower()

                # Code-related teaching
        # Check code BEFORE equations because code
        # commonly contains "=" for variable assignment.
        if any(
            keyword in text
            for keyword in [
                "python",
                "code",
                "function",
                "variable",
                "loop",
                "algorithm",
            ]
        ):
            return VisualEvent(
                type="code",
                title=concept,
                content=content,
            )

        # Mathematical / equation content
        if "=" in teaching or any(
            keyword in text
            for keyword in [
                "equation",
                "formula",
                "calculate",
                "mathematical",
            ]
        ):
            return VisualEvent(
                type="equation",
                title=concept,
                content=content,
            )

        # Diagram-like relationships
        if any(
            keyword in text
            for keyword in [
                "process",
                "flow",
                "step",
                "relationship",
                "connected",
                "leads to",
            ]
        ):
            return VisualEvent(
                type="diagram",
                title=concept,
                content=content,
            )

        # Default educational blackboard
        return VisualEvent(
            type="blackboard",
            title=concept,
            content=content,
        )