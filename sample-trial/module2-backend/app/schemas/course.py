"""Course schemas."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class CourseCreate(BaseModel):
    """Schema for creating a new course."""
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1)
    semester: str = Field(..., min_length=1)
    description: Optional[str] = None
    instructor_id: Optional[str] = None
    venue_latitude: Optional[float] = None
    venue_longitude: Optional[float] = None
    venue_name: Optional[str] = None
    geofence_radius_meters: float = 100.0
    require_face_recognition: bool = False
    require_device_binding: bool = True
    risk_threshold: float = 0.5


class CourseUpdate(BaseModel):
    """Schema for updating a course."""
    name: Optional[str] = None
    description: Optional[str] = None
    venue_latitude: Optional[float] = None
    venue_longitude: Optional[float] = None
    venue_name: Optional[str] = None
    geofence_radius_meters: Optional[float] = None
    require_face_recognition: Optional[bool] = None
    require_device_binding: Optional[bool] = None
    risk_threshold: Optional[float] = None
    is_active: Optional[bool] = None


class CourseResponse(BaseModel):
    """Schema for course response."""
    id: str
    code: str
    name: str
    semester: str
    description: Optional[str] = None
    instructor_id: Optional[str] = None
    instructor_name: Optional[str] = None
    venue_latitude: Optional[float] = None
    venue_longitude: Optional[float] = None
    venue_name: Optional[str] = None
    geofence_radius_meters: float = 100.0
    require_face_recognition: bool = False
    require_device_binding: bool = True
    risk_threshold: float = 0.5
    is_active: bool = True
    created_at: datetime

    class Config:
        from_attributes = True


class CourseListResponse(BaseModel):
    """Schema for course list response."""
    items: List[CourseResponse]
    total: int
    limit: int
    offset: int
