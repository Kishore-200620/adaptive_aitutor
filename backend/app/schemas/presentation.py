from pydantic import BaseModel
from typing import Optional
from enum import Enum

class PresentationMode(str, Enum):
    VOICE_ONLY = "VOICE_ONLY"
    VOICE_BLACKBOARD = "VOICE_BLACKBOARD"
    VOICE_TEACHER_VIDEO = "VOICE_TEACHER_VIDEO"
    VOICE_BLACKBOARD_TEACHER_VIDEO = "VOICE_BLACKBOARD_TEACHER_VIDEO"

class VoiceDecision(BaseModel):
    enabled: bool
    narration: str

class PdfVisualMetadata(BaseModel):
    visual_id: int
    document_id: int
    page_number: int
    visual_type: str
    asset_url: Optional[str] = None
    caption: Optional[str] = None
    metadata: dict = {}

class BlackboardDecision(BaseModel):
    enabled: bool
    content: str
    visual_type: str = "text"
    visual_source: str = "text" # "text", "generated_image", "pdf_visual", "local_diagram"
    visual_url: Optional[str] = None
    pdf_visual: Optional[PdfVisualMetadata] = None

class TeacherVideoTrigger(str, Enum):
    INTRO = "intro"
    CONCEPT_INTRO = "concept_intro"
    EMPHASIS = "emphasis"
    TRANSITION = "transition"
    ENCOURAGEMENT = "encouragement"
    COMPLETION = "completion"
    NONE = "none"

class TeacherVideoDecision(BaseModel):
    enabled: bool
    trigger: TeacherVideoTrigger = TeacherVideoTrigger.NONE
    reason: Optional[str] = None
    clip_id: Optional[str] = None
    provider: Optional[str] = None
    url: Optional[str] = None

class PresentationDecision(BaseModel):
    mode: PresentationMode
    voice: VoiceDecision
    blackboard: BlackboardDecision
    teacher_video: TeacherVideoDecision
