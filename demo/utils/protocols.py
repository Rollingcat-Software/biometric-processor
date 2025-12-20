"""Protocol definitions for Dependency Inversion Principle compliance.

This module defines abstract interfaces (protocols) that allow high-level modules
to depend on abstractions rather than concrete implementations. This enables:
    - Easy testing with mock implementations
    - Swappable implementations (production vs testing)
    - Loose coupling between components

Protocols Defined:
    - IAPIClient: HTTP API communication
    - IImageProcessor: Image processing operations
    - IWebSocketHandler: WebSocket connection management
    - ISessionManager: Streamlit session state management
    - ICacheManager: Response caching with TTL
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Awaitable


@runtime_checkable
class IAPIClient(Protocol):
    """Protocol for API client implementations.

    Defines the contract for HTTP communication with the Biometric Processor API.
    Both production (HTTPAPIClient) and mock implementations must satisfy this interface.

    Example:
        >>> class HTTPAPIClient(IAPIClient):
        ...     async def get(self, endpoint: str) -> dict[str, Any]:
        ...         # Implementation
        ...         pass
    """

    @property
    def base_url(self) -> str:
        """Return the base URL of the API."""
        ...

    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Perform an async GET request.

        Args:
            endpoint: API endpoint path (e.g., "/health").
            params: Optional query parameters.
            headers: Optional additional headers.

        Returns:
            Parsed JSON response as dictionary.

        Raises:
            APIConnectionError: If the API is unreachable.
            APIResponseError: If the API returns an error status.
        """
        ...

    async def post(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        files: dict[str, bytes] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Perform an async POST request.

        Args:
            endpoint: API endpoint path (e.g., "/enroll").
            data: Form data or JSON body.
            files: Files to upload as multipart form data.
            headers: Optional additional headers.

        Returns:
            Parsed JSON response as dictionary.

        Raises:
            APIConnectionError: If the API is unreachable.
            APIResponseError: If the API returns an error status.
        """
        ...

    async def delete(
        self,
        endpoint: str,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Perform an async DELETE request.

        Args:
            endpoint: API endpoint path.
            headers: Optional additional headers.

        Returns:
            Parsed JSON response as dictionary.

        Raises:
            APIConnectionError: If the API is unreachable.
            APIResponseError: If the API returns an error status.
        """
        ...

    async def patch(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Perform an async PATCH request.

        Args:
            endpoint: API endpoint path.
            data: JSON body data.
            headers: Optional additional headers.

        Returns:
            Parsed JSON response as dictionary.

        Raises:
            APIConnectionError: If the API is unreachable.
            APIResponseError: If the API returns an error status.
        """
        ...

    def health_check(self) -> bool:
        """Check if the API is reachable and healthy.

        Returns:
            True if API is healthy, False otherwise.
        """
        ...


@runtime_checkable
class IImageProcessor(Protocol):
    """Protocol for image processing operations.

    Defines the contract for image manipulation, validation, and optimization.
    Separates image processing concerns from API communication.

    Example:
        >>> class PILImageProcessor(IImageProcessor):
        ...     def validate(self, image: bytes) -> bool:
        ...         # Check if valid JPEG/PNG
        ...         pass
    """

    def validate(self, image: bytes) -> bool:
        """Validate image format and integrity.

        Args:
            image: Raw image bytes.

        Returns:
            True if image is valid JPEG or PNG.
        """
        ...

    def resize(
        self,
        image: bytes,
        max_size: tuple[int, int],
    ) -> bytes:
        """Resize image to fit within max dimensions.

        Args:
            image: Raw image bytes.
            max_size: Maximum (width, height) tuple.

        Returns:
            Resized image bytes.
        """
        ...

    def compress(
        self,
        image: bytes,
        quality: int = 85,
    ) -> bytes:
        """Compress image to reduce file size.

        Args:
            image: Raw image bytes.
            quality: JPEG quality (1-100).

        Returns:
            Compressed image bytes.
        """
        ...

    def optimize_for_upload(self, image: bytes) -> bytes:
        """Optimize image for API upload.

        Combines resize and compress operations for optimal upload size.

        Args:
            image: Raw image bytes.

        Returns:
            Optimized image bytes ready for upload.
        """
        ...

    def get_dimensions(self, image: bytes) -> tuple[int, int]:
        """Get image dimensions.

        Args:
            image: Raw image bytes.

        Returns:
            Tuple of (width, height).
        """
        ...

    def convert_to_rgb(self, image: bytes) -> bytes:
        """Convert image to RGB mode.

        Args:
            image: Raw image bytes (may be RGBA, P, etc.).

        Returns:
            RGB image bytes.
        """
        ...


@runtime_checkable
class IWebSocketHandler(Protocol):
    """Protocol for WebSocket connection handling.

    Defines the contract for real-time WebSocket communication
    used in proctoring streaming features.

    Example:
        >>> class WebSocketStreamHandler(IWebSocketHandler):
        ...     async def connect(self, url: str) -> None:
        ...         # Establish WebSocket connection
        ...         pass
    """

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is currently connected."""
        ...

    async def connect(self, url: str) -> None:
        """Establish WebSocket connection.

        Args:
            url: WebSocket URL to connect to.

        Raises:
            WebSocketError: If connection fails.
        """
        ...

    async def disconnect(self) -> None:
        """Close WebSocket connection gracefully."""
        ...

    async def send_bytes(self, data: bytes) -> None:
        """Send binary data over WebSocket.

        Args:
            data: Binary data to send.

        Raises:
            WebSocketError: If send fails.
        """
        ...

    async def send_json(self, data: dict[str, Any]) -> None:
        """Send JSON data over WebSocket.

        Args:
            data: Dictionary to serialize and send.

        Raises:
            WebSocketError: If send fails.
        """
        ...

    async def receive_bytes(self) -> bytes:
        """Receive binary data from WebSocket.

        Returns:
            Received binary data.

        Raises:
            WebSocketError: If receive fails or connection closed.
        """
        ...

    async def receive_json(self) -> dict[str, Any]:
        """Receive and parse JSON from WebSocket.

        Returns:
            Parsed JSON as dictionary.

        Raises:
            WebSocketError: If receive fails or invalid JSON.
        """
        ...


@runtime_checkable
class ISessionManager(Protocol):
    """Protocol for Streamlit session state management.

    Abstracts session state operations to enable testing
    without Streamlit runtime dependency.

    Example:
        >>> class StreamlitSessionManager(ISessionManager):
        ...     def get(self, key: str, default: Any = None) -> Any:
        ...         return st.session_state.get(key, default)
    """

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from session state.

        Args:
            key: Session state key.
            default: Default value if key not found.

        Returns:
            Stored value or default.
        """
        ...

    def set(self, key: str, value: Any) -> None:
        """Set value in session state.

        Args:
            key: Session state key.
            value: Value to store.
        """
        ...

    def delete(self, key: str) -> None:
        """Delete key from session state.

        Args:
            key: Session state key to delete.
        """
        ...

    def clear(self) -> None:
        """Clear all session state."""
        ...

    def has(self, key: str) -> bool:
        """Check if key exists in session state.

        Args:
            key: Session state key.

        Returns:
            True if key exists.
        """
        ...

    def get_all(self) -> dict[str, Any]:
        """Get all session state as dictionary.

        Returns:
            Copy of all session state data.
        """
        ...


@runtime_checkable
class ICacheManager(Protocol):
    """Protocol for response caching with TTL.

    Abstracts caching operations to enable different backends
    (memory, Redis, Streamlit cache) and testing.

    Example:
        >>> class StreamlitCacheManager(ICacheManager):
        ...     def get(self, key: str) -> Any | None:
        ...         # Check cache with TTL validation
        ...         pass
    """

    def get(self, key: str) -> Any | None:
        """Get cached value if not expired.

        Args:
            key: Cache key.

        Returns:
            Cached value or None if not found/expired.
        """
        ...

    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        """Set cached value with TTL.

        Args:
            key: Cache key.
            value: Value to cache.
            ttl_seconds: Time-to-live in seconds.
        """
        ...

    def delete(self, key: str) -> None:
        """Delete cached value.

        Args:
            key: Cache key to delete.
        """
        ...

    def clear(self) -> None:
        """Clear all cached values."""
        ...

    def has(self, key: str) -> bool:
        """Check if valid (non-expired) cache exists.

        Args:
            key: Cache key.

        Returns:
            True if valid cache exists.
        """
        ...
