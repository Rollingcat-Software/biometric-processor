"""Input validators for proctoring endpoints."""

import base64
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Constants
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_AUDIO_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
MAX_METADATA_DEPTH = 3
MAX_LIST_SIZE = 100
MAX_STRING_LENGTH = 1000

# Image magic bytes
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
WEBP_MAGIC_RIFF = b"RIFF"
WEBP_MAGIC_WEBP = b"WEBP"


class ImageValidator:
    """Validate image data for security and correctness."""

    @staticmethod
    def validate_base64_image(
        data: str,
        max_size: int = MAX_IMAGE_SIZE_BYTES,
    ) -> bytes:
        """Validate and decode base64 image data.

        Args:
            data: Base64-encoded image string
            max_size: Maximum allowed size in bytes

        Returns:
            Decoded image bytes

        Raises:
            ValueError: If validation fails
        """
        if not data:
            raise ValueError("Image data is empty")

        # Check base64 string length (rough estimate before decode)
        # Base64 has ~33% overhead, so max_size * 1.4 is approximate
        if len(data) > max_size * 1.4:
            raise ValueError(f"Image data too large (max {max_size} bytes)")

        try:
            decoded = base64.b64decode(data)
        except Exception as e:
            raise ValueError(f"Invalid base64 encoding: {e}")

        # Check decoded size
        if len(decoded) > max_size:
            raise ValueError(
                f"Image exceeds maximum size: {len(decoded)} > {max_size} bytes"
            )

        # Validate image format
        if not ImageValidator._is_valid_image(decoded):
            raise ValueError("Invalid image format (must be JPEG, PNG, or WebP)")

        return decoded

    @staticmethod
    def _is_valid_image(data: bytes) -> bool:
        """Check if data is a valid image format.

        Args:
            data: Raw image bytes

        Returns:
            True if valid image format
        """
        if len(data) < 12:
            return False

        # Check JPEG
        if data[:3] == JPEG_MAGIC:
            return True

        # Check PNG
        if data[:8] == PNG_MAGIC:
            return True

        # Check WebP
        if data[:4] == WEBP_MAGIC_RIFF and data[8:12] == WEBP_MAGIC_WEBP:
            return True

        return False

    @staticmethod
    def get_image_info(data: bytes) -> Dict[str, Any]:
        """Extract basic image information.

        Args:
            data: Raw image bytes

        Returns:
            Dictionary with image info
        """
        info = {
            "size_bytes": len(data),
            "format": "unknown",
        }

        if data[:3] == JPEG_MAGIC:
            info["format"] = "jpeg"
        elif data[:8] == PNG_MAGIC:
            info["format"] = "png"
        elif data[:4] == WEBP_MAGIC_RIFF and data[8:12] == WEBP_MAGIC_WEBP:
            info["format"] = "webp"

        return info


class InputSanitizer:
    """Sanitize user inputs to prevent injection attacks."""

    # Pattern for potentially dangerous content
    SCRIPT_PATTERN = re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
    HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
    NULL_BYTE_PATTERN = re.compile(r"\x00")

    # SQL injection patterns (for logging/detection, not primary defense)
    SQL_KEYWORDS = re.compile(
        r"\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|OR|AND|EXEC|EXECUTE)\b",
        re.IGNORECASE,
    )

    @staticmethod
    def sanitize_string(
        value: str,
        max_length: int = MAX_STRING_LENGTH,
        allow_html: bool = False,
    ) -> str:
        """Sanitize a string input.

        Args:
            value: Input string
            max_length: Maximum allowed length
            allow_html: Whether to allow HTML tags

        Returns:
            Sanitized string
        """
        if not value:
            return value

        # Truncate to max length
        sanitized = value[:max_length]

        # Remove null bytes
        sanitized = InputSanitizer.NULL_BYTE_PATTERN.sub("", sanitized)

        # Strip HTML tags unless allowed
        if not allow_html:
            sanitized = InputSanitizer.HTML_TAG_PATTERN.sub("", sanitized)

        # Remove script tags regardless
        sanitized = InputSanitizer.SCRIPT_PATTERN.sub("", sanitized)

        # Log potential SQL injection attempts (for monitoring)
        if InputSanitizer.SQL_KEYWORDS.search(value):
            logger.warning("Potential SQL injection detected in input")

        return sanitized.strip()

    @staticmethod
    def sanitize_metadata(
        metadata: Optional[Dict[str, Any]],
        max_depth: int = MAX_METADATA_DEPTH,
    ) -> Dict[str, Any]:
        """Sanitize metadata dictionary.

        Args:
            metadata: Input metadata dictionary
            max_depth: Maximum nesting depth

        Returns:
            Sanitized metadata
        """
        if not metadata:
            return {}

        def sanitize_value(val: Any, depth: int = 0) -> Any:
            if depth > max_depth:
                return None

            if isinstance(val, str):
                return InputSanitizer.sanitize_string(val)

            if isinstance(val, dict):
                return {
                    InputSanitizer.sanitize_string(str(k), max_length=255): sanitize_value(
                        v, depth + 1
                    )
                    for k, v in list(val.items())[:MAX_LIST_SIZE]
                }

            if isinstance(val, list):
                return [
                    sanitize_value(v, depth + 1) for v in val[:MAX_LIST_SIZE]
                ]

            if isinstance(val, (int, float, bool, type(None))):
                return val

            # Convert other types to string
            return InputSanitizer.sanitize_string(str(val), max_length=255)

        return sanitize_value(metadata)

    @staticmethod
    def sanitize_uuid(value: str) -> str:
        """Validate and sanitize UUID string.

        Args:
            value: Input UUID string

        Returns:
            Validated UUID string

        Raises:
            ValueError: If not a valid UUID
        """
        import uuid

        try:
            # Parse and re-format to ensure valid format
            parsed = uuid.UUID(value)
            return str(parsed)
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid UUID format: {value}")

    @staticmethod
    def sanitize_tenant_id(value: str) -> str:
        """Sanitize tenant ID.

        Args:
            value: Input tenant ID

        Returns:
            Sanitized tenant ID

        Raises:
            ValueError: If invalid
        """
        if not value:
            raise ValueError("Tenant ID is required")

        # Only allow alphanumeric, hyphens, underscores
        sanitized = re.sub(r"[^a-zA-Z0-9\-_]", "", value)

        if len(sanitized) < 1 or len(sanitized) > 255:
            raise ValueError("Invalid tenant ID length")

        if sanitized != value:
            logger.warning(f"Tenant ID sanitized: {value} -> {sanitized}")

        return sanitized


# Convenience functions
def validate_base64_image(data: str, max_size: int = MAX_IMAGE_SIZE_BYTES) -> bytes:
    """Validate and decode base64 image data."""
    return ImageValidator.validate_base64_image(data, max_size)


def sanitize_string(value: str, max_length: int = MAX_STRING_LENGTH) -> str:
    """Sanitize a string input."""
    return InputSanitizer.sanitize_string(value, max_length)


def sanitize_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Sanitize metadata dictionary."""
    return InputSanitizer.sanitize_metadata(metadata)
