"""Application configuration with Pydantic validation."""

import os
from typing import List, Literal, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with validation.

    All settings are validated using Pydantic to ensure correctness
    at startup time, preventing runtime errors from misconfiguration.

    Following best practices:
    - Type hints for all fields
    - Validation for acceptable ranges
    - Sensible defaults
    - Environment variable support
    """

    # Application
    APP_NAME: str = Field(default="FIVUCSAS Biometric Processor")
    VERSION: str = Field(default="1.0.0")
    ENVIRONMENT: Literal["development", "staging", "production"] = Field(
        default="development"
    )
    DEBUG: bool = Field(default=False)

    # API Settings
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8001, ge=1024, le=65535)
    API_WORKERS: int = Field(default=4, ge=1, le=32)

    # CORS Settings (NO WILDCARD!)
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"]
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # File Upload Settings
    UPLOAD_FOLDER: str = Field(default="./temp_uploads")
    MAX_FILE_SIZE: int = Field(
        default=10 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024
    )  # 1KB to 50MB
    ALLOWED_IMAGE_FORMATS: List[str] = Field(default=["jpg", "jpeg", "png"])

    # ML Model Settings
    FACE_DETECTION_BACKEND: Literal[
        "opencv", "ssd", "mtcnn", "retinaface", "mediapipe", "yolov8"
    ] = Field(default="opencv")

    FACE_RECOGNITION_MODEL: Literal[
        "VGG-Face",
        "Facenet",
        "Facenet512",
        "OpenFace",
        "DeepFace",
        "DeepID",
        "ArcFace",
        "Dlib",
        "SFace",
    ] = Field(default="Facenet")

    MODEL_DEVICE: Literal["cpu", "cuda"] = Field(default="cpu")

    # Thresholds
    VERIFICATION_THRESHOLD: float = Field(default=0.6, ge=0.0, le=1.0)
    LIVENESS_THRESHOLD: float = Field(default=80.0, ge=0.0, le=100.0)
    QUALITY_THRESHOLD: float = Field(default=70.0, ge=0.0, le=100.0)

    # Quality Assessment
    MIN_IMAGE_SIZE: int = Field(default=100, ge=50, le=1000)
    MAX_IMAGE_SIZE: int = Field(default=4000, ge=1000, le=10000)
    MIN_FACE_SIZE: int = Field(default=80, ge=40, le=500)
    BLUR_THRESHOLD: float = Field(default=100.0, ge=0.0)

    # Database (for future use in Sprint 4)
    DATABASE_URL: Optional[str] = Field(default=None)
    DATABASE_POOL_SIZE: int = Field(default=10, ge=1, le=100)

    # Redis (for future use in Sprint 4)
    REDIS_URL: Optional[str] = Field(default=None)
    REDIS_MAX_CONNECTIONS: int = Field(default=10, ge=1, le=100)

    # Webhook
    WEBHOOK_TIMEOUT: int = Field(default=10, ge=1, le=60)
    WEBHOOK_MAX_RETRIES: int = Field(default=3, ge=0, le=10)

    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    LOG_FORMAT: Literal["json", "text"] = Field(default="json")

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True)
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, ge=1)

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v):
        """Additional validation for production environment."""
        # Can add production-specific checks here
        return v

    def is_production(self) -> bool:
        """Check if running in production."""
        return self.ENVIRONMENT == "production"

    def is_development(self) -> bool:
        """Check if running in development."""
        return self.ENVIRONMENT == "development"

    def get_cors_config(self) -> dict:
        """Get CORS configuration."""
        return {
            "allow_origins": self.CORS_ORIGINS,
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE"],
            "allow_headers": ["*"],
        }


# Singleton settings instance
settings = Settings()

# Create upload folder on import
os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
