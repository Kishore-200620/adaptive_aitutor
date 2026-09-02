from app.avatar.jobs import (
    complete_job,
    fail_job,
)
from app.avatar.service import AvatarService


avatar_service = AvatarService()


async def generate_avatar_background(
    job_id: str,
    audio_path: str,
    filename: str,
):
    try:
        video_path = await avatar_service.generate_video(
            audio_path=audio_path,
            filename=filename,
        )

        complete_job(
            job_id=job_id,
            video_path=video_path,
        )

    except Exception as exc:
        fail_job(
            job_id=job_id,
            error=str(exc),
        )