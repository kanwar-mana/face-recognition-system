"""Application configuration from environment variables."""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = "postgresql://saiv:saiv_password@localhost:5434/saiv"

    # Redis
    REDIS_URL: str = "redis://localhost:6380"

    # JWT Configuration
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 1 hour
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Face Service
    FACE_SERVICE_URL: str = "http://localhost:8001"

    # CORS
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8501"]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
