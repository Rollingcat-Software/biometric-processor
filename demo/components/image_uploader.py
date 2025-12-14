"""Enhanced image upload component with validation.

This module provides a reusable image upload component with:
    - File upload support (JPEG, PNG)
    - Image preview
    - Size validation
    - Format validation

Example:
    >>> uploader = ImageUploader(max_size_mb=10)
    >>> uploader.render()
    >>> if uploader.has_image:
    ...     image_bytes = uploader.get_image_bytes()
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any

import streamlit as st
from PIL import Image

from components.base import BaseComponent
from utils.config import get_settings
from utils.exceptions import ImageValidationError

if TYPE_CHECKING:
    from utils.container import DependencyContainer


class ImageUploader(BaseComponent):
    """Enhanced image upload component with validation.

    Provides a consistent interface for image uploads across the demo app
    with built-in validation and preview functionality.

    Attributes:
        _max_size_mb: Maximum file size in megabytes.
        _accepted_types: List of accepted MIME types.
        _uploaded_file: Current uploaded file or None.
        _label: Upload button label.

    Example:
        >>> uploader = ImageUploader(label="Upload Face Image")
        >>> uploader.render()
        >>> if uploader.has_image:
        ...     process_image(uploader.get_image_bytes())
    """

    ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/jpg"]
    ACCEPTED_EXTENSIONS = ["jpg", "jpeg", "png"]

    def __init__(
        self,
        container: DependencyContainer | None = None,
        key: str | None = None,
        label: str = "Upload Image",
        max_size_mb: float | None = None,
        show_preview: bool = True,
        help_text: str | None = None,
    ) -> None:
        """Initialize image uploader component.

        Args:
            container: Dependency injection container.
            key: Unique Streamlit key for this component.
            label: Label for the upload button.
            max_size_mb: Maximum file size in MB. Defaults to settings value.
            show_preview: Whether to show image preview.
            help_text: Help text displayed below uploader.
        """
        super().__init__(container=container, key=key)

        settings = get_settings()
        self._max_size_mb = max_size_mb or settings.max_image_size_mb
        self._label = label
        self._show_preview = show_preview
        self._help_text = help_text or f"Max size: {self._max_size_mb}MB. Formats: JPEG, PNG"
        self._uploaded_file: Any = None
        self._validated_bytes: bytes | None = None

    @property
    def has_image(self) -> bool:
        """Check if a valid image has been uploaded."""
        return self._validated_bytes is not None

    def get_image_bytes(self) -> bytes | None:
        """Get validated image bytes.

        Returns:
            Image bytes if valid image uploaded, None otherwise.
        """
        return self._validated_bytes

    def get_image_pil(self) -> Image.Image | None:
        """Get uploaded image as PIL Image.

        Returns:
            PIL Image if valid image uploaded, None otherwise.
        """
        if self._validated_bytes:
            return Image.open(io.BytesIO(self._validated_bytes))
        return None

    def get_filename(self) -> str | None:
        """Get the original filename.

        Returns:
            Original filename or None if no file uploaded.
        """
        if self._uploaded_file:
            return self._uploaded_file.name
        return None

    def render(self) -> None:
        """Render the image upload component."""
        self._uploaded_file = st.file_uploader(
            self._label,
            type=self.ACCEPTED_EXTENSIONS,
            key=f"{self._key}_uploader",
            help=self._help_text,
        )

        if self._uploaded_file is not None:
            try:
                self._validate_and_process()

                if self._show_preview and self._validated_bytes:
                    self._render_preview()

            except ImageValidationError as e:
                st.error(e.to_user_message())
                self._validated_bytes = None

    def _validate_and_process(self) -> None:
        """Validate and process the uploaded file."""
        # Check file size
        file_size_mb = len(self._uploaded_file.getvalue()) / (1024 * 1024)
        if file_size_mb > self._max_size_mb:
            raise ImageValidationError(
                reason="too_large",
                details={"size_mb": file_size_mb, "max_mb": self._max_size_mb},
            )

        # Read file bytes
        file_bytes = self._uploaded_file.getvalue()

        # Validate it's a valid image
        try:
            img = Image.open(io.BytesIO(file_bytes))
            img.verify()  # Verify it's a valid image

            # Reopen after verify (verify closes the file)
            img = Image.open(io.BytesIO(file_bytes))

            # Check format
            if img.format not in ["JPEG", "PNG"]:
                raise ImageValidationError(
                    reason="invalid_format",
                    details={"format": img.format},
                )

            self._validated_bytes = file_bytes

        except ImageValidationError:
            raise
        except Exception as e:
            raise ImageValidationError(
                reason="invalid_format",
                details={"error": str(e)},
            )

    def _render_preview(self) -> None:
        """Render image preview with metadata."""
        if not self._validated_bytes:
            return

        img = Image.open(io.BytesIO(self._validated_bytes))

        col1, col2 = st.columns([2, 1])

        with col1:
            st.image(img, caption="Uploaded Image", use_container_width=True)

        with col2:
            st.markdown("**Image Info**")
            st.text(f"Size: {img.width} x {img.height}")
            st.text(f"Format: {img.format}")
            st.text(f"Mode: {img.mode}")

            file_size = len(self._validated_bytes) / 1024
            if file_size < 1024:
                st.text(f"File: {file_size:.1f} KB")
            else:
                st.text(f"File: {file_size/1024:.2f} MB")

    def get_state(self) -> dict[str, Any]:
        """Get current component state.

        Returns:
            Dictionary containing uploader state.
        """
        return {
            "has_image": self.has_image,
            "filename": self.get_filename(),
            "max_size_mb": self._max_size_mb,
        }


def render_image_uploader(
    label: str = "Upload Image",
    key: str = "image_uploader",
    max_size_mb: float | None = None,
    show_preview: bool = True,
) -> ImageUploader:
    """Convenience function to create and render an image uploader.

    Args:
        label: Upload button label.
        key: Unique Streamlit key.
        max_size_mb: Maximum file size in MB.
        show_preview: Whether to show preview.

    Returns:
        ImageUploader instance after rendering.
    """
    uploader = ImageUploader(
        key=key,
        label=label,
        max_size_mb=max_size_mb,
        show_preview=show_preview,
    )
    uploader.render()
    return uploader
