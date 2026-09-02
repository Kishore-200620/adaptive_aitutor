from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.avatar.jobs import (
    complete_job,
    create_job,
    fail_job,
    get_job,
)
from app.avatar.runner import generate_avatar_background


router = APIRouter(
    prefix="/avatar",
    tags=["Avatar"],
)




class AvatarGenerateRequest(BaseModel):
    audio_path: str
    filename: str = "teacher.mp4"




@router.post("/generate")
async def generate_avatar(
    request: AvatarGenerateRequest,
    background_tasks: BackgroundTasks,
):
    audio_path = Path(request.audio_path)

    if not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Audio file not found",
        )

    job_id = str(uuid4())

    create_job(job_id)

    background_tasks.add_task(
        generate_avatar_background,
        job_id,
        str(audio_path),
        request.filename,
    )

    return {
        "job_id": job_id,
        "status": "processing",
    }


@router.get("/status/{job_id}")
async def avatar_status(job_id: str):

    job = get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Avatar job not found",
        )

    return {
        "job_id": job_id,
        **job,
    }