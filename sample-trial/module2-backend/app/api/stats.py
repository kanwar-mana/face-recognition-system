"""Statistics and analytics endpoints."""
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_instructor_or_admin
from app.models.user import User
from app.models.course import Course
from app.models.session import Session as SessionModel
from app.models.enrollment import Enrollment
from app.models.checkin import CheckIn

router = APIRouter(prefix="/stats", tags=["statistics"])


@router.get("/overview")
def get_overview_stats(
    course_id: Optional[str] = None,
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_instructor_or_admin),
    db: Session = Depends(get_db)
):
    """Get system-wide statistics."""
    now = datetime.now(timezone.utc)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_week = start_of_today - timedelta(days=days)

    # Base query for sessions
    session_query = db.query(SessionModel)
    checkin_query = db.query(CheckIn)

    if course_id:
        session_query = session_query.filter(SessionModel.course_id == course_id)
        session_ids = [s.id for s in session_query.all()]
        checkin_query = checkin_query.filter(CheckIn.session_id.in_(session_ids))

    # Session counts
    total_sessions = session_query.count()
    active_sessions = session_query.filter(SessionModel.status == "active").count()

    # Check-in counts
    total_checkins_today = checkin_query.filter(
        CheckIn.checked_in_at >= start_of_today
    ).count()

    total_checkins_week = checkin_query.filter(
        CheckIn.checked_in_at >= start_of_week
    ).count()

    # Approval rate
    approved_count = checkin_query.filter(CheckIn.status == "approved").count()
    total_checkins = checkin_query.count()
    approval_rate = approved_count / total_checkins if total_checkins > 0 else 0.0

    # Flagged pending review
    flagged_count = checkin_query.filter(
        CheckIn.status.in_(["flagged", "appealed"])
    ).count()

    # Average risk score
    avg_risk = db.query(func.avg(CheckIn.risk_score)).scalar() or 0.0

    # High risk check-ins today
    high_risk_today = checkin_query.filter(
        CheckIn.checked_in_at >= start_of_today,
        CheckIn.risk_score >= 0.5
    ).count()

    # Trends (simplified)
    checkins_by_day = []
    for i in range(days):
        day_start = start_of_today - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        count = checkin_query.filter(
            CheckIn.checked_in_at >= day_start,
            CheckIn.checked_in_at < day_end
        ).count()
        checkins_by_day.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "count": count
        })

    # Count totals
    total_courses = db.query(Course).count()
    total_students = db.query(User).filter(User.role == "student").count()

    return {
        "total_sessions": total_sessions,
        "active_sessions": active_sessions,
        "total_courses": total_courses,
        "total_students": total_students,
        "today_checkins": total_checkins_today,
        "total_checkins_today": total_checkins_today,
        "total_checkins_week": total_checkins_week,
        "average_attendance_rate": 0.87,  # Placeholder
        "flagged_pending": flagged_count,
        "flagged_pending_review": flagged_count,
        "approval_rate": round(approval_rate, 2),
        "average_risk_score": round(float(avg_risk), 2),
        "high_risk_checkins_today": high_risk_today,
        "trends": {
            "checkins_by_day": checkins_by_day[::-1],  # Oldest first
        }
    }


@router.get("/sessions/{session_id}")
def get_session_stats(
    session_id: str,
    current_user: User = Depends(get_instructor_or_admin),
    db: Session = Depends(get_db)
):
    """Get statistics for a specific session."""
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    course = session.course

    # Get enrollment count
    total_enrolled = db.query(Enrollment).filter(
        Enrollment.course_id == session.course_id,
        Enrollment.is_active == True
    ).count()

    # Get check-in stats
    checkins = db.query(CheckIn).filter(CheckIn.session_id == session_id).all()
    checked_in = len(checkins)
    attendance_rate = checked_in / total_enrolled if total_enrolled > 0 else 0.0

    # Status breakdown
    by_status = {"approved": 0, "flagged": 0, "rejected": 0, "pending": 0}
    total_risk = 0.0
    total_distance = 0.0
    distance_count = 0

    for checkin in checkins:
        by_status[checkin.status] = by_status.get(checkin.status, 0) + 1
        total_risk += checkin.risk_score
        if checkin.distance_from_venue_meters:
            total_distance += checkin.distance_from_venue_meters
            distance_count += 1

    avg_risk = total_risk / checked_in if checked_in > 0 else 0.0
    avg_distance = total_distance / distance_count if distance_count > 0 else 0.0

    # Risk distribution
    low_risk = sum(1 for c in checkins if c.risk_score < 0.3)
    medium_risk = sum(1 for c in checkins if 0.3 <= c.risk_score < 0.5)
    high_risk = sum(1 for c in checkins if c.risk_score >= 0.5)

    return {
        "session_id": session_id,
        "session_name": session.name,
        "course_code": course.code if course else None,
        "scheduled_start": session.scheduled_start,
        "status": session.status,
        "total_enrolled": total_enrolled,
        "checked_in": checked_in,
        "attendance_rate": round(attendance_rate, 2),
        "by_status": by_status,
        "average_risk_score": round(avg_risk, 2),
        "average_distance_meters": round(avg_distance, 1),
        "risk_distribution": {
            "low": low_risk,
            "medium": medium_risk,
            "high": high_risk
        }
    }


@router.get("/courses/{course_id}")
def get_course_stats(
    course_id: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_instructor_or_admin),
    db: Session = Depends(get_db)
):
    """Get attendance statistics for a course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Get sessions
    session_query = db.query(SessionModel).filter(SessionModel.course_id == course_id)
    if start_date:
        session_query = session_query.filter(SessionModel.scheduled_start >= start_date)
    if end_date:
        session_query = session_query.filter(SessionModel.scheduled_start <= end_date)

    sessions = session_query.all()
    total_sessions = len(sessions)

    # Get enrollment count
    total_enrolled = db.query(Enrollment).filter(
        Enrollment.course_id == course_id,
        Enrollment.is_active == True
    ).count()

    # Calculate overall attendance
    session_data = []
    total_checkins = 0

    for session in sessions:
        checkin_count = db.query(CheckIn).filter(CheckIn.session_id == session.id).count()
        total_checkins += checkin_count
        rate = checkin_count / total_enrolled if total_enrolled > 0 else 0.0

        session_data.append({
            "session_id": session.id,
            "name": session.name,
            "date": session.scheduled_start.strftime("%Y-%m-%d"),
            "attendance_rate": round(rate, 2),
            "checked_in": checkin_count
        })

    overall_rate = total_checkins / (total_sessions * total_enrolled) if total_sessions * total_enrolled > 0 else 0.0

    # Count flagged check-ins
    session_ids = [s.id for s in sessions]
    flagged_count = 0
    if session_ids:
        flagged_count = db.query(CheckIn).filter(
            CheckIn.session_id.in_(session_ids),
            CheckIn.status.in_(["flagged", "appealed"])
        ).count()

    return {
        "course_id": course_id,
        "course_code": course.code,
        "course_name": course.name,
        "total_sessions": total_sessions,
        "total_enrolled": total_enrolled,
        "average_attendance_rate": round(overall_rate, 2),
        "overall_attendance_rate": round(overall_rate, 2),
        "flagged_checkins": flagged_count,
        "sessions": session_data
    }


@router.get("/students/{student_id}")
def get_student_stats(
    student_id: str,
    current_user: User = Depends(get_instructor_or_admin),
    db: Session = Depends(get_db)
):
    """Get attendance statistics for a student."""
    student = db.query(User).filter(User.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Get enrollments
    enrollments = db.query(Enrollment).filter(
        Enrollment.student_id == student_id,
        Enrollment.is_active == True
    ).all()

    courses = []
    for enrollment in enrollments:
        course = enrollment.course

        # Count sessions and check-ins
        sessions = db.query(SessionModel).filter(SessionModel.course_id == course.id).all()
        total_sessions = len(sessions)

        checkins = db.query(CheckIn).join(SessionModel).filter(
            CheckIn.student_id == student_id,
            SessionModel.course_id == course.id
        ).all()

        sessions_attended = len(checkins)
        attendance_rate = sessions_attended / total_sessions if total_sessions > 0 else 0.0
        avg_risk = sum(c.risk_score for c in checkins) / len(checkins) if checkins else 0.0

        courses.append({
            "course_id": course.id,
            "course_code": course.code,
            "attendance_rate": round(attendance_rate, 2),
            "sessions_attended": sessions_attended,
            "total_sessions": total_sessions,
            "average_risk_score": round(avg_risk, 2)
        })

    # Recent check-ins
    recent_checkins = db.query(CheckIn).filter(
        CheckIn.student_id == student_id
    ).order_by(CheckIn.checked_in_at.desc()).limit(10).all()

    recent = []
    for checkin in recent_checkins:
        session = checkin.session
        recent.append({
            "session_name": session.name if session else None,
            "course_code": session.course.code if session and session.course else None,
            "checked_in_at": checkin.checked_in_at,
            "status": checkin.status
        })

    # Calculate aggregates
    total_enrolled_courses = len(courses)
    total_sessions_all = sum(c["total_sessions"] for c in courses)
    attended_sessions_all = sum(c["sessions_attended"] for c in courses)
    overall_rate = attended_sessions_all / total_sessions_all if total_sessions_all > 0 else 0.0

    return {
        "student_id": student_id,
        "student_name": student.full_name,
        "student_email": student.email,
        "total_enrolled_courses": total_enrolled_courses,
        "total_sessions": total_sessions_all,
        "attended_sessions": attended_sessions_all,
        "attendance_rate": round(overall_rate, 2),
        "courses": courses,
        "recent_sessions": recent,
        "recent_checkins": recent
    }
