"""Device schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DeviceCreate(BaseModel):
    """Schema for registering a device."""
    device_fingerprint: str
    device_name: Optional[str] = None
    platform: Optional[str] = None
    browser: Optional[str] = None
    public_key: Optional[str] = None


class DeviceUpdate(BaseModel):
    """Schema for updating a device."""
    device_name: Optional[str] = None
    is_trusted: Optional[bool] = None
    is_active: Optional[bool] = None


class DeviceResponse(BaseModel):
    """Schema for device response."""
    id: str
    device_fingerprint: str
    device_name: Optional[str] = None
    platform: Optional[str] = None
    is_trusted: bool = False
    trust_score: str = "low"
    is_active: bool = True
    first_seen_at: datetime
    last_seen_at: datetime
    total_checkins: int = 0

    class Config:
        from_attributes = True
