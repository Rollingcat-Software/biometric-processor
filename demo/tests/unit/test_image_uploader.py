"""Unit tests for ImageUploader component.

Tests the image upload component functionality including validation.
"""

from __future__ import annotations

import pytest

from components.image_uploader import ImageUploader
from utils.exceptions import ImageValidationError


class TestImageUploader:
    """Tests for ImageUploader component."""

    def test_initialization_defaults(self) -> None:
        """Test component initialization with defaults."""
        uploader = ImageUploader()

        assert uploader.key == "ImageUploader"
        assert uploader._max_size_mb == 10  # Default from settings
        assert uploader._show_preview is True
        assert uploader.has_image is False

    def test_initialization_custom(self) -> None:
        """Test component initialization with custom values."""
        uploader = ImageUploader(
            key="custom_uploader",
            label="Custom Label",
            max_size_mb=5,
            show_preview=False,
        )

        assert uploader.key == "custom_uploader"
        assert uploader._label == "Custom Label"
        assert uploader._max_size_mb == 5
        assert uploader._show_preview is False

    def test_has_image_false_initially(self) -> None:
        """Test that has_image is False before upload."""
        uploader = ImageUploader()
        assert uploader.has_image is False

    def test_get_image_bytes_none_initially(self) -> None:
        """Test that get_image_bytes returns None before upload."""
        uploader = ImageUploader()
        assert uploader.get_image_bytes() is None

    def test_get_image_pil_none_initially(self) -> None:
        """Test that get_image_pil returns None before upload."""
        uploader = ImageUploader()
        assert uploader.get_image_pil() is None

    def test_get_filename_none_initially(self) -> None:
        """Test that get_filename returns None before upload."""
        uploader = ImageUploader()
        assert uploader.get_filename() is None

    def test_get_state(self) -> None:
        """Test get_state returns correct state dictionary."""
        uploader = ImageUploader(
            key="test_uploader",
            max_size_mb=5,
        )

        state = uploader.get_state()

        assert state["has_image"] is False
        assert state["filename"] is None
        assert state["max_size_mb"] == 5

    def test_accepted_types(self) -> None:
        """Test that accepted types are correct."""
        assert "image/jpeg" in ImageUploader.ACCEPTED_TYPES
        assert "image/png" in ImageUploader.ACCEPTED_TYPES

    def test_accepted_extensions(self) -> None:
        """Test that accepted extensions are correct."""
        assert "jpg" in ImageUploader.ACCEPTED_EXTENSIONS
        assert "jpeg" in ImageUploader.ACCEPTED_EXTENSIONS
        assert "png" in ImageUploader.ACCEPTED_EXTENSIONS


class TestImageUploaderValidation:
    """Tests for ImageUploader validation logic."""

    def test_valid_jpeg_bytes(self, sample_face_image: bytes) -> None:
        """Test validation of valid JPEG bytes."""
        uploader = ImageUploader()
        uploader._validated_bytes = sample_face_image

        assert uploader.has_image is True
        assert uploader.get_image_bytes() == sample_face_image

    def test_valid_png_bytes(self, sample_png_image: bytes) -> None:
        """Test validation of valid PNG bytes."""
        uploader = ImageUploader()
        uploader._validated_bytes = sample_png_image

        assert uploader.has_image is True
        assert uploader.get_image_bytes() == sample_png_image


class TestImageUploaderWithMockUpload:
    """Tests for ImageUploader with mock file upload."""

    def test_state_after_setting_bytes(self, sample_face_image: bytes) -> None:
        """Test state after manually setting validated bytes."""
        uploader = ImageUploader(key="test")
        uploader._validated_bytes = sample_face_image

        state = uploader.get_state()
        assert state["has_image"] is True

    def test_clear_image(self) -> None:
        """Test clearing uploaded image."""
        uploader = ImageUploader()
        uploader._validated_bytes = b"test_data"

        # Clear the image
        uploader._validated_bytes = None

        assert uploader.has_image is False
        assert uploader.get_image_bytes() is None
