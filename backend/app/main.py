from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.routes.documents import router as documents_router
from app.api.routes.lessons import router as lessons_router
from app.api.routes.answers import router as answers_router
from app.api.routes.assessments import router as assessments_router
from app.api.routes.progress import router as progress_router
from app.api.routes.voice import router as voice_router
from app.api.routes.avatar import router as avatar_router
from app.api.routes.students import router as students_router
from pathlib import Path

app = FastAPI(
    title="EDI-BUDDY",
    description="AI Teacher Platform",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)
app.include_router(lessons_router)
app.include_router(answers_router)
app.include_router(assessments_router)
app.include_router(progress_router)
app.include_router(voice_router)
app.include_router(avatar_router)
app.include_router(students_router)

static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
def root():
    return {
        "message": "EDUVA API is running"
    }