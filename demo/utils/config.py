"""Application configuration with Pydantic Settings.

This module provides typed, validated configuration management using Pydantic.
Settings can be loaded from environment variables or .env files.

Features:
    - Type-safe configuration with validation
    - Environment variable support
    - Default values for development
    - Centralized configuration access

Example:
    >>> from utils.config import get_settings
    >>> settings = get_settings()
    >>> print(settings.api_base_url)
    http://localhost:8001
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support.

    All settings can be overridden via environment variables with the
    DEMO_ prefix (e.g., DEMO_API_BASE_URL).

    Attributes:
        app_name: Display name of the application.
        app_version: Application version string.
        debug: Enable debug mode with verbose logging.
        api_base_url: Base URL for the Biometric Processor API.
        api_timeout: Timeout for API requests in seconds.
        api_key: Optional API key for authentication.
        max_image_size_mb: Maximum allowed image upload size.
        image_quality: JPEG compression quality (1-100).
        max_image_dimension: Maximum image dimension in pixels.
        cache_ttl_seconds: Default cache TTL for API responses.
        websocket_reconnect_attempts: Max WebSocket reconnection attempts.
        theme: UI theme (light/dark/auto).
    """

    model_config = SettingsConfigDict(
        env_prefix="DEMO_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application Settings
    app_name: str = Field(
        default="Biometric Processor Demo",
        description="Display name of the application",
    )
    app_version: str = Field(
        default="1.0.0",
        description="Application version string",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode with verbose logging",
    )

    # API Settings
    api_base_url: str = Field(
        default="http://localhost:8001",
        description="Base URL for the Biometric Processor API",
    )
    api_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Timeout for API requests in seconds",
    )
    api_key: str | None = Field(
        default=None,
        description="Optional API key for authentication",
    )

    # Image Processing Settings
    max_image_size_mb: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum allowed image upload size in MB",
    )
    image_quality: int = Field(
        default=85,
        ge=20,
        le=100,
        description="JPEG compression quality (1-100)",
    )
    max_image_dimension: int = Field(
        default=1920,
        ge=640,
        le=4096,
        description="Maximum image dimension in pixels",
    )
    target_image_size_kb: int = Field(
        default=500,
        ge=100,
        le=2000,
        description="Target image size after compression in KB",
    )

    # Cache Settings
    cache_ttl_seconds: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Default cache TTL for API responses",
    )
    cache_config_ttl: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Cache TTL for configuration data",
    )

    # WebSocket Settings
    websocket_reconnect_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Max WebSocket reconnection attempts",
    )
    websocket_reconnect_delay: float = Field(
        default=1.0,
        ge=0.5,
        le=10.0,
        description="Delay between reconnection attempts in seconds",
    )

    # UI Settings
    theme: Literal["light", "dark", "auto"] = Field(
        default="auto",
        description="UI theme (light/dark/auto)",
    )
    sidebar_default_expanded: bool = Field(
        default=True,
        description="Whether sidebar is expanded by default",
    )

    # Feature Flags
    enable_webcam: bool = Field(
        default=True,
        description="Enable webcam capture feature",
    )
    enable_proctoring: bool = Field(
        default=True,
        description="Enable proctoring features",
    )
    enable_admin: bool = Field(
        default=True,
        description="Enable admin dashboard",
    )

    @field_validator("api_base_url")
    @classmethod
    def validate_api_url(cls, v: str) -> str:
        """Validate and normalize API base URL."""
        # Remove trailing slash
        v = v.rstrip("/")

        # Ensure it starts with http:// or https://
        if not v.startswith(("http://", "https://")):
            v = f"http://{v}"

        return v

    @property
    def max_image_size_bytes(self) -> int:
        """Get maximum image size in bytes."""
        return self.max_image_size_mb * 1024 * 1024

    @property
    def target_image_size_bytes(self) -> int:
        """Get target image size in bytes."""
        return self.target_image_size_kb * 1024

    @property
    def api_version(self) -> str:
        """Get API version path."""
        return "/api/v1"

    def get_api_endpoint(self, path: str) -> str:
        """Construct full API endpoint URL.

        Args:
            path: Endpoint path (e.g., "/health").

        Returns:
            Full URL including base URL and API version.
        """
        # Ensure path starts with /
        if not path.startswith("/"):
            path = f"/{path}"

        return f"{self.api_base_url}{self.api_version}{path}"


class Thresholds:
    """Configuration thresholds as named constants.

    This class eliminates magic numbers by providing named constants
    for all threshold values used throughout the application.
    """

    # Verification Thresholds
    VERIFICATION_SIMILARITY: float = 0.6
    HIGH_CONFIDENCE_THRESHOLD: float = 0.8
    LOW_CONFIDENCE_THRESHOLD: float = 0.5

    # Quality Thresholds
    QUALITY_SCORE_MIN: float = 70.0
    BLUR_VARIANCE_MIN: float = 100.0
    BRIGHTNESS_MIN: float = 40.0
    BRIGHTNESS_MAX: float = 220.0

    # Liveness Thresholds
    LIVENESS_SCORE_MIN: float = 70.0
    EAR_THRESHOLD: float = 0.25  # Eye Aspect Ratio
    MAR_THRESHOLD: float = 0.6  # Mouth Aspect Ratio

    # Image Thresholds
    MIN_FACE_SIZE_PX: int = 80
    MIN_IMAGE_SIZE_PX: int = 100
    MAX_IMAGE_SIZE_MB: int = 10

    # Proctoring Thresholds
    GAZE_AWAY_SECONDS: float = 5.0
    HEAD_PITCH_DEGREES: float = 20.0
    HEAD_YAW_DEGREES: float = 30.0
    RISK_SCORE_HIGH: float = 0.7
    RISK_SCORE_MEDIUM: float = 0.4

    # API Thresholds
    API_TIMEOUT_SECONDS: int = 30
    WEBSOCKET_TIMEOUT_SECONDS: int = 60
    RATE_LIMIT_REQUESTS: int = 100


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached application settings instance.

    Uses LRU cache to ensure only one Settings instance exists,
    avoiding repeated environment variable parsing.

    Returns:
        Singleton Settings instance.

    Example:
        >>> settings = get_settings()
        >>> print(settings.api_base_url)
        http://localhost:8001
    """
    return Settings()


def get_thresholds() -> type[Thresholds]:
    """Get thresholds class for accessing named constants.

    Returns:
        Thresholds class with all named constants.

    Example:
        >>> thresholds = get_thresholds()
        >>> print(thresholds.VERIFICATION_SIMILARITY)
        0.6
    """
    return Thresholds
