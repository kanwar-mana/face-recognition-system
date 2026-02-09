"""RiskSignal model."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class RiskSignal(Base):
    """RiskSignal table for individual risk indicators."""

    __tablename__ = "risk_signals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    checkin_id = Column(String(36), ForeignKey("checkins.id"), nullable=False, index=True)

    # Signal classification
    signal_type = Column(String(50), nullable=False, index=True)
    # Types: geo_out_of_bounds, impossible_travel, geo_accuracy_low,
    #        vpn_detected, proxy_detected, tor_detected, suspicious_ip,
    #        device_unknown, device_emulator, device_rooted, attestation_failed,
    #        rapid_succession, unusual_time, pattern_anomaly,
    #        liveness_failed, liveness_low_confidence, deepfake_suspected, replay_suspected,
    #        face_match_failed, face_match_low_confidence

    severity = Column(String(20), nullable=False, index=True)  # low, medium, high, critical
    confidence = Column(Float, nullable=False, default=1.0)
    details = Column(Text, nullable=True)  # JSON metadata
    weight = Column(Float, nullable=False, default=0.1)
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationships
    checkin = relationship("CheckIn", back_populates="risk_signals")
