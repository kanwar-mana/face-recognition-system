"""Data export endpoints."""
import csv
import io
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_instructor_or_admin
from app.models.user import User
from app.models.course import Course
from app.models.session import Session as SessionModel
from app.models.enrollment import Enrollment
from app.models.checkin import CheckIn

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/attendance/{course_id}")
def export_attendance(
    course_id: str,
    format: str = Query("csv", regex="^(csv|json)$"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_instructor_or_admin),
    db: Session = Depends(get_db)
):
    """Export attendance data for a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Get sessions
    session_query = db.query(SessionModel).filter(SessionModel.course_id == course_id)
    if start_date:
        session_query = session_query.filter(SessionModel.scheduled_start >= start_date)
    if end_date:
        session_query = session_query.filter(SessionModel.scheduled_start <= end_date)

    sessions = session_query.order_by(SessionModel.scheduled_start).all()
    session_ids = [s.id for s in sessions]

    # Get check-ins
    checkins = db.query(CheckIn).filter(CheckIn.session_id.in_(session_ids)).all()

    # Build data
    data = []
    for checkin in checkins:
        student = checkin.student
        session = checkin.session

        data.append({
            "student_id": student.id if student else None,
            "student_name": student.full_name if student else None,
            "student_email": student.email if student else None,
            "session_date": session.scheduled_start.strftime("%Y-%m-%d") if session else None,
            "session_name": session.name if session else None,
            "status": checkin.status,
            "checked_in_at": checkin.checked_in_at.isoformat() if checkin.checked_in_at else None,
            "risk_score": checkin.risk_score
        })

    if format == "json":
        return data

    # CSV format
    output = io.StringIO()
    if data:
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=attendance_{course.code}_{datetime.now().strftime('%Y%m%d')}.csv"
        }
    )


@router.get("/session/{session_id}")
def export_session(
    session_id: str,
    format: str = Query("csv", regex="^(csv|json)$"),
    current_user: User = Depends(get_instructor_or_admin),
    db: Session = Depends(get_db)
):
    """Export check-in data for a session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    checkins = db.query(CheckIn).filter(CheckIn.session_id == session_id).all()

    # Build data with required columns
    data = []
    for checkin in checkins:
        student = checkin.student

        data.append({
            "checkin_id": checkin.id,
            "student_id": checkin.student_id,
            "session_id": checkin.session_id,
            "timestamp": checkin.checked_in_at.isoformat() if checkin.checked_in_at else None,
            "verification_status": checkin.status,
            "risk_score": checkin.risk_score,
            "liveness_score": checkin.liveness_score,
            "face_match_score": checkin.face_match_score,
            "latitude": checkin.latitude,
            "longitude": checkin.longitude,
        })

    if format == "json":
        return data

    # CSV format
    output = io.StringIO()
    if data:
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=session_{session_id[:8]}_{datetime.now().strftime('%Y%m%d')}.csv"
        }
    )
