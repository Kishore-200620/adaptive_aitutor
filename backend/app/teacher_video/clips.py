from app.schemas.presentation import TeacherVideoTrigger
import os
from pathlib import Path

# In a real environment, these would map to actual static assets.
# We map TeacherVideoTrigger to a dict containing the file path/url, clip_id, and duration.
# "file_path" should be relative to the static directory or an absolute URL.
PREDEFINED_CLIPS = {
    TeacherVideoTrigger.INTRO: {
        "clip_id": "intro_mp4",
        "url": "/teacher_videos/intro.mp4",
        "duration": 0.0 # Will depend on actual file
    },
    TeacherVideoTrigger.CONCEPT_INTRO: {
        "clip_id": "concept_intro_mp4",
        "url": "/teacher_videos/concept_intro.mp4",
        "duration": 0.0
    }
}

def check_asset_exists(url_or_path: str) -> bool:
    """
    Checks if a predefined video clip actually exists.
    If it's a relative path, checks the local filesystem.
    """
    if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
        # Assume external URLs are valid for now, or could make a HEAD request.
        return True
    
    # Check local public directory
    base_dir = Path(__file__).parent.parent.parent.parent / "frontend" / "public"
    
    if url_or_path.startswith("/"):
        url_or_path = url_or_path[1:]
        
    local_path = base_dir / url_or_path
    return local_path.exists()
