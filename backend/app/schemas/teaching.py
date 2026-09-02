from pydantic import BaseModel
from typing import Optional


class SpeechEvent(BaseModel):
    text: str
    audio_url: Optional[str] = None
    avatar_job_id: Optional[str] = None
    avatar_status_url: Optional[str] = None


class VisualEvent(BaseModel):
    type: str
    content: str
    title: Optional[str] = None


class QuestionEvent(BaseModel):
    text: str
    type: str = "open_ended"


class TeachingEvent(BaseModel):
    speech: SpeechEvent
    visual: Optional[VisualEvent] = None
    question: QuestionEvent