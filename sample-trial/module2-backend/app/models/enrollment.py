"""Enrollment model."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


class Enrollment(Base):
    """Enrollment table for student-course relationships."""

    __tablename__ = "enrollments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    course_id = Column(String(36), ForeignKey("courses.id"), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    enrolled_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    dropped_at = Column(DateTime, nullable=True)

    # Unique constraint for student-course pair
    __table_args__ = (
        UniqueConstraint('student_id', 'course_id', name='uq_student_course'),
    )

    # Relationships
    student = relationship("User", back_populates="enrollments", foreign_keys=[student_id])
    course = relationship("Course", back_populates="enrollments")
