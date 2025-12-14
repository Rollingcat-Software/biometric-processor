"""Dependency Injection Container for the Demo Application.

This module provides a DI container that manages application dependencies,
enabling the Dependency Inversion Principle (DIP) from SOLID.

Features:
    - Centralized dependency management
    - Production and testing configurations
    - Lazy initialization of dependencies
    - Type-safe dependency access

Example:
    >>> container = DependencyContainer.create_production()
    >>> api_client = container.api_client
    >>> result = await api_client.get("/api/v1/health")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from utils.api_client import HTTPAPIClient, MockAPIClient
from utils.config import Settings, get_settings
from utils.protocols import (
    IAPIClient,
    ICacheManager,
    IImageProcessor,
    ISessionManager,
)

if TYPE_CHECKING:
    pass


@dataclass
class DependencyContainer:
    """Dependency injection container for the application.

    Manages all application dependencies through a centralized container,
    allowing easy swapping of implementations for testing.

    Attributes:
        api_client: HTTP client for API communication.
        image_processor: Image processing utilities.
        session_manager: Streamlit session state manager.
        cache_manager: Response cache manager.
        settings: Application settings.

    Example:
        >>> # Production usage
        >>> container = DependencyContainer.create_production()
        >>> result = await container.api_client.get("/health")

        >>> # Testing usage
        >>> container = DependencyContainer.create_testing()
        >>> container.api_client.set_response("/health", {"status": "healthy"})
    """

    api_client: IAPIClient
    image_processor: IImageProcessor
    session_manager: ISessionManager
    cache_manager: ICacheManager
    settings: Settings = field(default_factory=get_settings)

    @classmethod
    def create_production(cls) -> DependencyContainer:
        """Create container with production dependencies.

        Creates a fully configured container with real implementations
        suitable for production use.

        Returns:
            DependencyContainer configured for production.

        Example:
            >>> container = DependencyContainer.create_production()
            >>> assert isinstance(container.api_client, HTTPAPIClient)
        """
        settings = get_settings()

        return cls(
            api_client=HTTPAPIClient(
                base_url=settings.api_base_url,
                timeout=settings.api_timeout,
                api_key=settings.api_key,
            ),
            image_processor=PILImageProcessor(settings),
            session_manager=StreamlitSessionManager(),
            cache_manager=StreamlitCacheManager(),
            settings=settings,
        )

    @classmethod
    def create_testing(cls) -> DependencyContainer:
        """Create container with mock dependencies for testing.

        Creates a container with mock implementations suitable for
        unit testing without external dependencies.

        Returns:
            DependencyContainer configured for testing.

        Example:
            >>> container = DependencyContainer.create_testing()
            >>> assert isinstance(container.api_client, MockAPIClient)
        """
        settings = get_settings()

        return cls(
            api_client=MockAPIClient(),
            image_processor=MockImageProcessor(),
            session_manager=InMemorySessionManager(),
            cache_manager=InMemoryCacheManager(),
            settings=settings,
        )


class PILImageProcessor(IImageProcessor):
    """Production image processor using Pillow.

    Implements IImageProcessor protocol for real image processing operations.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize image processor with settings."""
        self._settings = settings or get_settings()

    def validate(self, image: bytes) -> bool:
        """Validate image format and integrity."""
        try:
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(image))
            img.verify()
            return img.format in ("JPEG", "PNG")
        except Exception:
            return False

    def resize(self, image: bytes, max_size: tuple[int, int]) -> bytes:
        """Resize image to fit within max dimensions."""
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image))
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

        output = io.BytesIO()
        img_format = img.format or "JPEG"
        img.save(output, format=img_format)
        return output.getvalue()

    def compress(self, image: bytes, quality: int = 85) -> bytes:
        """Compress image to reduce file size."""
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image))

        # Convert to RGB if necessary
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        output = io.BytesIO()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        return output.getvalue()

    def optimize_for_upload(self, image: bytes) -> bytes:
        """Optimize image for API upload."""
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image))

        # Convert to RGB if necessary
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize if too large
        max_dim = self._settings.max_image_dimension
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        # Compress with quality adjustment
        output = io.BytesIO()
        quality = self._settings.image_quality
        target_size = self._settings.target_image_size_bytes

        while quality > 20:
            output.seek(0)
            output.truncate()
            img.save(output, format="JPEG", quality=quality, optimize=True)

            if output.tell() <= target_size:
                break
            quality -= 10

        return output.getvalue()

    def get_dimensions(self, image: bytes) -> tuple[int, int]:
        """Get image dimensions."""
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image))
        return img.size

    def convert_to_rgb(self, image: bytes) -> bytes:
        """Convert image to RGB mode."""
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image))
        if img.mode != "RGB":
            img = img.convert("RGB")

        output = io.BytesIO()
        img.save(output, format="JPEG")
        return output.getvalue()


class StreamlitSessionManager(ISessionManager):
    """Session manager using Streamlit session state."""

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from session state."""
        import streamlit as st
        return st.session_state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set value in session state."""
        import streamlit as st
        st.session_state[key] = value

    def delete(self, key: str) -> None:
        """Delete key from session state."""
        import streamlit as st
        if key in st.session_state:
            del st.session_state[key]

    def clear(self) -> None:
        """Clear all session state."""
        import streamlit as st
        for key in list(st.session_state.keys()):
            del st.session_state[key]

    def has(self, key: str) -> bool:
        """Check if key exists in session state."""
        import streamlit as st
        return key in st.session_state

    def get_all(self) -> dict[str, Any]:
        """Get all session state as dictionary."""
        import streamlit as st
        return dict(st.session_state)


class StreamlitCacheManager(ICacheManager):
    """Cache manager using Streamlit session state with TTL."""

    def __init__(self) -> None:
        """Initialize cache manager."""
        self._cache_key = "_demo_cache"
        self._timestamps_key = "_demo_cache_timestamps"

    def _get_cache(self) -> dict[str, Any]:
        """Get cache dictionary from session state."""
        import streamlit as st
        if self._cache_key not in st.session_state:
            st.session_state[self._cache_key] = {}
        return st.session_state[self._cache_key]

    def _get_timestamps(self) -> dict[str, float]:
        """Get cache timestamps from session state."""
        import streamlit as st
        if self._timestamps_key not in st.session_state:
            st.session_state[self._timestamps_key] = {}
        return st.session_state[self._timestamps_key]

    def get(self, key: str) -> Any | None:
        """Get cached value if not expired."""
        import time

        cache = self._get_cache()
        timestamps = self._get_timestamps()

        if key not in cache:
            return None

        # Check TTL
        if key in timestamps:
            if time.time() > timestamps[key]:
                self.delete(key)
                return None

        return cache[key]

    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        """Set cached value with TTL."""
        import time

        cache = self._get_cache()
        timestamps = self._get_timestamps()

        cache[key] = value
        timestamps[key] = time.time() + ttl_seconds

    def delete(self, key: str) -> None:
        """Delete cached value."""
        cache = self._get_cache()
        timestamps = self._get_timestamps()

        cache.pop(key, None)
        timestamps.pop(key, None)

    def clear(self) -> None:
        """Clear all cached values."""
        import streamlit as st
        st.session_state[self._cache_key] = {}
        st.session_state[self._timestamps_key] = {}

    def has(self, key: str) -> bool:
        """Check if valid (non-expired) cache exists."""
        return self.get(key) is not None


# Mock implementations for testing


class MockImageProcessor(IImageProcessor):
    """Mock image processor for testing."""

    def validate(self, image: bytes) -> bool:
        """Always returns True for testing."""
        return len(image) > 0

    def resize(self, image: bytes, max_size: tuple[int, int]) -> bytes:
        """Returns image unchanged for testing."""
        return image

    def compress(self, image: bytes, quality: int = 85) -> bytes:
        """Returns image unchanged for testing."""
        return image

    def optimize_for_upload(self, image: bytes) -> bytes:
        """Returns image unchanged for testing."""
        return image

    def get_dimensions(self, image: bytes) -> tuple[int, int]:
        """Returns fixed dimensions for testing."""
        return (640, 480)

    def convert_to_rgb(self, image: bytes) -> bytes:
        """Returns image unchanged for testing."""
        return image


class InMemorySessionManager(ISessionManager):
    """In-memory session manager for testing."""

    def __init__(self) -> None:
        """Initialize in-memory storage."""
        self._storage: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from memory."""
        return self._storage.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set value in memory."""
        self._storage[key] = value

    def delete(self, key: str) -> None:
        """Delete key from memory."""
        self._storage.pop(key, None)

    def clear(self) -> None:
        """Clear all storage."""
        self._storage.clear()

    def has(self, key: str) -> bool:
        """Check if key exists."""
        return key in self._storage

    def get_all(self) -> dict[str, Any]:
        """Get all storage as dictionary."""
        return self._storage.copy()


class InMemoryCacheManager(ICacheManager):
    """In-memory cache manager for testing."""

    def __init__(self) -> None:
        """Initialize in-memory cache."""
        self._cache: dict[str, Any] = {}
        self._timestamps: dict[str, float] = {}

    def get(self, key: str) -> Any | None:
        """Get cached value if not expired."""
        import time

        if key not in self._cache:
            return None

        if key in self._timestamps:
            if time.time() > self._timestamps[key]:
                self.delete(key)
                return None

        return self._cache[key]

    def set(self, key: str, value: Any, ttl_seconds: int = 60) -> None:
        """Set cached value with TTL."""
        import time

        self._cache[key] = value
        self._timestamps[key] = time.time() + ttl_seconds

    def delete(self, key: str) -> None:
        """Delete cached value."""
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()
        self._timestamps.clear()

    def has(self, key: str) -> bool:
        """Check if valid cache exists."""
        return self.get(key) is not None


# Global container instance
_container: DependencyContainer | None = None


def get_container() -> DependencyContainer:
    """Get or create the global dependency container.

    Returns:
        Global DependencyContainer instance.
    """
    global _container
    if _container is None:
        _container = DependencyContainer.create_production()
    return _container


def set_container(container: DependencyContainer) -> None:
    """Set the global dependency container (for testing).

    Args:
        container: DependencyContainer instance to use globally.
    """
    global _container
    _container = container
