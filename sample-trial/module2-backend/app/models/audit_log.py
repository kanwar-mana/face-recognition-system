"""AuditLog model."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class AuditLog(Base):
    """AuditLog table for immutable audit trail."""

    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)

    # Action classification
    action = Column(String(50), nullable=False, index=True)
    # Actions: login_success, login_failed, logout, user_created, user_updated,
    #          checkin_attempted, checkin_approved, checkin_rejected,
    #          data_exported, security_violation, etc.

    resource_type = Column(String(50), nullable=True)  # user, checkin, session, course, etc.
    resource_id = Column(String(36), nullable=True)

    # Request context
    ip_address = Column(String(45), nullable=True, index=True)  # IPv4 or IPv6
    user_agent = Column(String(500), nullable=True)
    device_id = Column(String(36), nullable=True)

    # Details
    details = Column(Text, nullable=True)  # JSON details
    success = Column(Boolean, default=True)

    # Timestamp (immutable - no updated_at!)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")
