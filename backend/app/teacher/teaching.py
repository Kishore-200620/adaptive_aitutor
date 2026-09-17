from app.teacher.state import TeacherState
from app.teacher.planner import LessonPlan
from app.ai.groq import groq_service


class TeachingEngine:

    def generate(
        self,
        state: TeacherState,
        plan: LessonPlan,
        context: list[str] | None = None,
        candidate_visuals: list[dict] | None = None,
    ):
        context_text = (
            "\n\n".join(context)
            if context
            else "No reference material provided."
        )

        visuals_context = ""
        if candidate_visuals:
            visuals_context = "AVAILABLE PDF VISUALS (You may select ONE if it highly matches the concept):\n"
            for v in candidate_visuals:
                visuals_context += f"- [ID: {v['id']}] Type: {v.get('visual_type', 'unknown')}, Caption: {v.get('caption', 'None')}\n"

        total_subtopics = len(state.planned_concepts) if state.planned_concepts else 1
        subtopic_idx = state.current_concept_index + 1
        curriculum_context = f"CURRENT SUBTOPIC: {plan.current_concept}\nSUBTOPIC POSITION: {subtopic_idx} of {total_subtopics}\n"

        step_context = f"This concept is being taught in {state.concept_steps_total} steps.\nYou are generating STEP {state.concept_steps_current} of {state.concept_steps_total}.\n"
        if state.concept_steps_current > 1 and state.concept_history:
            step_context += "PREVIOUS TEACHING STEPS:\n" + "\n---\n".join(state.concept_history) + "\n\nContinue naturally from the previous explanation. Do not repeat the previous step unnecessarily.\n"

        question_rule = "- End with one question to check understanding."
        question_instruction = "<one question>"
        if state.concept_steps_current < state.concept_steps_total:
            question_rule = "- DO NOT ask an assessment question at this step. The student will continue when ready."
            question_instruction = "<leave blank>"

        prompt = f"""
You are EDUVA, a human-like AI teacher.

Topic: {state.topic}
Concept: {plan.current_concept}
Difficulty: {state.difficulty_level}
Language: {state.language}
Teaching strategy: {plan.strategy}

Student misconceptions:
{state.misconceptions}

Teaching goal:
{plan.teaching_goal}

{curriculum_context}
{step_context}
REFERENCE MATERIAL:
{context_text}

{visuals_context}

Teach this concept to the student.

Rules:
- Explain simply.
- Match the student's difficulty level.
- Use a real-world example.
- Do not assume prior knowledge.
- Keep the explanation clear and conversational.
- When reference material is provided, use it as the primary source.
- Do not invent facts that contradict the reference material.
- Teach entirely in the requested language.
- Keep technical terms understandable for the learner.
- Do NOT use any markdown formatting (like **, _, or \[ \]) in the NARRATION. The NARRATION is spoken text.
{question_rule}

Return exactly in this format:

BLACKBOARD:
<Concise visual content, labels, diagrams, or equations. Keep it very short.>

VISUAL_DIRECTIVE:
<Optional instructions for generating an educational image. Leave blank if not needed. If an available PDF visual is highly relevant to the concept, you MUST use it by writing exactly: USE_PDF_VISUAL: [ID]>

NARRATION:
<The spoken, conversational explanation pointing to the blackboard>

QUESTION:
{question_instruction}
"""

        response = groq_service.generate(prompt)

        return response

    async def generate_stream(
        self,
        state: TeacherState,
        plan: LessonPlan,
        context: list[str] | None = None,
        candidate_visuals: list[dict] | None = None,
    ):
        context_text = (
            "\n\n".join(context)
            if context
            else "No reference material provided."
        )

        visuals_context = ""
        if candidate_visuals:
            visuals_context = "AVAILABLE PDF VISUALS (You may select ONE if it highly matches the concept):\n"
            for v in candidate_visuals:
                visuals_context += f"- [ID: {v['id']}] Type: {v.get('visual_type', 'unknown')}, Caption: {v.get('caption', 'None')}\n"

        total_subtopics = len(state.planned_concepts) if state.planned_concepts else 1
        subtopic_idx = state.current_concept_index + 1
        curriculum_context = f"CURRENT SUBTOPIC: {plan.current_concept}\nSUBTOPIC POSITION: {subtopic_idx} of {total_subtopics}\n"

        step_context = f"This concept is being taught in {state.concept_steps_total} steps.\nYou are generating STEP {state.concept_steps_current} of {state.concept_steps_total}.\n"
        if state.concept_steps_current > 1 and state.concept_history:
            step_context += "PREVIOUS TEACHING STEPS:\n" + "\n---\n".join(state.concept_history) + "\n\nContinue naturally from the previous explanation. Do not repeat the previous step unnecessarily.\n"

        question_rule = "- End with one question to check understanding."
        question_instruction = "<one question>"
        if state.concept_steps_current < state.concept_steps_total:
            question_rule = "- DO NOT ask an assessment question at this step. The student will continue when ready."
            question_instruction = "<leave blank>"

        prompt = f"""
You are EDUVA, a human-like AI teacher.

Topic: {state.topic}
Concept: {plan.current_concept}
Difficulty: {state.difficulty_level}
Language: {state.language}
Teaching strategy: {plan.strategy}

Student misconceptions:
{state.misconceptions}

Teaching goal:
{plan.teaching_goal}

{curriculum_context}
{step_context}
REFERENCE MATERIAL:
{context_text}

{visuals_context}

Teach this concept to the student.

Rules:
- Explain simply.
- Match the student's difficulty level.
- Use a real-world example.
- Do not assume prior knowledge.
- Keep the explanation clear and conversational.
- When reference material is provided, use it as the primary source.
- Do not invent facts that contradict the reference material.
- Teach entirely in the requested language.
- Keep technical terms understandable for the learner.
- Do NOT use any markdown formatting (like **, _, or \[ \]) in the NARRATION. The NARRATION is spoken text.
{question_rule}

Return exactly in this format:

BLACKBOARD:
<Concise visual content, labels, diagrams, or equations. Keep it very short.>

VISUAL_DIRECTIVE:
<Optional instructions for generating an educational image. Leave blank if not needed. If an available PDF visual is highly relevant to the concept, you MUST use it by writing exactly: USE_PDF_VISUAL: [ID]>

NARRATION:
<The spoken, conversational explanation pointing to the blackboard>

QUESTION:
{question_instruction}
"""
        async for chunk in groq_service.generate_stream(prompt):
            yield chunk

    def translate(self, text: str, language: str) -> str:
        if language.lower() == "english":
            return text
            
        prompt = f"""
You are EDUVA, a human-like AI teacher.

Translate the following teaching event exactly into {language}.
Preserve the exact format:
NARRATION:
<narration>

BLACKBOARD:
<blackboard>

VISUAL_DIRECTIVE:
<visual_directive>

QUESTION:
<question>

Also preserve any [PDF Diagram available at ...] markers exactly as they are.

TEACHING EVENT TO TRANSLATE:
{text}
"""
        response = groq_service.generate(prompt)
        return response