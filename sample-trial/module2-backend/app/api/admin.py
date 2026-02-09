"""Admin endpoints (CRITICAL for test fixtures)."""
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_admin_user
from app.core.security import get_password_hash
from app.models.user import User
from app.models.session import Session as SessionModel
from app.models.enrollment import Enrollment
from app.schemas.user import UserCreate, UserResponse
from app.schemas.enrollment import EnrollmentCreate, EnrollmentResponse

router = APIRouter(prefix="/admin", tags=["admin"])


class SessionStatusUpdate(BaseModel):
    """Schema for session status update."""
    status: str


class BulkUserCreate(BaseModel):
    """Schema for bulk user creation."""
    users: List[UserCreate]


class BulkUserResponse(BaseModel):
    """Response for bulk user creation."""
    created: int
    failed: int
    users: List[UserResponse]
    errors: List[str]


@router.patch("/users/{user_id}/deactivate")
def deactivate_user(
    user_id: str,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Deactivate a user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user.is_active = False
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "email": user.email,
        "is_active": user.is_active,
        "message": "User deactivated successfully"
    }


@router.patch("/users/{user_id}/activate")
def activate_user(
    user_id: str,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Activate a user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user.is_active = True
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "email": user.email,
        "is_active": user.is_active,
        "message": "User activated successfully"
    }


@router.post("/users/bulk", response_model=BulkUserResponse, status_code=status.HTTP_201_CREATED)
def bulk_create_users(
    data: BulkUserCreate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Bulk create users."""
    created_users = []
    errors = []

    for user_data in data.users:
        try:
            # Check if email already exists
            existing = db.query(User).filter(User.email == user_data.email).first()
            if existing:
                errors.append(f"Email {user_data.email} already exists")
                continue

            user = User(
                email=user_data.email,
                full_name=user_data.full_name,
                hashed_password=get_password_hash(user_data.password),
                role=user_data.role,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(user)
            db.flush()  # Get the ID without committing
            created_users.append(user)
        except Exception as e:
            errors.append(f"Error creating {user_data.email}: {str(e)}")

    db.commit()

    return BulkUserResponse(
        created=len(created_users),
        failed=len(errors),
        users=[UserResponse.model_validate(u) for u in created_users],
        errors=errors
    )


@router.patch("/sessions/{session_id}/status")
def update_session_status(
    session_id: str,
    status_update: SessionStatusUpdate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Update session status (CRITICAL for check-in tests)."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    valid_statuses = ["scheduled", "active", "closed", "cancelled"]
    if status_update.status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    old_status = session.status
    session.status = status_update.status
    session.updated_at = datetime.now(timezone.utc)

    # Set actual_start when activating
    if status_update.status == "active" and old_status != "active":
        session.actual_start = datetime.now(timezone.utc)

    # Set actual_end when closing
    if status_update.status == "closed" and old_status != "closed":
        session.actual_end = datetime.now(timezone.utc)

    db.commit()
    db.refresh(session)

    return {
        "id": session.id,
        "name": session.name,
        "status": session.status,
        "message": f"Session status changed from '{old_status}' to '{session.status}'"
    }


@router.post("/enrollments/", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
def admin_create_enrollment(
    enrollment_data: EnrollmentCreate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Create enrollment (admin bypass for test fixtures)."""
    # Check student exists
    student = db.query(User).filter(User.id == enrollment_data.student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )

    # Check course exists
    from app.models.course import Course
    course = db.query(Course).filter(Course.id == enrollment_data.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
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
