"""Input validation utilities for security and data integrity.

This module provides validation functions for user inputs to prevent:
- SQL injection
- Path traversal
- Command injection
- XSS attacks
- Invalid data formats
- File type spoofing
"""

import imghdr
import re
from pathlib import Path
from typing import Optional

# Patterns for validation
# User ID and Tenant ID: alphanumeric, hyphens, underscores only
# Length: 1-255 characters
USER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,255}$")
TENANT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,255}$")

# Email pattern (basic validation)
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class ValidationError(ValueError):
    """Raised when input validation fails.

    This is a domain exception that should be caught by the API layer
    and converted to appropriate HTTP error responses.
    """

    pass


def validate_user_id(user_id: str) -> str:
    """Validate user ID format.

    Args:
        user_id: User identifier to validate

    Returns:
        Validated user_id (stripped of whitespace)

    Raises:
        ValidationError: If user_id format is invalid

    Security:
        - Prevents SQL injection
        - Prevents path traversal
        - Prevents command injection
        - Enforces strict alphanumeric format

    Examples:
        >>> validate_user_id("user123")
        'user123'
        >>> validate_user_id("user-456_abc")
        'user-456_abc'
        >>> validate_user_id("user@email.com")  # raises ValidationError
        >>> validate_user_id("'; DROP TABLE--")  # raises ValidationError
    """
    if not user_id or not isinstance(user_id, str):
        raise ValidationError("user_id must be a non-empty string")

    # Strip whitespace
    user_id = user_id.strip()

    # Check length
    if len(user_id) == 0:
        raise ValidationError("user_id cannot be empty or whitespace")

    if len(user_id) > 255:
        raise ValidationError(
            f"user_id too long: {len(user_id)} characters (max 255)"
        )

    # Validate format
    if not USER_ID_PATTERN.match(user_id):
        raise ValidationError(
            "user_id must contain only alphanumeric characters, hyphens, and underscores"
        )

    return user_id


def validate_tenant_id(tenant_id: Optional[str]) -> Optional[str]:
    """Validate tenant ID format.

    Args:
        tenant_id: Optional tenant identifier to validate

    Returns:
        Validated tenant_id (stripped of whitespace) or None

    Raises:
        ValidationError: If tenant_id format is invalid

    Security:
        - Prevents SQL injection
        - Prevents path traversal
        - Prevents command injection
        - Enforces strict alphanumeric format

    Examples:
        >>> validate_tenant_id(None)
        None
        >>> validate_tenant_id("tenant-123")
        'tenant-123'
        >>> validate_tenant_id("'; DELETE FROM--")  # raises ValidationError
    """
    if tenant_id is None:
        return None

    if not isinstance(tenant_id, str):
        raise ValidationError("tenant_id must be a string or None")

    # Strip whitespace
    tenant_id = tenant_id.strip()

    # Empty string is treated as None
    if len(tenant_id) == 0:
        return None

    # Check length
    if len(tenant_id) > 255:
        raise ValidationError(
            f"tenant_id too long: {len(tenant_id)} characters (max 255)"
        )

    # Validate format
    if not TENANT_ID_PATTERN.match(tenant_id):
        raise ValidationError(
            "tenant_id must contain only alphanumeric characters, hyphens, and underscores"
        )

    return tenant_id


def validate_file_extension(filename: str, allowed_extensions: list[str]) -> bool:
    """Validate file extension.

    Args:
        filename: Filename to check
        allowed_extensions: List of allowed extensions (e.g., ['jpg', 'png'])

    Returns:
        True if extension is allowed, False otherwise

    Examples:
        >>> validate_file_extension("photo.jpg", ["jpg", "png"])
        True
        >>> validate_file_extension("malware.exe", ["jpg", "png"])
        False
    """
    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in [ext.lower() for ext in allowed_extensions]


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename (only basename, special chars removed)

    Security:
        - Removes path components (../, /, \\)
        - Removes special characters
        - Limits length

    Examples:
        >>> sanitize_filename("photo.jpg")
        'photo.jpg'
        >>> sanitize_filename("../../etc/passwd")
        'passwd'
        >>> sanitize_filename("file<script>.jpg")
        'filescript.jpg'
    """
    import os

    # Get basename only (removes path components)
    filename = os.path.basename(filename)

    # Remove dangerous characters
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", filename)

    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[: 255 - len(ext)] + ext

    return filename


def validate_quality_score(score: float) -> float:
    """Validate quality score is in valid range.

    Args:
        score: Quality score to validate

    Returns:
        Validated score

    Raises:
        ValidationError: If score is out of range

    Examples:
        >>> validate_quality_score(75.5)
        75.5
        >>> validate_quality_score(-5.0)  # raises ValidationError
        >>> validate_quality_score(150.0)  # raises ValidationError
    """
    if not isinstance(score, (int, float)):
        raise ValidationError(f"quality_score must be a number, got {type(score)}")

    if not 0 <= score <= 100:
        raise ValidationError(
            f"quality_score must be between 0 and 100, got {score}"
        )

    return float(score)


def validate_threshold(threshold: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Validate threshold is in valid range.

    Args:
        threshold: Threshold value to validate
        min_val: Minimum allowed value (default: 0.0)
        max_val: Maximum allowed value (default: 1.0)

    Returns:
        Validated threshold

    Raises:
        ValidationError: If threshold is out of range

    Examples:
        >>> validate_threshold(0.6)
        0.6
        >>> validate_threshold(1.5)  # raises ValidationError
    """
    if not isinstance(threshold, (int, float)):
        raise ValidationError(f"threshold must be a number, got {type(threshold)}")

    if not min_val <= threshold <= max_val:
        raise ValidationError(
            f"threshold must be between {min_val} and {max_val}, got {threshold}"
        )

    return float(threshold)


def validate_positive_integer(value: int, name: str = "value", max_val: int = None) -> int:
    """Validate value is a positive integer.

    Args:
        value: Value to validate
        name: Name of the parameter (for error messages)
        max_val: Optional maximum value

    Returns:
        Validated integer

    Raises:
        ValidationError: If value is invalid

    Examples:
        >>> validate_positive_integer(5, "limit")
        5
        >>> validate_positive_integer(-1, "limit")  # raises ValidationError
        >>> validate_positive_integer(100, "limit", max_val=50)  # raises ValidationError
    """
    if not isinstance(value, int):
        raise ValidationError(f"{name} must be an integer, got {type(value)}")

    if value <= 0:
        raise ValidationError(f"{name} must be positive, got {value}")

    if max_val is not None and value > max_val:
        raise ValidationError(f"{name} must be <= {max_val}, got {value}")

    return value


def validate_image_file(file_path: str, allowed_formats: list[str] = None) -> str:
    """Validate file is actually an image by checking magic bytes.

    This function performs actual file content validation instead of trusting
    the Content-Type header, which can be easily spoofed by attackers.

    Args:
        file_path: Path to the file to validate
        allowed_formats: List of allowed image formats (default: ['jpeg', 'png', 'gif', 'bmp'])

    Returns:
        Detected image format (e.g., 'jpeg', 'png')

    Raises:
        ValidationError: If file is not a valid image or format not allowed

    Security:
        - Detects actual file type using magic bytes (file signatures)
        - Prevents file type confusion attacks
        - Prevents malware disguised as images
        - Does not trust Content-Type headers

    Examples:
        >>> validate_image_file("/tmp/photo.jpg")
        'jpeg'
        >>> validate_image_file("/tmp/malware.exe")  # raises ValidationError
        >>> validate_image_file("/tmp/script.jpg")  # raises ValidationError if not actual image
    """
    if allowed_formats is None:
        allowed_formats = ['jpeg', 'png', 'gif', 'bmp']

    # Convert formats to lowercase for comparison
    allowed_formats = [fmt.lower() for fmt in allowed_formats]

    # Check file exists
    if not Path(file_path).exists():
        raise ValidationError(f"File not found: {file_path}")

    # Detect actual file type using magic bytes
    try:
        detected_type = imghdr.what(file_path)
    except Exception as e:
        raise ValidationError(f"Failed to detect image type: {str(e)}")

    # Check if file is actually an image
    if detected_type is None:
        raise ValidationError(
            "File is not a valid image. File type detection failed. "
            "Please upload a valid JPEG, PNG, GIF, or BMP image."
        )

    # Normalize detected type (imghdr returns 'jpeg' for both jpg and jpeg)
    if detected_type == 'jpeg':
        detected_type = 'jpeg'  # Already normalized

    # Check if format is allowed
    if detected_type not in allowed_formats:
        raise ValidationError(
            f"Image format not allowed. Detected: {detected_type}, "
            f"Allowed: {', '.join(allowed_formats)}"
        )

    return detected_type
