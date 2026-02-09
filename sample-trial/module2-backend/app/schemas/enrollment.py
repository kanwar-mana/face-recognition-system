"""Enrollment schemas."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class EnrollmentCreate(BaseModel):
    """Schema for creating an enrollment."""
    student_id: str
    course_id: str


class EnrollmentResponse(BaseModel):
    """Schema for enrollment response."""
    id: str
    student_id: str
    course_id: str
    course_code: Optional[str] = None
    course_name: Optional[str] = None
    semester: Optional[str] = None
    instructor_name: Optional[str] = None
    student_email: Optional[str] = None
    student_name: Optional[str] = None
    is_active: bool = True
    enrolled_at: datetime
    face_enrolled: Optional[bool] = None

    class Config:
        from_attributes = True


class EnrollmentListResponse(BaseModel):
    """Schema for enrollment list response."""
    course_id: str
    course_code: Optional[str] = None
    total_enrolled: int
    students: List[EnrollmentResponse]
