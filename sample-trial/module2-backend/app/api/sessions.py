"""Session management endpoints."""
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_instructor_or_admin
from app.models.user import User
from app.models.course import Course
from app.models.session import Session as SessionModel
from app.models.enrollment import Enrollment
from app.models.checkin import CheckIn
from app.schemas.session import SessionCreate, SessionResponse, SessionUpdate, SessionListResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])


def get_session_response(session: SessionModel, db: Session) -> SessionResponse:
    """Helper to build session response with computed fields."""
    course = session.course
    course_code = course.code if course else None
    course_name = course.name if course else None

    # Count enrolled students
    total_enrolled = db.query(Enrollment).filter(
        Enrollment.course_id == session.course_id,
        Enrollment.is_active == True
    ).count()

    # Count check-ins
    checked_in_count = db.query(CheckIn).filter(
        CheckIn.session_id == session.id
    ).count()

    return SessionResponse(
        id=session.id,
        course_id=session.course_id,
        course_code=course_code,
        course_name=course_name,
        instructor_id=session.instructor_id,
        name=session.name,
        session_type=session.session_type,
        description=session.description,
        status=session.status,
        scheduled_start=session.scheduled_start,
        scheduled_end=session.scheduled_end,
        checkin_opens_at=session.checkin_opens_at,
        checkin_closes_at=session.checkin_closes_at,
        venue_latitude=session.venue_latitude or (course.venue_latitude if course else None),
        venue_longitude=session.venue_longitude or (course.venue_longitude if course else None),
        venue_name=session.venue_name or (course.venue_name if course else None),
        geofence_radius_meters=session.geofence_radius_meters or (course.geofence_radius_meters if course else 100.0),
        require_liveness_check=session.require_liveness_check,
        require_face_match=session.require_face_match,
        risk_threshold=session.risk_threshold or (course.risk_threshold if course else 0.5),
        total_enrolled=total_enrolled,
        checked_in_count=checked_in_count,
        created_at=session.created_at,
    )


@router.get("/active", response_model=List[SessionResponse])
def list_active_sessions(db: Session = Depends(get_db)):
    """List all currently active check-in sessions (public)."""
    now = datetime.now(timezone.utc)
    sessions = db.query(SessionModel).filter(
        SessionModel.status == "active",
        SessionModel.checkin_opens_at <= now,
        SessionModel.checkin_closes_at >= now
    ).all()

    return [get_session_response(s, db) for s in sessions]


@router.get("/", response_model=SessionListResponse)
def list_sessions(
    status: Optional[str] = None,
    course_id: Optional[str] = None,
    instructor_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    current_user: User = Depends(get_instructor_or_admin),
    db: Session = Depends(get_db)
):
    """List all sessions (instructor/admin)."""
    query = db.query(SessionModel)

    if status:
        query = query.filter(SessionModel.status == status)
    if course_id:
        query = query.filter(SessionModel.course_id == course_id)
    if instructor_id:
        query = query.filter(SessionModel.instructor_id == instructor_id)
    if start_date:
        query = query.filter(SessionModel.scheduled_start >= start_date)
    if end_date:
        query = query.filter(SessionModel.scheduled_start <= end_date)

    total = query.count()
    sessions = query.order_by(SessionModel.scheduled_start.desc()).offset(offset).limit(limit).all()

    return SessionListResponse(
        items=[get_session_response(s, db) for s in sessions],
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/my-sessions", response_model=List[SessionResponse])
def list_my_sessions(
    status: Optional[str] = None,
    upcoming: bool = False,
    limit: int = Query(50, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List sessions relevant to current user."""
    if current_user.role in ("instructor", "admin"):
        # Show sessions they teach
        query = db.query(SessionModel).filter(SessionModel.instructor_id == current_user.id)
    else:
        # Show sessions for enrolled courses
        enrolled_course_ids = db.query(Enrollment.course_id).filter(
            Enrollment.student_id == current_user.id,
            Enrollment.is_active == True
        ).subquery()
        query = db.query(SessionModel).filter(SessionModel.course_id.in_(enrolled_course_ids))

    if status:
        query = query.filter(SessionModel.status == status)
    if upcoming:
        now = datetime.now(timezone.utc)
        query = query.filter(SessionModel.scheduled_start >= now)

    sessions = query.order_by(SessionModel.scheduled_start).limit(limit).all()
    return [get_session_response(s, db) for s in sessions]


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    session_data: SessionCreate,
    current_user: User = Depends(get_instructor_or_admin),
    db: Session = Depends(get_db)
):
    """Create a new session."""
    # Verify course exists
    course = db.query(Course).filter(Course.id == session_data.course_id).first()
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )

    # Check permissions (must be instructor role or admin)
    # Note: Any instructor can create sessions - course assignment is optional
    if current_user.role not in ("admin", "instructor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create sessions"
        )

    # Set default check-in times if not provided
    checkin_opens_at = session_data.checkin_opens_at
    if not checkin_opens_at:
        checkin_opens_at = session_data.scheduled_start - timedelta(minutes=15)

    checkin_closes_at = session_data.checkin_closes_at
    if not checkin_closes_at:
        checkin_closes_at = session_data.scheduled_start + timedelta(minutes=30)

    session = SessionModel(
        course_id=session_data.course_id,
        instructor_id=current_user.id,
        name=session_data.name,
        session_type=session_data.session_type,
        description=session_data.description,
        scheduled_start=session_data.scheduled_start,
        scheduled_end=session_data.scheduled_end,
        checkin_opens_at=checkin_opens_at,
        checkin_closes_at=checkin_closes_at,
        venue_latitude=session_data.venue_latitude,
        venue_longitude=session_data.venue_longitude,
        venue_name=session_data.venue_name,
        geofence_radius_meters=session_data.geofence_radius_meters,
        require_liveness_check=session_data.require_liveness_check,
        require_face_match=session_data.require_face_match,
        risk_threshold=session_data.risk_threshold,
        status="scheduled",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return get_session_response(session, db)


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get session details."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    return get_session_response(session, db)


@router.patch("/{session_id}", response_model=SessionResponse)
def update_session(
    session_id: str,
    update_data: SessionUpdate,
    current_user: User = Depends(get_instructor_or_admin),
    db: Session = Depends(get_db)
):
    """Update a session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # Check permissions
    if current_user.role != "admin" and session.instructor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this session"
        )

    # Apply updates
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(session, key, value)

    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)

    return get_session_response(session, db)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: str,
    current_user: User = Depends(get_instructor_or_admin),
    db: Session = Depends(get_db)
):
    """Delete a session (only scheduled sessions)."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # Check permissions
    if current_user.role != "admin" and session.instructor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this session"
        )

    # Can only delete scheduled sessions
    if session.status != "scheduled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only delete scheduled sessions. Use cancel for active sessions."
        )

    db.delete(session)
    db.commit()
    return None
