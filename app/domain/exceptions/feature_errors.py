"""Feature-specific domain exceptions.

This module contains exceptions for new features:
- Demographics analysis
- Landmark detection
- Image preprocessing
- Webhooks
- Export/Import
- Rate limiting
"""

from app.domain.exceptions.base import BiometricProcessorError


# ============================================================================
# Demographics Exceptions
# ============================================================================


class DemographicsError(BiometricProcessorError):
    """Base exception for demographics analysis errors."""

    def __init__(self, message: str = "Demographics analysis failed"):
        super().__init__(message, "DEMOGRAPHICS_ERROR")


class DemographicsModelError(DemographicsError):
    """Demographics model loading or inference error."""

    def __init__(self, message: str = "Demographics model error"):
        super().__init__(message)
        self.error_code = "DEMOGRAPHICS_MODEL_ERROR"


# ============================================================================
# Landmark Exceptions
# ============================================================================


class LandmarkError(BiometricProcessorError):
    """Base exception for landmark detection errors."""

    def __init__(self, message: str = "Landmark detection failed"):
        super().__init__(message, "LANDMARK_ERROR")


class LandmarkModelError(LandmarkError):
    """Landmark model loading or inference error."""

    def __init__(self, message: str = "Landmark model error"):
        super().__init__(message)
        self.error_code = "LANDMARK_MODEL_ERROR"


# ============================================================================
# Preprocessing Exceptions
# ============================================================================


class PreprocessingError(BiometricProcessorError):
    """Image preprocessing error."""

    def __init__(self, message: str = "Image preprocessing failed"):
        super().__init__(message, "PREPROCESSING_ERROR")


# ============================================================================
# Webhook Exceptions
# ============================================================================


class WebhookError(BiometricProcessorError):
    """Base exception for webhook errors."""

    def __init__(self, message: str = "Webhook error"):
        super().__init__(message, "WEBHOOK_ERROR")


class WebhookDeliveryError(WebhookError):
    """Webhook delivery failed after retries."""

    def __init__(self, message: str = "Webhook delivery failed after retries"):
        super().__init__(message)
        self.error_code = "WEBHOOK_DELIVERY_FAILED"


class WebhookTimeoutError(WebhookError):
    """Webhook request timed out."""

    def __init__(self, message: str = "Webhook request timed out"):
        super().__init__(message)
        self.error_code = "WEBHOOK_TIMEOUT"


class WebhookConfigError(WebhookError):
    """Webhook configuration error."""

    def __init__(self, message: str = "Invalid webhook configuration"):
        super().__init__(message)
        self.error_code = "WEBHOOK_CONFIG_ERROR"


# ============================================================================
# Export/Import Exceptions
# ============================================================================


class ExportError(BiometricProcessorError):
    """Embedding export error."""

    def __init__(self, message: str = "Export failed"):
        super().__init__(message, "EXPORT_ERROR")


class EmbeddingImportError(BiometricProcessorError):
    """Embedding import error."""

    def __init__(self, message: str = "Import failed"):
        super().__init__(message, "IMPORT_ERROR")


class ImportValidationError(EmbeddingImportError):
    """Import file validation failed."""

    def __init__(self, message: str = "Import file validation failed"):
        super().__init__(message)
        self.error_code = "IMPORT_VALIDATION_ERROR"


# ============================================================================
# Rate Limiting Exceptions
# ============================================================================


class RateLimitError(BiometricProcessorError):
    """Rate limit exceeded error."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 60,
        limit: int = 60,
        tier: str = "standard",
    ):
        super().__init__(message, "RATE_LIMIT_EXCEEDED")
        self.retry_after = retry_after
        self.limit = limit
        self.tier = tier

    def to_dict(self) -> dict:
        """Convert to dictionary including rate limit info."""
        result = super().to_dict()
        result.update(
            {
                "retry_after": self.retry_after,
                "limit": self.limit,
                "tier": self.tier,
            }
        )
        return result
