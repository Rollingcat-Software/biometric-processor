"""Unit tests for DependencyContainer module.

Tests the dependency injection container and its implementations.
"""

from __future__ import annotations

import pytest

from utils.container import (
    DependencyContainer,
    InMemoryCacheManager,
    InMemorySessionManager,
    MockImageProcessor,
    PILImageProcessor,
)
from utils.api_client import MockAPIClient
from utils.protocols import IAPIClient, ICacheManager, IImageProcessor, ISessionManager


class TestDependencyContainer:
    """Tests for DependencyContainer class."""

    def test_create_testing_container(self) -> None:
        """Test creating a testing container."""
        container = DependencyContainer.create_testing()

        assert container is not None
        assert container.api_client is not None
        assert container.image_processor is not None
        assert container.session_manager is not None
        assert container.cache_manager is not None

    def test_create_custom_container(self) -> None:
        """Test creating a container with custom components."""
        api_client = MockAPIClient()
        image_processor = MockImageProcessor()
        session_manager = InMemorySessionManager()
        cache_manager = InMemoryCacheManager()

        container = DependencyContainer(
            api_client=api_client,
            image_processor=image_processor,
            session_manager=session_manager,
            cache_manager=cache_manager,
        )

        assert container.api_client is api_client
        assert container.image_processor is image_processor
        assert container.session_manager is session_manager
        assert container.cache_manager is cache_manager

    def test_container_components_implement_protocols(self) -> None:
        """Test that container components implement their protocols."""
        container = DependencyContainer.create_testing()

        # Check protocol compliance using isinstance
        assert isinstance(container.api_client, IAPIClient)
        assert isinstance(container.image_processor, IImageProcessor)
        assert isinstance(container.session_manager, ISessionManager)
        assert isinstance(container.cache_manager, ICacheManager)


class TestInMemorySessionManager:
    """Tests for InMemorySessionManager class."""

    def test_initialization(self) -> None:
        """Test session manager initialization."""
        manager = InMemorySessionManager()
        assert manager is not None

    def test_set_and_get(self) -> None:
        """Test setting and getting values."""
        manager = InMemorySessionManager()

        manager.set("key1", "value1")
        manager.set("key2", {"nested": "dict"})

        assert manager.get("key1") == "value1"
        assert manager.get("key2") == {"nested": "dict"}

    def test_get_default(self) -> None:
        """Test getting with default value."""
        manager = InMemorySessionManager()

        assert manager.get("nonexistent") is None
        assert manager.get("nonexistent", "default") == "default"

    def test_delete(self) -> None:
        """Test deleting values."""
        manager = InMemorySessionManager()

        manager.set("key", "value")
        assert manager.get("key") == "value"

        manager.delete("key")
        assert manager.get("key") is None

    def test_clear(self) -> None:
        """Test clearing all values."""
        manager = InMemorySessionManager()

        manager.set("key1", "value1")
        manager.set("key2", "value2")

        manager.clear()

        assert manager.get("key1") is None
        assert manager.get("key2") is None


class TestInMemoryCacheManager:
    """Tests for InMemoryCacheManager class."""

    def test_initialization(self) -> None:
        """Test cache manager initialization."""
        manager = InMemoryCacheManager()
        assert manager is not None

    def test_set_and_get(self) -> None:
        """Test setting and getting cached values."""
        manager = InMemoryCacheManager()

        manager.set("cache_key", {"data": "cached"})
        result = manager.get("cache_key")

        assert result == {"data": "cached"}

    def test_get_missing_key(self) -> None:
        """Test getting missing key returns None."""
        manager = InMemoryCacheManager()

        assert manager.get("missing") is None

    def test_delete(self) -> None:
        """Test deleting cached values."""
        manager = InMemoryCacheManager()

        manager.set("key", "value")
        manager.delete("key")

        assert manager.get("key") is None

    def test_clear(self) -> None:
        """Test clearing cache."""
        manager = InMemoryCacheManager()

        manager.set("key1", "value1")
        manager.set("key2", "value2")

        manager.clear()

        assert manager.get("key1") is None
        assert manager.get("key2") is None


class TestMockImageProcessor:
    """Tests for MockImageProcessor class."""

    def test_initialization(self) -> None:
        """Test processor initialization."""
        processor = MockImageProcessor()
        assert processor is not None

    def test_resize(self) -> None:
        """Test image resize."""
        processor = MockImageProcessor()

        result = processor.resize(b"image_data", 100, 100)

        assert isinstance(result, bytes)

    def test_to_jpeg(self) -> None:
        """Test conversion to JPEG."""
        processor = MockImageProcessor()

        result = processor.to_jpeg(b"image_data")

        assert isinstance(result, bytes)

    def test_to_base64(self) -> None:
        """Test conversion to base64."""
        processor = MockImageProcessor()

        result = processor.to_base64(b"image_data")

        assert isinstance(result, str)

    def test_from_base64(self) -> None:
        """Test conversion from base64."""
        processor = MockImageProcessor()

        # Set mock response
        processor._from_base64_result = b"decoded_data"
        result = processor.from_base64("base64_string")

        assert isinstance(result, bytes)

    def test_get_dimensions(self) -> None:
        """Test getting image dimensions."""
        processor = MockImageProcessor()

        width, height = processor.get_dimensions(b"image_data")

        assert width == 640
        assert height == 480


class TestPILImageProcessor:
    """Tests for PILImageProcessor class."""

    def test_initialization(self) -> None:
        """Test processor initialization."""
        processor = PILImageProcessor()
        assert processor is not None

    def test_to_base64_with_valid_image(self, sample_face_image: bytes) -> None:
        """Test base64 encoding of valid image."""
        processor = PILImageProcessor()

        result = processor.to_base64(sample_face_image)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_from_base64(self) -> None:
        """Test base64 decoding."""
        processor = PILImageProcessor()

        # Create a simple base64 string
        import base64
        original = b"test_data"
        b64_string = base64.b64encode(original).decode()

        result = processor.from_base64(b64_string)

        assert result == original

    def test_get_dimensions_with_valid_image(self, sample_face_image: bytes) -> None:
        """Test getting dimensions of valid image."""
        processor = PILImageProcessor()

        width, height = processor.get_dimensions(sample_face_image)

        assert width > 0
        assert height > 0
