"""Course model."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Course(Base):
    """Course table for course information."""

    __tablename__ = "courses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    semester = Column(String(20), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Instructor
    instructor_id = Column(String(36), ForeignKey("users.id"), nullable=True)

    # Venue settings
    venue_latitude = Column(Float, nullable=True)
    venue_longitude = Column(Float, nullable=True)
    venue_name = Column(String(255), nullable=True)

    # Security settings
    geofence_radius_meters = Column(Float, default=100.0)
    require_face_recognition = Column(Boolean, default=False)
    require_device_binding = Column(Boolean, default=True)
    risk_threshold = Column(Float, default=0.5)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    instructor = relationship("User", back_populates="taught_courses")
    enrollments = relationship("Enrollment", back_populates="course")
    sessions = relationship("Session", back_populates="course")
