"""User model."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    """User table for students, instructors, TAs, and admins."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="student", index=True)  # student, instructor, ta, admin
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Consent tracking
    camera_consent = Column(Boolean, default=False)
    geolocation_consent = Column(Boolean, default=False)

    # Face enrollment
    face_embedding_hash = Column(String(64), nullable=True)  # SHA-256 hash only
    face_enrolled = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)

    # Privacy
    scheduled_deletion_at = Column(DateTime, nullable=True)

    # Relationships
    enrollments = relationship("Enrollment", back_populates="student", foreign_keys="Enrollment.student_id")
    devices = relationship("Device", back_populates="user")
    checkins = relationship("CheckIn", back_populates="student", foreign_keys="CheckIn.student_id")
    taught_courses = relationship("Course", back_populates="instructor")
    taught_sessions = relationship("Session", back_populates="instructor")
    audit_logs = relationship("AuditLog", back_populates="user")
