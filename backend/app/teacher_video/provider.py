from abc import ABC, abstractmethod
from typing import Optional
from app.schemas.presentation import TeacherVideoTrigger
from app.teacher_video.clips import PREDEFINED_CLIPS, check_asset_exists

class TeacherVideoProvider(ABC):
    @abstractmethod
    def get_clip(self, trigger: TeacherVideoTrigger) -> Optional[dict]:
        """
        Returns a dictionary containing the clip information if available,
        otherwise returns None.
        
        Expected dictionary format:
        {
            "clip_id": str,
            "url": str,
            "duration": float,
            "provider": str
        }
        """
        pass

class PredefinedVideoProvider(TeacherVideoProvider):
    def get_clip(self, trigger: TeacherVideoTrigger) -> Optional[dict]:
        if trigger not in PREDEFINED_CLIPS:
            return None
            
        clip_data = PREDEFINED_CLIPS[trigger]
        url = clip_data.get("url")
        
        if not url or not check_asset_exists(url):
            return None
            
        return {
            "clip_id": clip_data.get("clip_id"),
            "url": url,
            "duration": clip_data.get("duration"),
            "provider": "predefined"
        }
