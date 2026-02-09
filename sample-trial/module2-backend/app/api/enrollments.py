"""Enrollment management endpoints."""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_instructor_or_admin
from app.models.user import User
from app.models.course import Course
from app.models.enrollment import Enrollment
from app.schemas.enrollment import EnrollmentCreate, EnrollmentResponse, EnrollmentListResponse

router = APIRouter(prefix="/enrollments", tags=["enrollments"])


@router.get("/my-enrollments", response_model=List[EnrollmentResponse])
def get_my_enrollments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current student's enrollments."""
    enrollments = db.query(Enrollment).filter(
        Enrollment.student_id == current_user.id,
        Enrollment.is_active == True
    ).all()

    result = []
    for enrollment in enrollments:
        course = enrollment.course
        instructor_name = course.instructor.full_name if course.instructor else None

        result.append(EnrollmentResponse(
            id=enrollment.id,
            student_id=enrollment.student_id,
            course_id=enrollment.course_id,
            course_code=course.code,
            course_name=course.name,
            semester=course.semester,
            instructor_name=instructor_name,
            is_active=enrollment.is_active,
            enrolled_at=enrollment.enrolled_at,
        ))

    return result


@router.get("/course/{course_id}", response_model=EnrollmentListResponse)
def get_course_enrollments(
    course_id: str,
    is_active: bool = True,
    search: Optional[str] = None,
    current_user: User = Depends(get_instructor_or_admin),
    db: Session = Depends(get_db)
):
    """Get all students enrolled in a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    query = db.query(Enrollment).filter(Enrollment.course_id == course_id)

    if is_active is not None:
        query = query.filter(Enrollment.is_active == is_active)

    enrollments = query.all()

    students = []
    for enrollment in enrollments:
        student = enrollment.student
        if search and search.lower() not in student.full_name.lower() and search.lower() not in student.email.lower():
            continue

        students.append(EnrollmentResponse(
            id=enrollment.id,
            student_id=enrollment.student_id,
            course_id=enrollment.course_id,
            student_email=student.email,
            student_name=student.full_name,
            is_active=enrollment.is_active,
            enrolled_at=enrollment.enrolled_at,
            face_enrolled=student.face_enrolled,
        ))

    return EnrollmentListResponse(
        course_id=course_id,
        course_code=course.code,
        total_enrolled=len(students),
        students=students
    )


@router.post("/", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
def create_enrollment(
    enrollment_data: EnrollmentCreate,
    current_user: User = Depends(get_instructor_or_admin),
    db: Session = Depends(get_db)
):
    """Enroll a student in a course."""
    # Check student exists
    student = db.query(User).filter(User.id == enrollment_data.student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )

    # Check course exists
    course = db.query(Course).filter(Course.id == enrollment_data.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    # Check permissions (must be course instructor or admin)
    if current_user.role != "admin" and course.instructor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to enroll students in this course"
        )

    # Check not already enrolled
    existing = db.query(Enrollment).filter(
        Enrollment.student_id == enrollment_data.student_id,
        Enrollment.course_id == enrollment_data.course_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student already enrolled"
        )

    enrollment = Enrollment(
        student_id=enrollment_data.student_id,
        course_id=enrollment_data.course_id,
        enrolled_at=datetime.now(timezone.utc),
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    return EnrollmentResponse(
        id=enrollment.id,
        student_id=enrollment.student_id,
        course_id=enrollment.course_id,
        course_code=course.code,
        course_name=course.name,
        is_active=enrollment.is_active,
        enrolled_at=enrollment.enrolled_at,
    )


class BulkEnrollRequest(BaseModel):
    course_id: str
    student_emails: List[str]
    create_accounts: bool = False


class BulkEnrollResponse(BaseModel):
    enrolled: int
    already_enrolled: int
    not_found: int
    created: int
    details: List[dict]


@router.post("/bulk", response_model=BulkEnrollResponse)
def bulk_enroll(
    data: BulkEnrollRequest,
    current_user: User = Depends(get_instructor_or_admin),
    db: Session = Depends(get_db)
):
    """Bulk enroll students by email."""
    course = db.query(Course).filter(Course.id == data.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    # Check permissions
    if current_user.role != "admin" and course.instructor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to enroll students in this course"
        )

    enrolled = 0
    already_enrolled = 0
    not_found = 0
    created = 0
    details = []

    for email in data.student_emails:
        student = db.query(User).filter(User.email == email).first()

        if not student:
            not_found += 1
            details.append({"email": email, "status": "not_found"})
            continue

        existing = db.query(Enrollment).filter(
            Enrollment.student_id == student.id,
            Enrollment.course_id == data.course_id
        ).first()

        if existing:
            already_enrolled += 1
            details.append({"email": email, "status": "already_enrolled"})
            continue

        enrollment = Enrollment(
            student_id=student.id,
            course_id=data.course_id,
            enrolled_at=datetime.now(timezone.utc),
        )
        db.add(enrollment)
        enrolled += 1
        details.append({"email": email, "status": "enrolled"})

    db.commit()

    return BulkEnrollResponse(
        enrolled=enrolled,
        already_enrolled=already_enrolled,
        not_found=not_found,
        created=created,
        details=details
    )


@router.delete("/{enrollment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_enrollment(
    enrollment_id: str,
    current_user: User = Depends(get_instructor_or_admin),
    db: Session = Depends(get_db)
):
    """Remove an enrollment."""
    enrollment = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found"
        )

    course = enrollment.course
    if current_user.role != "admin" and course.instructor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to remove this enrollment"
        )

    db.delete(enrollment)
    db.commit()
    return None
