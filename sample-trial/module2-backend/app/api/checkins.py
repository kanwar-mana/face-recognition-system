"""Check-in endpoints."""
import json
from datetime import datetime, timezone
from typing import Optional, List
from math import radians, sin, cos, sqrt, atan2
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_instructor_ta_or_admin
from app.models.user import User
from app.models.course import Course
from app.models.session import Session as SessionModel
from app.models.enrollment import Enrollment
from app.models.checkin import CheckIn
from app.schemas.checkin import CheckInCreate, CheckInResponse, CheckInListResponse

router = APIRouter(prefix="/checkins", tags=["checkins"])


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters using Haversine formula."""
    R = 6371000  # Earth's radius in meters

    lat1_rad, lon1_rad = radians(lat1), radians(lon1)
    lat2_rad, lon2_rad = radians(lat2), radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c


def calculate_risk_score(checkin: CheckIn, session: SessionModel, course: Course) -> tuple:
    """Calculate risk score and factors for a check-in."""
    risk_factors = []
    total_risk = 0.0

    # Distance risk
    if checkin.distance_from_venue_meters is not None:
        geofence = session.geofence_radius_meters or course.geofence_radius_meters or 100.0
        if checkin.distance_from_venue_meters > geofence:
            # Outside geofence
            excess_ratio = checkin.distance_from_venue_meters / geofence
            geo_risk = min(0.4, 0.1 * excess_ratio)
            total_risk += geo_risk
            risk_factors.append({
                "type": "geo_out_of_bounds",
                "weight": geo_risk,
                "severity": "high" if excess_ratio > 2 else "medium"
            })

    # Liveness risk
    if checkin.liveness_score is not None:
        if checkin.liveness_score < 0.6:
            liveness_risk = (0.6 - checkin.liveness_score) * 0.5
            total_risk += liveness_risk
            risk_factors.append({
                "type": "liveness_low_confidence",
                "weight": liveness_risk,
                "severity": "high" if checkin.liveness_score < 0.3 else "medium"
            })

    # Face match risk
    if checkin.face_match_score is not None:
        if checkin.face_match_score < 0.7:
            face_risk = (0.7 - checkin.face_match_score) * 0.5
            total_risk += face_risk
            risk_factors.append({
                "type": "face_match_low_confidence",
                "weight": face_risk,
                "severity": "high" if checkin.face_match_score < 0.4 else "medium"
            })

    # Unknown device risk
    if checkin.device_id is None:
        total_risk += 0.15
        risk_factors.append({
            "type": "device_unknown",
            "weight": 0.15,
            "severity": "medium"
        })

    return min(1.0, total_risk), risk_factors


def get_checkin_status(risk_score: float, session: SessionModel, course: Course) -> str:
    """Determine check-in status based on risk score."""
    threshold = session.risk_threshold or course.risk_threshold or 0.5

    if risk_score >= threshold:
        return "flagged"
    return "approved"


def build_checkin_response(checkin: CheckIn, db: Session) -> CheckInResponse:
    """Build check-in response with related data."""
    session = checkin.session
    student = checkin.student

    risk_factors = []
    if checkin.risk_factors:
        try:
            risk_factors = json.loads(checkin.risk_factors)
        except:
            pass

    return CheckInResponse(
        id=checkin.id,
        session_id=checkin.session_id,
        session_name=session.name if session else None,
        student_id=checkin.student_id,
        student_name=student.full_name if student else None,
        student_email=student.email if student else None,
        status=checkin.status,
        checked_in_at=checkin.checked_in_at,
        latitude=checkin.latitude,
        longitude=checkin.longitude,
        distance_from_venue_meters=checkin.distance_from_venue_meters,
        liveness_passed=checkin.liveness_passed,
        liveness_score=checkin.liveness_score,
        face_match_passed=checkin.face_match_passed,
        face_match_score=checkin.face_match_score,
        risk_score=checkin.risk_score,
        risk_factors=risk_factors,
        device_trusted=checkin.device.is_trusted if checkin.device else None,
        course_code=session.course.code if session and session.course else None,
    )


@router.post("/", response_model=CheckInResponse, status_code=status.HTTP_201_CREATED)
def create_checkin(
    checkin_data: CheckInCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit a check-in."""
    # Verify session exists
    session = db.query(SessionModel).filter(SessionModel.id == checkin_data.session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # Verify session is active
    if session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is not active"
        )

    # Check check-in window
    now = datetime.now(timezone.utc)
    if now < session.checkin_opens_at.replace(tzinfo=timezone.utc) or now > session.checkin_closes_at.replace(tzinfo=timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Check-in window is closed"
        )

    # Verify enrollment
    enrollment = db.query(Enrollment).filter(
        Enrollment.student_id == current_user.id,
        Enrollment.course_id == session.course_id,
        Enrollment.is_active == True
    ).first()
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not enrolled in this course"
        )

    # Check for existing check-in
    existing = db.query(CheckIn).filter(
        CheckIn.session_id == checkin_data.session_id,
        CheckIn.student_id == current_user.id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already checked in to this session"
        )

    # Calculate distance from venue
    distance = None
    course = session.course
    venue_lat = session.venue_latitude or course.venue_latitude
    venue_lon = session.venue_longitude or course.venue_longitude

    if venue_lat and venue_lon and checkin_data.latitude and checkin_data.longitude:
        distance = haversine_distance(
            checkin_data.latitude, checkin_data.longitude,
            venue_lat, venue_lon
        )

    # Create check-in
    checkin = CheckIn(
        session_id=checkin_data.session_id,
        student_id=current_user.id,
        latitude=checkin_data.latitude,
        longitude=checkin_data.longitude,
        location_accuracy_meters=checkin_data.location_accuracy_meters,
        distance_from_venue_meters=distance,
        checked_in_at=datetime.now(timezone.utc),
    )

    # Calculate risk score
    risk_score, risk_factors = calculate_risk_score(checkin, session, course)
    checkin.risk_score = risk_score
    checkin.risk_factors = json.dumps(risk_factors) if risk_factors else None

    # Determine status
    checkin.status = get_checkin_status(risk_score, session, course)
    if checkin.status == "approved":
        checkin.verified_at = datetime.now(timezone.utc)

    db.add(checkin)
    db.commit()
    db.refresh(checkin)

    return build_checkin_response(checkin, db)


@router.get("/", response_model=CheckInListResponse)
def list_checkins(
    session_id: Optional[str] = None,
    course_id: Optional[str] = None,
    student_id: Optional[str] = None,
    status: Optional[str] = None,
    min_risk_score: Optional[float] = None,
    max_risk_score: Optional[float] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    current_user: User = Depends(get_instructor_ta_or_admin),
    db: Session = Depends(get_db)
):
    """List check-ins with filters (instructor/TA/admin)."""
    query = db.query(CheckIn)

    if session_id:
        query = query.filter(CheckIn.session_id == session_id)
    if student_id:
        query = query.filter(CheckIn.student_id == student_id)
    if status:
        query = query.filter(CheckIn.status == status)
    if min_risk_score is not None:
        query = query.filter(CheckIn.risk_score >= min_risk_score)
    if max_risk_score is not None:
        query = query.filter(CheckIn.risk_score <= max_risk_score)
    if start_date:
        query = query.filter(CheckIn.checked_in_at >= start_date)
    if end_date:
        query = query.filter(CheckIn.checked_in_at <= end_date)

    if course_id:
        query = query.join(SessionModel).filter(SessionModel.course_id == course_id)

    total = query.count()
    checkins = query.order_by(CheckIn.checked_in_at.desc()).offset(offset).limit(limit).all()

    return CheckInListResponse(
        items=[build_checkin_response(c, db) for c in checkins],
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/my-checkins", response_model=List[CheckInResponse])
def get_my_checkins(
    course_id: Optional[str] = None,
    limit: int = Query(50, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current student's check-in history."""
    query = db.query(CheckIn).filter(CheckIn.student_id == current_user.id)

    if course_id:
        query = query.join(SessionModel).filter(SessionModel.course_id == course_id)

    checkins = query.order_by(CheckIn.checked_in_at.desc()).limit(limit).all()
    return [build_checkin_response(c, db) for c in checkins]


@router.get("/session/{session_id}", response_model=List[CheckInResponse])
def get_session_checkins(
    session_id: str,
    current_user: User = Depends(get_instructor_ta_or_admin),
    db: Session = Depends(get_db)
):
    """Get all check-ins for a session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    checkins = db.query(CheckIn).filter(CheckIn.session_id == session_id).all()
    return [build_checkin_response(c, db) for c in checkins]


@router.get("/flagged", response_model=CheckInListResponse)
def get_flagged_checkins(
    course_id: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    current_user: User = Depends(get_instructor_ta_or_admin),
    db: Session = Depends(get_db)
):
    """Get check-ins requiring review."""
    query = db.query(CheckIn).filter(CheckIn.status.in_(["flagged", "appealed"]))

    if session_id:
        query = query.filter(CheckIn.session_id == session_id)
    if course_id:
        query = query.join(SessionModel).filter(SessionModel.course_id == course_id)

    total = query.count()
    checkins = query.order_by(CheckIn.checked_in_at.desc()).offset(offset).limit(limit).all()

    return CheckInListResponse(
        items=[build_checkin_response(c, db) for c in checkins],
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/{checkin_id}", response_model=CheckInResponse)
def get_checkin(
    checkin_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get check-in details."""
    checkin = db.query(CheckIn).filter(CheckIn.id == checkin_id).first()
    if not checkin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Check-in not found"
        )

    # Students can only view their own check-ins
    if current_user.role == "student" and checkin.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view other students' check-ins"
        )

    return build_checkin_response(checkin, db)
