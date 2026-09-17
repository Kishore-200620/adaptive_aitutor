from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.voice.tts import tts_service


from uuid import uuid4

router = APIRouter(prefix="/voice", tags=["Voice"])




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

    filename = f"teacher_speech_{uuid4().hex}.mp3"

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


@router.get("/audio/status/{filename}")
def get_audio_status(filename: str):
    status = tts_service.job_status.get(filename)
    if status:
        return {"status": status}
    
    audio_dir = Path(tts_service.output_dir)
    audio_path = audio_dir / filename
    if audio_path.exists():
        return {"status": "ready"}
    
    return {"status": "failed"}


@router.get("/audio/{filename}")
def get_audio(filename: str):
    audio_dir = Path(tts_service.output_dir)
    audio_path = audio_dir / filename
    
    try:
        resolved_path = audio_path.resolve()
        resolved_dir = audio_dir.resolve()
        if not str(resolved_path).startswith(str(resolved_dir)):
            raise ValueError()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid filename")

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