from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.voice.tts import TTSService


router = APIRouter(prefix="/voice", tags=["Voice"])

tts_service = TTSService()


class SpeechRequest(BaseModel):
    text: str
    language: str = "English"


@router.post("/synthesize")
async def synthesize_speech(request: SpeechRequest):
    if not request.text.strip():
        raise HTTPException(
            status_code=400,
            detail="Text cannot be empty",
        )

    filename = "teacher_speech.mp3"

    output_path = await tts_service.generate_speech(
        text=request.text,
        language=request.language,
        filename=filename,
    )

    return {
        "message": "Speech generated successfully",
        "language": request.language,
        "audio_file": filename,
        "audio_url": f"/voice/audio/{filename}",
    }


@router.get("/audio/{filename}")
def get_audio(filename: str):
    audio_dir = Path(tts_service.output_dir)
    audio_path = audio_dir / filename

    if not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Audio file not found",
        )

    return FileResponse(
        path=audio_path,
        media_type="audio/mpeg",
        filename=filename,
    )