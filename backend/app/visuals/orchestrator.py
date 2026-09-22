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
from app.visuals.fallback import EducationalFallbackRenderer
from app.teacher_video.provider import PredefinedVideoProvider

class PresentationOrchestrator:
    def __init__(self):
        self.visual_router = VisualRouter()
        self.image_service = ImageGenerationService()
        self.fallback_renderer = EducationalFallbackRenderer()
        self.video_provider = PredefinedVideoProvider()

    async def orchestrate(
        self,
        teacher_state: TeacherState,
        narration: str,
        blackboard_content: str,
        visual_directive: Optional[str] = None,
        pdf_visual_data: Optional[dict] = None,
        teaching_context: Optional[list[str]] = None,
        fetch_pdf_visual_cb = None
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
        
        pdf_visual_metadata = None
        pdf_visual_valid = False

        visual_required = bool(visual_directive and visual_directive.strip())

        if visual_required:
            import logging
            logger = logging.getLogger("eduva.orchestrator")
            logger.info("[EDUVA][Visuals] Mandatory visual request detected")
            logger.info("[EDUVA][Visuals] Checking relevant PDF visual")

            if pdf_visual_data:
                from app.schemas.presentation import PdfVisualMetadata
                from pathlib import Path
                asset_url = pdf_visual_data.get("asset_url")
                if asset_url:
                    file_path = Path(asset_url.lstrip("/"))
                    if file_path.exists():
                        pdf_visual_valid = True
                    else:
                        logger.warning(f"[EDUVA][Visuals] Selected PDF visual asset missing: {file_path}")
                
                if pdf_visual_valid:
                    metadata_dict = {
                        "visual_id": pdf_visual_data.get("id"),
                        "document_id": pdf_visual_data.get("document_id"),
                        "page_number": pdf_visual_data.get("page_number"),
                        "visual_type": pdf_visual_data.get("visual_type"),
                        "asset_url": asset_url,
                        "caption": pdf_visual_data.get("caption"),
                        "metadata": pdf_visual_data.get("metadata", {})
                    }
                    pdf_visual_metadata = PdfVisualMetadata(**metadata_dict)
                    bb_url = pdf_visual_metadata.asset_url
                    bb_source = "pdf_visual"
                    bb_type = "image"
                    logger.info("[EDUVA][Visuals] Mandatory visual satisfied\n"
                                f"        source={bb_source}\n"
                                f"        url={bb_url}")
            
            if not pdf_visual_valid:
                concept = (teacher_state.current_concept or teacher_state.topic)[:120]
                visual_subject = (visual_directive or "")[:300]
                
                logger.info(f"[EDUVA][Visuals] Raw visual directive: {visual_subject.replace(chr(10), ' ')}")
                
                # Analyze visual intent safely
                from app.visuals.fallback import VisualIntent
                try:
                    intent = self.fallback_renderer.analyze_intent(visual_directive, concept)
                except Exception as e:
                    logger.error(f"[EDUVA][Visuals] Error during intent analysis: {e}")
                    intent = VisualIntent(primary_intent="generic", components=[], is_photorealistic=False, routing_reason="fallback_due_to_exception")
                
                requested_subject = intent.components[0] if intent.components else (intent.composition_intent or intent.primary_intent)
                if requested_subject == "generated_image":
                    requested_subject = intent.composition_intent or "generic"

                logger.info(f"[EDUVA][Visuals] Lesson concept: {concept}")
                logger.info(f"[EDUVA][Visuals] Requested visual subject: {requested_subject}")
                
                if fetch_pdf_visual_cb:
                    logger.info(f"[EDUVA][Visuals] PDF visual search subject: {requested_subject}")
                    try:
                        new_pdf_data = fetch_pdf_visual_cb(requested_subject)
                        if new_pdf_data:
                            logger.info(f"[EDUVA][Visuals] Relevant PDF visual: {new_pdf_data.get('id')}")
                            pdf_visual_data = new_pdf_data
                            pdf_visual_valid = True
                            
                            asset_url = pdf_visual_data.get("asset_url")
                            from app.schemas.presentation import PdfVisualMetadata
                            metadata_dict = {
                                "visual_id": pdf_visual_data.get("id"),
                                "document_id": pdf_visual_data.get("document_id"),
                                "page_number": pdf_visual_data.get("page_number"),
                                "visual_type": pdf_visual_data.get("visual_type"),
                                "asset_url": asset_url,
                                "caption": pdf_visual_data.get("caption"),
                                "metadata": pdf_visual_data.get("metadata", {})
                            }
                            pdf_visual_metadata = PdfVisualMetadata(**metadata_dict)
                            bb_url = pdf_visual_metadata.asset_url
                            bb_source = "pdf_visual"
                            bb_type = "image"
                        else:
                            logger.info("[EDUVA][Visuals] Relevant PDF visual: none")
                    except Exception as e:
                        logger.error(f"Error fetching PDF visual for requested subject: {e}")
                        logger.info("[EDUVA][Visuals] Relevant PDF visual: none")
                else:
                    logger.info("[EDUVA][Visuals] Relevant PDF visual: none")
                    
                if not pdf_visual_valid and requested_subject != concept and intent.routing_reason != 'component comparison request':
                    intent.routing_reason = "requested subject overrides lesson topic for current visual request"
                    
                # If we STILL don't have a PDF visual, use the deterministic or GenAI renderer
                if not pdf_visual_valid:
                    logger.info(f"[EDUVA][Visuals] Visual intent: {intent.primary_intent}")
                    logger.info(f"[EDUVA][Visuals] Primary subject: {intent.composition_intent or intent.primary_intent}")
                    logger.info(f"[EDUVA][Visuals] Components detected: {', '.join(intent.components) if intent.components else 'none'}")
                    if intent.is_photorealistic:
                        logger.info(f"[EDUVA][Visuals] Visual style: {intent.visual_style}")
                    logger.info(f"[EDUVA][Visuals] Routing reason: {intent.routing_reason}")
                    
                    # Check for deterministic educational visual FIRST
                    if intent.primary_intent != "generic" and intent.primary_intent != "generated_image":
                        logger.info(f"[EDUVA][Visuals] Selected renderer: deterministic_{intent.primary_intent}")
                        fallback_url = self.fallback_renderer.render(visual_directive, concept)
                        if fallback_url:
                            bb_url = fallback_url
                            if "emergency_fallback" in fallback_url or "data:image" in fallback_url:
                                bb_source = "emergency_fallback"
                            else:
                                bb_source = "local_diagram"
                            bb_type = "image"
                            logger.info("[EDUVA][Visuals] Mandatory visual satisfied via deterministic renderer\n"
                                        f"        source={bb_source}\n"
                                        f"        url={bb_url}")
                        else:
                            bb_url = self.fallback_renderer.get_emergency_fallback()
                            bb_source = "emergency_fallback"
                            bb_type = "image"
                            logger.info("[EDUVA][Visuals] Mandatory visual satisfied via emergency fallback\n"
                                        f"        source={bb_source}\n"
                                        f"        url={bb_url}")
                    else:
                        # Proceed with GenAI (Pollinations) for generic open-ended visuals
                        logger.info("[EDUVA][Visuals] Selected renderer: flux")
                        
                        # Image Provider Model configuration logging
                        from app.core.config import settings
                        logger.info(f"[EDUVA][Visuals] Model: black-forest-labs/{settings.pollinations_image_model}")
                        
                        # Prompt Builder for FLUX.2 Max
                        subject = visual_subject if visual_directive else concept
                        components = ', '.join(intent.components) if intent.components else 'none specifically requested'
                        style = intent.visual_style if intent.is_photorealistic else 'clean educational illustration, textbook-style'
                        
                        target_visual = intent.composition_intent or subject
                        
                        grounded_prompt = (
                            f"Create a clear educational illustration of {target_visual}.\n"
                            f"Primary subject: {subject}\n"
                            f"Required objects: {components}\n"
                            f"Physical and spatial relationships: properly position and connect the components as described in the primary subject.\n"
                            f"Composition: clear, focused, neutral background.\n"
                            f"Labels: preserve any requested values or labels.\n"
                            f"Style: {style}.\n"
                            f"Exclusions: Do not include unrelated objects, concepts, text, decorations, or characters."
                        )
                        
                        # Remove line breaks for the actual request, but keep it clean
                        grounded_prompt = " ".join(grounded_prompt.split())[:1200]
                        
                        logger.info(f"[EDUVA][Visuals] Image prompt length: {len(grounded_prompt)}")
                        logger.info(f"[EDUVA][Visuals] Final image prompt: {grounded_prompt}")
                        
                        generated_url = await self.image_service.generate_image(grounded_prompt)
                        
                        if generated_url:
                            bb_url = generated_url
                            bb_source = "generated_image"
                            bb_type = "image"
                            logger.info("[EDUVA][Visuals] Mandatory visual satisfied via GenAI\n"
                                        f"        source={bb_source}\n"
                                        f"        url={bb_url}")
                        else:
                            logger.info("[EDUVA][Visuals] GenAI failed, using generic local fallback")
                            bb_url = self.fallback_renderer.render(visual_directive, concept)
                            if not bb_url:
                                bb_url = self.fallback_renderer.get_emergency_fallback()
                            bb_source = "emergency_fallback"
                            bb_type = "image"

            blackboard_enabled = True
            
            assert bb_type == "image", "MANDATORY VISUAL VIOLATION: bb_type must be 'image'"
            assert bb_url is not None, "MANDATORY VISUAL VIOLATION: bb_url cannot be None"
            assert bb_url != "", "MANDATORY VISUAL VIOLATION: bb_url cannot be empty"

        else:
            if pdf_visual_data:
                from app.schemas.presentation import PdfVisualMetadata
                import logging
                from pathlib import Path
                
                logger = logging.getLogger("eduva.orchestrator")
                asset_url = pdf_visual_data.get("asset_url")
                
                if asset_url:
                    file_path = Path(asset_url.lstrip("/"))
                    if file_path.exists():
                        pdf_visual_valid = True
                        metadata_dict = {
                            "visual_id": pdf_visual_data.get("id"),
                            "document_id": pdf_visual_data.get("document_id"),
                            "page_number": pdf_visual_data.get("page_number"),
                            "visual_type": pdf_visual_data.get("visual_type"),
                            "asset_url": asset_url,
                            "caption": pdf_visual_data.get("caption"),
                            "metadata": pdf_visual_data.get("metadata", {})
                        }
                        pdf_visual_metadata = PdfVisualMetadata(**metadata_dict)
                        bb_url = pdf_visual_metadata.asset_url
                        bb_source = "pdf_visual"
                        bb_type = "image"
                        blackboard_enabled = True

        blackboard_decision = BlackboardDecision(
            enabled=blackboard_enabled,
            content=bb_content,
            visual_type=bb_type,
            visual_source=bb_source,
            visual_url=bb_url,
            pdf_visual=pdf_visual_metadata
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
