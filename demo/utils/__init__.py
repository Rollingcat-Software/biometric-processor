"""Utility modules for Biometric Processor Demo Application.

This package contains shared utilities including:
    - protocols: Interface definitions (DIP compliance)
    - exceptions: Custom exception hierarchy
    - config: Application configuration
    - api_client: HTTP client for API communication
    - container: Dependency injection container
    - cache: Response caching with TTL
    - image_utils: Image processing utilities
"""

from utils.protocols import (
    IAPIClient,
    ICacheManager,
    IImageProcessor,
    ISessionManager,
    IWebSocketHandler,
)
from utils.exceptions import (
    DemoAppError,
    APIConnectionError,
    APIResponseError,
    ImageValidationError,
    WebSocketError,
    RateLimitExceededError,
)
from utils.config import Settings, get_settings
from utils.container import DependencyContainer

__all__ = [
    # Protocols
    "IAPIClient",
    "ICacheManager",
    "IImageProcessor",
    "ISessionManager",
    "IWebSocketHandler",
    # Exceptions
    "DemoAppError",
    "APIConnectionError",
    "APIResponseError",
    "ImageValidationError",
    "WebSocketError",
    "RateLimitExceededError",
    # Config
    "Settings",
    "get_settings",
    # Container
    "DependencyContainer",
]
