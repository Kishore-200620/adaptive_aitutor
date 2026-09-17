from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.models.student import Student

router = APIRouter(
    prefix="/students",
    tags=["Students"],
)

@router.post("/init")
def init_student(
    db: Session = Depends(get_db),
):
    """
    Initialize a default student if none exists.
    Returns the student_id to be used by the frontend.
    """
    student = db.query(Student).first()
    if not student:
        student = Student(
            name="Guest Student",
            preferred_language="English",
            education_level="beginner"
        )
        db.add(student)
        db.commit()
        db.refresh(student)
        
    return {
        "student_id": student.id,
        "name": student.name
    }
