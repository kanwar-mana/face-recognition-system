"""Device model."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Device(Base):
    """Device table for registered user devices."""

    __tablename__ = "devices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Device identification
    device_fingerprint = Column(String(64), unique=True, nullable=False, index=True)
    device_name = Column(String(255), nullable=True)
    platform = Column(String(50), nullable=True)  # ios, android, web, desktop
    browser = Column(String(100), nullable=True)
    os_version = Column(String(50), nullable=True)
    app_version = Column(String(50), nullable=True)

    # Public key for device attestation
    public_key = Column(Text, nullable=True)
    public_key_created_at = Column(DateTime, nullable=True)
    public_key_expires_at = Column(DateTime, nullable=True)

    # Attestation
    attestation_passed = Column(Boolean, default=False)
    last_attestation_at = Column(DateTime, nullable=True)
    attestation_token = Column(Text, nullable=True)

    # Trust
    is_trusted = Column(Boolean, default=False, index=True)
    trust_score = Column(String(20), default="low")  # low, medium, high
    is_emulator = Column(Boolean, default=False)
    is_rooted_jailbroken = Column(Boolean, default=False)

    # Tracking
    first_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    total_checkins = Column(Integer, default=0)

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    revoked_at = Column(DateTime, nullable=True)
    revocation_reason = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", back_populates="devices")
    checkins = relationship("CheckIn", back_populates="device")
