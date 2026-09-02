from fastapi import FastAPI

from app.api.routes.documents import router as documents_router
from app.api.routes.lessons import router as lessons_router
from app.api.routes.answers import router as answers_router
from app.api.routes.assessments import router as assessments_router
from app.api.routes.progress import router as progress_router
from app.api.routes.voice import router as voice_router
from app.api.routes.avatar import router as avatar_router
app = FastAPI(
    title="EDUVA",
    description="AI Teacher Platform",
    version="1.0.0",
)


app.include_router(documents_router)
app.include_router(lessons_router)
app.include_router(answers_router)
app.include_router(assessments_router)
app.include_router(progress_router)
app.include_router(voice_router)
app.include_router(avatar_router)

@app.get("/")
def root():
    return {
        "message": "EDUVA API is running"
    }