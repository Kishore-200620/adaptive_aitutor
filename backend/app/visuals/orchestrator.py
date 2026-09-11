from typing import Optional
from app.teacher.state import TeacherState
from app.schemas.presentation import (
    PresentationDecision,
    PresentationMode,
    VoiceDecision,
    BlackboardDecision,
    TeacherVideoDecision,
    TeacherVideoTrigger
)
from app.schemas.teaching import VisualEvent
from app.visuals.router import VisualRouter
from app.visuals.pollinations import ImageGenerationService
from app.teacher_video.provider import PredefinedVideoProvider

class PresentationOrchestrator:
    def __init__(self):
        self.visual_router = VisualRouter()
        self.image_service = ImageGenerationService()
        self.video_provider = PredefinedVideoProvider()

    async def orchestrate(
        self,
        teacher_state: TeacherState,
        narration: str,
        blackboard_content: str,
        visual_directive: Optional[str] = None
    ) -> PresentationDecision:
        """
        Takes the parsed outputs from the Teacher Brain and decides the presentation layer.
        """
        
        # 1. Voice
        voice_decision = VoiceDecision(
            enabled=bool(narration),
            narration=narration or ""
        )

        # 2. Blackboard
        # Use existing VisualRouter to classify content
        visual_event: Optional[VisualEvent] = self.visual_router.generate(
            teaching=blackboard_content or narration,
            concept=teacher_state.current_concept or teacher_state.topic
        )
        
        blackboard_enabled = bool(blackboard_content or visual_event)
        
        bb_type = visual_event.type if visual_event else "blackboard"
        bb_content = blackboard_content if blackboard_content else (visual_event.content if visual_event else "")
        bb_url = visual_event.url if visual_event else None
        bb_source = "pdf_image" if bb_url else "text"

        # If visual directive exists and we don't have a PDF URL, generate image
        if visual_directive and not bb_url:
            generated_url = await self.image_service.generate_image(visual_directive)
            if generated_url:
                bb_url = generated_url
                bb_source = "generated_image"
                bb_type = "image"
                blackboard_enabled = True

        blackboard_decision = BlackboardDecision(
            enabled=blackboard_enabled,
            content=bb_content,
            visual_type=bb_type,
            visual_source=bb_source,
            visual_url=bb_url
        )

        # 3. Teacher Video
        trigger = TeacherVideoTrigger.NONE
        video_reason = None
        
        if teacher_state.current_phase == "introduction":
            if not teacher_state.concepts_completed:
                trigger = TeacherVideoTrigger.INTRO
                video_reason = "introduction"
            else:
                trigger = TeacherVideoTrigger.CONCEPT_INTRO
                video_reason = "concept_introduction"
        elif teacher_state.current_phase == "completed":
            trigger = TeacherVideoTrigger.COMPLETION
            video_reason = "completion"
        elif teacher_state.current_phase == "transition":
            trigger = TeacherVideoTrigger.TRANSITION
            video_reason = "transition"
        elif teacher_state.needs_reteaching and teacher_state.attempt_count == 1:
            trigger = TeacherVideoTrigger.ENCOURAGEMENT
            video_reason = "encouragement"

        video_decision = TeacherVideoDecision(enabled=False, trigger=trigger, reason=video_reason)

        import os
        video_enabled_env = os.environ.get("TEACHER_VIDEO_ENABLED", "false").lower() == "true"

        if trigger != TeacherVideoTrigger.NONE and video_enabled_env:
            clip = self.video_provider.get_clip(trigger)
            if clip:
                video_decision.enabled = True
                video_decision.clip_id = clip.get("clip_id")
                video_decision.url = clip.get("url")
                video_decision.provider = clip.get("provider")

        # 4. Mode determination
        if voice_decision.enabled and blackboard_decision.enabled and video_decision.enabled:
            mode = PresentationMode.VOICE_BLACKBOARD_TEACHER_VIDEO
        elif voice_decision.enabled and blackboard_decision.enabled:
            mode = PresentationMode.VOICE_BLACKBOARD
        elif voice_decision.enabled and video_decision.enabled:
            mode = PresentationMode.VOICE_TEACHER_VIDEO
        else:
            mode = PresentationMode.VOICE_ONLY

        return PresentationDecision(
            mode=mode,
            voice=voice_decision,
            blackboard=blackboard_decision,
            teacher_video=video_decision
        )
