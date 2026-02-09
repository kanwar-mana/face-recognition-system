"""Device management endpoints."""
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_admin_user
from app.models.user import User
from app.models.device import Device
from app.schemas.device import DeviceCreate, DeviceResponse, DeviceUpdate

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
@router.post("/register", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def register_device(
    device_data: DeviceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Register a new device."""
    # Check if device already exists
    existing = db.query(Device).filter(
        Device.device_fingerprint == device_data.device_fingerprint
    ).first()

    if existing:
        # Update last seen and return existing
        existing.last_seen_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    device = Device(
        user_id=current_user.id,
        device_fingerprint=device_data.device_fingerprint,
        device_name=device_data.device_name,
        platform=device_data.platform,
        browser=device_data.browser,
        public_key=device_data.public_key,
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(device)
    db.commit()
    db.refresh(device)

    return device


@router.get("/")
def list_all_devices(
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """List all devices (admin only)."""
    devices = db.query(Device).all()
    return {
        "items": [DeviceResponse.model_validate(d) for d in devices],
        "total": len(devices)
    }


@router.get("/my-devices", response_model=List[DeviceResponse])
def list_my_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List current user's devices."""
    devices = db.query(Device).filter(
        Device.user_id == current_user.id,
        Device.is_active == True
    ).all()
    return devices


@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get device details."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )

    # Users can only view their own devices (unless admin)
    if current_user.role != "admin" and device.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view other users' devices"
        )

    return device


@router.patch("/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: str,
    update_data: DeviceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update device properties."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )

    # Check permissions
    is_owner = device.user_id == current_user.id
    is_admin = current_user.role == "admin"

    if not is_owner and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this device"
        )

    # Apply updates
    if update_data.device_name is not None:
        device.device_name = update_data.device_name
    if update_data.is_active is not None:
        device.is_active = update_data.is_active
    if update_data.is_trusted is not None and is_admin:
        device.is_trusted = update_data.is_trusted

    device.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(device)

    return device


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a device."""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found"
        )

    # Check permissions
    if current_user.role != "admin" and device.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this device"
        )

    db.delete(device)
    db.commit()
    return None
