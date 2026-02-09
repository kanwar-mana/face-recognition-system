"""Course management endpoints."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_admin_user
from app.models.user import User
from app.models.course import Course
from app.schemas.course import CourseCreate, CourseResponse, CourseUpdate, CourseListResponse

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("/", response_model=CourseListResponse)
def list_courses(
    is_active: Optional[bool] = True,
    semester: Optional[str] = None,
    instructor_id: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all courses."""
    query = db.query(Course)

    if is_active is not None:
        query = query.filter(Course.is_active == is_active)
    if semester:
        query = query.filter(Course.semester == semester)
    if instructor_id and current_user.role == "admin":
        query = query.filter(Course.instructor_id == instructor_id)

    total = query.count()
    courses = query.offset(offset).limit(limit).all()

    items = []
    for course in courses:
        instructor_name = None
        if course.instructor:
            instructor_name = course.instructor.full_name

        items.append(CourseResponse(
            id=course.id,
            code=course.code,
            name=course.name,
            semester=course.semester,
            description=course.description,
            instructor_id=course.instructor_id,
            instructor_name=instructor_name,
            venue_latitude=course.venue_latitude,
            venue_longitude=course.venue_longitude,
            venue_name=course.venue_name,
            geofence_radius_meters=course.geofence_radius_meters,
            require_face_recognition=course.require_face_recognition,
            require_device_binding=course.require_device_binding,
            risk_threshold=course.risk_threshold,
            is_active=course.is_active,
            created_at=course.created_at,
        ))

    return CourseListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset
    )


@router.post("/", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(
    course_data: CourseCreate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Create a new course (admin only)."""
    # Check code uniqueness
    existing = db.query(Course).filter(Course.code == course_data.code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course code already exists"
        )

    course = Course(
        code=course_data.code,
        name=course_data.name,
        semester=course_data.semester,
        description=course_data.description,
        instructor_id=course_data.instructor_id,
        venue_latitude=course_data.venue_latitude,
        venue_longitude=course_data.venue_longitude,
        venue_name=course_data.venue_name,
        geofence_radius_meters=course_data.geofence_radius_meters,
        require_face_recognition=course_data.require_face_recognition,
        require_device_binding=course_data.require_device_binding,
        risk_threshold=course_data.risk_threshold,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(course)
    db.commit()
    db.refresh(course)

    return CourseResponse.model_validate(course)


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get course details."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    instructor_name = None
    if course.instructor:
        instructor_name = course.instructor.full_name

    return CourseResponse(
        id=course.id,
        code=course.code,
        name=course.name,
        semester=course.semester,
        description=course.description,
        instructor_id=course.instructor_id,
        instructor_name=instructor_name,
        venue_latitude=course.venue_latitude,
        venue_longitude=course.venue_longitude,
        venue_name=course.venue_name,
        geofence_radius_meters=course.geofence_radius_meters,
        require_face_recognition=course.require_face_recognition,
        require_device_binding=course.require_device_binding,
        risk_threshold=course.risk_threshold,
        is_active=course.is_active,
        created_at=course.created_at,
    )


@router.put("/{course_id}", response_model=CourseResponse)
def update_course(
    course_id: str,
    update_data: CourseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    # Check permissions (admin or course instructor)
    if current_user.role != "admin" and course.instructor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this course"
        )

    # Apply updates
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(course, key, value)

    course.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(course)

    return CourseResponse.model_validate(course)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(
    course_id: str,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Soft-delete a course (admin only)."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    course.is_active = False
    course.updated_at = datetime.now(timezone.utc)
    db.commit()
    return None
