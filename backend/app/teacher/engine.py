from app.teacher.state import TeacherState
from app.teacher.planner import LessonPlanner
from app.teacher.teaching import TeachingEngine
from app.teacher.questioning import QuestioningEngine
from app.teacher.evaluator import AnswerEvaluator
from app.teacher.misconception import MisconceptionEngine
from app.teacher.adaptation import AdaptationEngine
from app.teacher.graph import ConceptGraph
from app.visuals.router import VisualRouter
from app.ai.groq import groq_service

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

    def classify_intent(self, state: TeacherState, message: str) -> str:
        # 1. Deterministic CONTINUE intent detector
        clean_msg = message.strip().lower()
        continue_phrases = [
            "continue", "okay, continue", "ok, continue", "got it",
            "i understand", "let's continue", "go on", "proceed",
            "okay", "ok", "makes sense", "understood", "yes, continue",
            "next"
        ]
        
        if clean_msg in continue_phrases or (len(clean_msg) < 20 and any(clean_msg.startswith(p) for p in continue_phrases)):
            return "continue"

        if not state.assessment_active:
            return "clarification"

        # 2. LLM Intent Classifier
        recent_context = ""
        if state.recent_clarifications:
            recent_context = "Recent conversation context:\n"
            for msg in state.recent_clarifications[-4:]:
                role = "Student" if msg.get("role") == "user" else "Teacher"
                recent_context += f"{role}: {msg.get('content')}\n"
                
        prompt = f"""
You are an expert AI teacher interacting with a student.

You just asked this question:
{state.last_question}

{recent_context}

The student replied:
"{message}"

Classify the student's reply as either an actual attempt to answer the question (even if incorrect) or a clarification request (e.g. they don't understand the question, they are asking a follow up question, they are asking for help).

Return EXACTLY one word:
ASSESSMENT_ANSWER
or
CLARIFICATION
"""
        try:
            response = groq_service.generate(prompt).strip().upper()
            if "CLARIFICATION" in response:
                return "clarification"
            elif "ASSESSMENT_ANSWER" in response:
                return "assessment_answer"
            return "clarification"  # Safe fallback
        except Exception:
            return "clarification"  # Safe fallback

    def clarify(self, state: TeacherState, message: str, context: list[str] | None = None) -> str:
        context_text = "\n\n".join(context) if context else "No reference material provided."
        
        recent_context = ""
        if state.recent_clarifications:
            recent_context = "RECENT CONVERSATION CONTEXT:\n"
            for msg in state.recent_clarifications[-6:]:
                role = "Student" if msg.get("role") == "user" else "Teacher"
                recent_context += f"{role}: {msg.get('content')}\n"
        
        assessment_section = ""
        guidance_section = ""
        question_output = ""
        
        if state.assessment_active:
            assessment_section = f"Active Assessment Question:\n{state.last_question}\n"
            guidance_section = "If the student is just saying \"continue\" or \"okay\", gently remind them to answer the active assessment question.\nDO NOT ASK NEW QUESTIONS. After clarifying, gently remind them of the active assessment question."
            question_output = f"QUESTION:\n<The SAME active assessment question exactly as: {state.last_question}>"
        else:
            guidance_section = "Answer the student's clarification naturally. Do NOT ask them an assessment question. If they say 'continue' or 'okay', acknowledge it."
            question_output = f"QUESTION:\n<The SAME question exactly as: {state.last_question}>"
        
        prompt = f"""
You are EDUVA, a human-like AI teacher.

Topic: {state.topic}
Concept: {state.current_concept}
Language: {state.language}

{assessment_section}
{recent_context}

Student is asking for clarification or making a comment:
"{message}"

REFERENCE MATERIAL:
{context_text}

Provide a helpful, conversational response addressing the student's clarification request or comment in {state.language}. 
{guidance_section}

Return exactly in this format:

NARRATION:
<The spoken, conversational explanation>

BLACKBOARD:
<Concise visual content, labels, diagrams, or equations. Keep it very short.>

VISUAL_DIRECTIVE:
<Optional instructions for generating an educational image. Leave blank if not needed.>

{question_output}
"""
        return groq_service.generate(prompt)

    async def clarify_stream(self, state: TeacherState, message: str, context: list[str] | None = None):
        context_text = "\n\n".join(context) if context else "No reference material provided."
        
        recent_context = ""
        if state.recent_clarifications:
            recent_context = "RECENT CONVERSATION CONTEXT:\n"
            for msg in state.recent_clarifications[-6:]:
                role = "Student" if msg.get("role") == "user" else "Teacher"
                recent_context += f"{role}: {msg.get('content')}\n"
        
        assessment_section = ""
        guidance_section = ""
        question_output = ""
        
        if state.assessment_active:
            assessment_section = f"Active Assessment Question:\n{state.last_question}\n"
            guidance_section = "If the student is just saying \"continue\" or \"okay\", gently remind them to answer the active assessment question.\nDO NOT ASK NEW QUESTIONS. After clarifying, gently remind them of the active assessment question."
            question_output = f"QUESTION:\n<The SAME active assessment question exactly as: {state.last_question}>"
        else:
            guidance_section = "Answer the student's clarification naturally. Do NOT ask them an assessment question. If they say 'continue' or 'okay', acknowledge it."
            question_output = f"QUESTION:\n<The SAME question exactly as: {state.last_question}>"
        
        prompt = f"""
You are EDUVA, a human-like AI teacher.

Topic: {state.topic}
Concept: {state.current_concept}
Language: {state.language}

{assessment_section}
{recent_context}

Student is asking for clarification or making a comment:
"{message}"

REFERENCE MATERIAL:
{context_text}

Provide a helpful, conversational response addressing the student's clarification request or comment in {state.language}. 
{guidance_section}

Return exactly in this format:

NARRATION:
<The spoken, conversational explanation>

BLACKBOARD:
<Concise visual content, labels, diagrams, or equations. Keep it very short.>

VISUAL_DIRECTIVE:
<Optional instructions for generating an educational image. Leave blank if not needed.>

{question_output}
"""
        async def generator():
            teaching_text = ""
            async for chunk in groq_service.generate_stream(prompt):
                teaching_text += chunk
                yield {"type": "teaching_chunk", "content": chunk}
            
            yield {
                "type": "complete",
                "data": {
                    "action": "clarification",
                    "concept": state.current_concept,
                    "teaching": teaching_text,
                    "question": state.last_question,
                }
            }
        return generator()
    def start(
        self,
        student_id: int,
        topic: str,
        teaching_context: list[str] | None = None,
        language: str = "English",
        planned_concepts: list[str] | None = None,
    ):
        state = TeacherState(
            student_id=student_id,
            topic=topic,
            language=language,
        )
        if planned_concepts:
            state.planned_concepts = planned_concepts

        plan = self.planner.create_plan(state)
        state.current_concept = plan.current_concept
        
        state.concept_steps_total = 2
        state.concept_steps_current = 1
        state.concept_history = []

        teaching = self.teaching.generate(state, plan, context=teaching_context)
        state.concept_history.append(teaching)

        if state.concept_steps_current == state.concept_steps_total:
            question = self.questioning.generate_question(state, state.current_concept)
            self.questioning.record_question(state, question)
        else:
            question = "When you're ready, say \"Continue\" or ask a question."
            state.last_question = question
            state.assessment_active = False

        return {
            "state": state,
            "plan": plan,
            "teaching": teaching,
            "question": question,
        }

    def answer(
        self,
        state: TeacherState,
        answer: str,
    ):
        state.increment_attempt()
        state.assessment_active = False
        state.recent_clarifications = []
        
        evaluation = self.evaluator.evaluate(state, answer)
        self.misconception.process(state, evaluation.misconception)
        self.adaptation.adapt(state)

        if state.mastery_score >= 0.8:
            next_concept = self.graph.get_next_concept(state)
            return {
                "evaluation": evaluation,
                "action": "next_concept",
                "next_concept": next_concept,
            }

        return {
            "evaluation": evaluation,
            "action": "reteach",
            "next_concept": None,
        }

    def continue_step(self, state: TeacherState, teaching_context: list[str] | None = None):
        state.concept_steps_current += 1
        plan = self.planner.create_plan(state)
        
        teaching = self.teaching.generate(state, plan, context=teaching_context)
        state.concept_history.append(teaching)
        
        if state.concept_steps_current == state.concept_steps_total:
            question = self.questioning.generate_question(state, state.current_concept)
            self.questioning.record_question(state, question)
        else:
            question = "When you're ready, say \"Continue\" or ask a question."
            state.last_question = question
            state.assessment_active = False
            
        return {
            "action": "continue_step",
            "concept": state.current_concept,
            "plan": plan,
            "teaching": teaching,
            "question": question,
        }

    async def continue_step_stream(self, state: TeacherState, teaching_context: list[str] | None = None):
        state.concept_steps_current += 1
        plan = self.planner.create_plan(state)
        
        async def generator():
            teaching_text = ""
            async for chunk in self.teaching.generate_stream(state, plan, context=teaching_context):
                teaching_text += chunk
                yield {"type": "teaching_chunk", "content": chunk}
                
            state.concept_history.append(teaching_text)
            
            if state.concept_steps_current == state.concept_steps_total:
                question = self.questioning.generate_question(state, state.current_concept)
                self.questioning.record_question(state, question)
            else:
                question = "When you're ready, say \"Continue\" or ask a question."
                state.last_question = question
                state.assessment_active = False
                
            yield {
                "type": "complete",
                "data": {
                    "action": "continue_step",
                    "concept": state.current_concept,
                    "plan": plan,
                    "teaching": teaching_text,
                    "question": question,
                }
            }
        return generator()
    def answer(
        self,
        state: TeacherState,
        answer: str,
    ):
        state.increment_attempt()
        state.assessment_active = False
        state.recent_clarifications = []
        
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
        if state.needs_reteaching:
            plan = self.planner.create_plan(state)
            
            state.concept_steps_total = 2
            state.concept_steps_current = 1
            state.concept_history = []

            teaching = self.teaching.generate(state, plan, context=teaching_context)
            state.concept_history.append(teaching)

            if state.concept_steps_current == state.concept_steps_total:
                question = self.questioning.generate_question(state, state.current_concept)
                self.questioning.record_question(state, question)
            else:
                question = "When you're ready, say \"Continue\" or ask a question."
                state.last_question = question
                state.assessment_active = False

            return {
                "action": "reteach",
                "concept": state.current_concept,
                "plan": plan,
                "teaching": teaching,
                "question": question,
            }

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

        state.current_concept = next_concept
        state.current_concept_index += 1
        state.mastery_score = 0.0
        state.current_phase = "introduction"
        state.needs_reteaching = False
        
        state.concept_steps_total = 2
        state.concept_steps_current = 1
        state.concept_history = []

        plan = self.planner.create_plan(state)

        teaching = self.teaching.generate(state, plan, context=teaching_context)
        state.concept_history.append(teaching)

        if state.concept_steps_current == state.concept_steps_total:
            question = self.questioning.generate_question(state, state.current_concept)
            self.questioning.record_question(state, question)
        else:
            question = "When you're ready, say \"Continue\" or ask a question."
            state.last_question = question
            state.assessment_active = False

        return {
            "action": "next_concept",
            "concept": state.current_concept,
            "plan": plan,
            "teaching": teaching,
            "question": question,
        }

    async def start_stream(
        self,
        student_id: int,
        topic: str,
        teaching_context: list[str] | None = None,
        language: str = "English",
        planned_concepts: list[str] | None = None,
    ):
        state = TeacherState(
            student_id=student_id,
            topic=topic,
            language=language,
        )
        if planned_concepts:
            state.planned_concepts = planned_concepts

        plan = self.planner.create_plan(state)
        state.current_concept = plan.current_concept
        
        state.concept_steps_total = 2
        state.concept_steps_current = 1
        state.concept_history = []

        async def generator():
            teaching_text = ""
            async for chunk in self.teaching.generate_stream(
                state,
                plan,
                context=teaching_context,
            ):
                teaching_text += chunk
                yield {"type": "teaching_chunk", "content": chunk}

            state.concept_history.append(teaching_text)

            import time
            import logging
            logger = logging.getLogger("eduva.stream")
            
            if state.concept_steps_current == state.concept_steps_total:
                logger.info("[EDUVA][Latency] TEACHING_PARSE_START (Question generation)")
                question = self.questioning.generate_question(state, state.current_concept)
                logger.info("[EDUVA][Latency] TEACHING_PARSE_COMPLETE (Question generation)")
                self.questioning.record_question(state, question)
            else:
                question = "When you're ready, say \"Continue\" or ask a question."
                state.last_question = question
                state.assessment_active = False
            
            yield {
                "type": "complete",
                "data": {
                    "state": state,
                    "plan": plan,
                    "teaching": teaching_text,
                    "question": question,
                }
            }

        return generator()

    async def next_step_stream(
        self,
        state: TeacherState,
        teaching_context: list[str] | None = None,
    ):
        if state.needs_reteaching:
            plan = self.planner.create_plan(state)
            
            state.concept_steps_total = 2
            state.concept_steps_current = 1
            state.concept_history = []

            async def reteach_generator():
                teaching_text = ""
                async for chunk in self.teaching.generate_stream(
                    state,
                    plan,
                    context=teaching_context,
                ):
                    teaching_text += chunk
                    yield {"type": "teaching_chunk", "content": chunk}

                state.concept_history.append(teaching_text)

                if state.concept_steps_current == state.concept_steps_total:
                    question = self.questioning.generate_question(state, state.current_concept)
                    self.questioning.record_question(state, question)
                else:
                    question = "When you're ready, say \"Continue\" or ask a question."
                    state.last_question = question
                    state.assessment_active = False
                
                yield {
                    "type": "complete",
                    "data": {
                        "action": "reteach",
                        "concept": state.current_concept,
                        "plan": plan,
                        "teaching": teaching_text,
                        "question": question,
                    }
                }
            return reteach_generator()

        next_concept = self.graph.get_next_concept(state)

        if next_concept is None:
            state.current_phase = "completed"

            async def complete_generator():
                yield {
                    "type": "complete",
                    "data": {
                        "action": "completed",
                        "concept": None,
                        "plan": None,
                        "teaching": None,
                        "question": None,
                    }
                }
            return complete_generator()

        state.current_concept = next_concept
        state.current_concept_index += 1
        state.mastery_score = 0.0
        state.current_phase = "introduction"
        state.needs_reteaching = False
        
        state.concept_steps_total = 2
        state.concept_steps_current = 1
        state.concept_history = []

        plan = self.planner.create_plan(state)

        async def next_generator():
            teaching_text = ""
            async for chunk in self.teaching.generate_stream(
                state,
                plan,
                context=teaching_context,
            ):
                teaching_text += chunk
                yield {"type": "teaching_chunk", "content": chunk}

            state.concept_history.append(teaching_text)

            if state.concept_steps_current == state.concept_steps_total:
                question = self.questioning.generate_question(state, state.current_concept)
                self.questioning.record_question(state, question)
            else:
                question = "When you're ready, say \"Continue\" or ask a question."
                state.last_question = question
                state.assessment_active = False
            
            yield {
                "type": "complete",
                "data": {
                    "action": "next_concept",
                    "concept": state.current_concept,
                    "plan": plan,
                    "teaching": teaching_text,
                    "question": question,
                }
            }
        return next_generator()