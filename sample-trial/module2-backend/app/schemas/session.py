"""Session schemas."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    """Schema for creating a new session."""
    course_id: str
    name: str = Field(..., min_length=1)
    session_type: str = "lecture"
    description: Optional[str] = None
    scheduled_start: datetime
    scheduled_end: datetime
    checkin_opens_at: Optional[datetime] = None
    checkin_closes_at: Optional[datetime] = None
    venue_latitude: Optional[float] = None
    venue_longitude: Optional[float] = None
    venue_name: Optional[str] = None
    geofence_radius_meters: Optional[float] = None
    require_liveness_check: bool = True
    require_face_match: bool = False
    risk_threshold: Optional[float] = None


class SessionUpdate(BaseModel):
    """Schema for updating a session."""
    name: Optional[str] = None
    session_type: Optional[str] = None
    description: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    checkin_opens_at: Optional[datetime] = None
    checkin_closes_at: Optional[datetime] = None
    status: Optional[str] = None
    venue_latitude: Optional[float] = None
    venue_longitude: Optional[float] = None
    venue_name: Optional[str] = None
    geofence_radius_meters: Optional[float] = None
    require_liveness_check: Optional[bool] = None
    require_face_match: Optional[bool] = None
    risk_threshold: Optional[float] = None


class SessionResponse(BaseModel):
    """Schema for session response."""
    id: str
    course_id: str
    course_code: Optional[str] = None
    course_name: Optional[str] = None
    instructor_id: Optional[str] = None
    name: str
    session_type: str = "lecture"
    description: Optional[str] = None
    status: str = "scheduled"
    scheduled_start: datetime
    scheduled_end: datetime
    checkin_opens_at: datetime
    checkin_closes_at: datetime
    venue_latitude: Optional[float] = None
    venue_longitude: Optional[float] = None
    venue_name: Optional[str] = None
    geofence_radius_meters: Optional[float] = None
    require_liveness_check: bool = True
    require_face_match: bool = False
    risk_threshold: Optional[float] = None
    total_enrolled: Optional[int] = None
    checked_in_count: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """Schema for session list response."""
    items: List[SessionResponse]
    total: int
    limit: int
    offset: int
