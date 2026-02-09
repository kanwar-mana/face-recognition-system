"""CheckIn schemas."""
from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field


class CheckInCreate(BaseModel):
    """Schema for creating a check-in."""
    session_id: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_accuracy_meters: Optional[float] = None
    device_fingerprint: Optional[str] = None
    liveness_challenge_response: Optional[str] = None
    qr_code: Optional[str] = None


class RiskFactor(BaseModel):
    """Schema for a risk factor."""
    type: str
    weight: float
    severity: Optional[str] = None


class CheckInResponse(BaseModel):
    """Schema for check-in response."""
    id: str
    session_id: str
    session_name: Optional[str] = None
    student_id: str
    student_name: Optional[str] = None
    student_email: Optional[str] = None
    status: str = "pending"
    checked_in_at: datetime
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_from_venue_meters: Optional[float] = None
    liveness_passed: Optional[bool] = None
    liveness_score: Optional[float] = None
    face_match_passed: Optional[bool] = None
    face_match_score: Optional[float] = None
    risk_score: float = 0.0
    risk_factors: Optional[List[Dict[str, Any]]] = None
    device_trusted: Optional[bool] = None
    course_code: Optional[str] = None

    class Config:
        from_attributes = True


class CheckInListResponse(BaseModel):
    """Schema for check-in list response."""
    items: List[CheckInResponse]
    total: int
    limit: int
    offset: int
