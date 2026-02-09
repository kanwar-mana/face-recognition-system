"""CheckIn model."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Float, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


class CheckIn(Base):
    """CheckIn table for student check-in records."""

    __tablename__ = "checkins"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=True)

    # Status
    status = Column(String(20), nullable=False, default="pending", index=True)  # pending, approved, flagged, rejected, appealed
    checked_in_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    verified_at = Column(DateTime, nullable=True)

    # Location
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_accuracy_meters = Column(Float, nullable=True)
    distance_from_venue_meters = Column(Float, nullable=True)

    # Liveness
    liveness_passed = Column(Boolean, nullable=True)
    liveness_score = Column(Float, nullable=True)
    liveness_challenge_type = Column(String(50), nullable=True)

    # Face match
    face_match_passed = Column(Boolean, nullable=True)
    face_match_score = Column(Float, nullable=True)
    face_embedding_hash = Column(String(64), nullable=True)

    # Risk assessment
    risk_score = Column(Float, nullable=False, default=0.0, index=True)
    risk_factors = Column(Text, nullable=True)  # JSON array

    # QR code
    qr_code_verified = Column(Boolean, default=False)

    # Review
    reviewed_by_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)

    # Appeal
    appeal_reason = Column(Text, nullable=True)
    appealed_at = Column(DateTime, nullable=True)

    # Privacy
    scheduled_deletion_at = Column(DateTime, nullable=True)

    # Unique constraint: one check-in per student per session
    __table_args__ = (
        UniqueConstraint('session_id', 'student_id', name='uq_session_student'),
    )

    # Relationships
    session = relationship("Session", back_populates="checkins")
    student = relationship("User", back_populates="checkins", foreign_keys=[student_id])
    device = relationship("Device", back_populates="checkins")
    risk_signals = relationship("RiskSignal", back_populates="checkin")
