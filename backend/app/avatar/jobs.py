from typing import Any


avatar_jobs: dict[str, dict[str, Any]] = {}


def create_job(job_id: str):
    avatar_jobs[job_id] = {
        "status": "processing",
        "video_path": None,
        "error": None,
    }


def complete_job(
    job_id: str,
    video_path: str,
):
    avatar_jobs[job_id] = {
        "status": "completed",
        "video_path": video_path,
        "error": None,
    }


def fail_job(
    job_id: str,
    error: str,
):
    avatar_jobs[job_id] = {
        "status": "failed",
        "video_path": None,
        "error": error,
    }


def get_job(job_id: str):
    return avatar_jobs.get(job_id)