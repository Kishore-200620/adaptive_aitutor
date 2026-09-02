from app.teacher.state import TeacherState
from app.teacher.planner import LessonPlanner
from app.teacher.teaching import TeachingEngine
from app.teacher.questioning import QuestioningEngine
from app.teacher.evaluator import AnswerEvaluator
from app.teacher.misconception import MisconceptionEngine
from app.teacher.adaptation import AdaptationEngine
from app.teacher.graph import ConceptGraph
from app.visuals.router import VisualRouter

class TeacherEngine:

    def __init__(self):
        self.planner = LessonPlanner()
        self.teaching = TeachingEngine()
        self.questioning = QuestioningEngine()
        self.evaluator = AnswerEvaluator()
        self.misconception = MisconceptionEngine()
        self.adaptation = AdaptationEngine()
        self.graph = ConceptGraph()
        self.visuals = VisualRouter()
    def start(
        self,
        student_id: int,
        topic: str,
        teaching_context: list[str] | None = None,
        language: str = "English",
    ):
        state = TeacherState(
    student_id=student_id,
    topic=topic,
    language=language,
)

        # 1. Create the lesson plan
        plan = self.planner.create_plan(state)

        # 2. Set the first concept selected by the planner
        state.current_concept = plan.current_concept

        # 3. Generate teaching content
        teaching = self.teaching.generate(
            state,
            plan,
            context=teaching_context,
        )

        # 4. Generate a question for the current concept
        question = self.questioning.generate_question(
            state,
            state.current_concept,
        )

        # 5. Store the question in the state
        self.questioning.record_question(
            state,
            question,
        )
        visual = self.visuals.generate(
            teaching=teaching,
            concept=state.current_concept,
        )
        return {
            "state": state,
            "plan": plan,
            "teaching": teaching,
            "question": question,
            "visual": visual,
    }
    def answer(
        self,
        state: TeacherState,
        answer: str,
    ):
        state.increment_attempt()

        
        # 1. Evaluate the student's answer
        evaluation = self.evaluator.evaluate(
            state,
            answer,
        )

        # 2. Detect and store misconception
        self.misconception.process(
            state,
            evaluation.misconception,
        )

        # 3. Adapt teaching strategy
        self.adaptation.adapt(state)

        # 4. Student has mastered the concept
        if state.mastery_score >= 0.8:
            next_concept = self.graph.get_next_concept(state)

            return {
                "evaluation": evaluation,
                "action": "next_concept",
                "next_concept": next_concept,
            }

        # 5. Student still needs help
        return {
            "evaluation": evaluation,
            "action": "reteach",
            "next_concept": None,
        }
    def next_step(
        self,
        state: TeacherState,
        teaching_context: list[str] | None = None,
    ):
        # Student still needs help with the current concept
        if state.needs_reteaching:
            plan = self.planner.create_plan(state)

            teaching = self.teaching.generate(
                state,
                plan,
                context=teaching_context,
            )

            question = self.questioning.generate_question(
                state,
                state.current_concept,
            )

            self.questioning.record_question(
                state,
                question,
            )
            visual = self.visuals.generate(
                teaching=teaching,
                concept=state.current_concept,
            )
            return {
    "action": "reteach",
    "concept": state.current_concept,
    "plan": plan,
    "teaching": teaching,
    "question": question,
    "visual": visual,
}

        # Current concept is mastered
        next_concept = self.graph.get_next_concept(state)

        if next_concept is None:
            state.current_phase = "completed"

            return {
                "action": "completed",
                "concept": None,
                "plan": None,
                "teaching": None,
                "question": None,
            }

        # Move to the next concept
        state.current_concept = next_concept
        state.mastery_score = 0.0
        state.current_phase = "introduction"
        state.needs_reteaching = False

        plan = self.planner.create_plan(state)

        teaching = self.teaching.generate(
        state,
        plan,
        context=teaching_context,
    )

        question = self.questioning.generate_question(
            state,
            state.current_concept,
        )

        self.questioning.record_question(
            state,
            question,
        )
        visual = self.visuals.generate(
    teaching=teaching,
    concept=state.current_concept,
)
        return {
    "action": "next_concept",
    "concept": state.current_concept,
    "plan": plan,
    "teaching": teaching,
    "question": question,
    "visual": visual,
}