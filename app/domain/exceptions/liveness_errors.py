"""Liveness detection related errors."""

from app.domain.exceptions.base import BiometricProcessorError


class LivenessCheckFailedError(BiometricProcessorError):
    """Raised when liveness check fails (spoofing detected or low score).

    This indicates:
    - Possible spoofing attack (photo, video, mask)
    - Insufficient liveness indicators
    - Challenge not completed properly
    """

    def __init__(
        self, liveness_score: float, min_threshold: float = 80.0, challenge: str = "unknown"
    ) -> None:
        """Initialize liveness check failed error.

        Args:
            liveness_score: Actual liveness score (0-100)
            min_threshold: Minimum acceptable liveness score
            challenge: Type of liveness challenge used
        """
        super().__init__(
            message=(
                f"Liveness check failed (score: {liveness_score:.0f}/100, "
                f"minimum: {min_threshold:.0f}). Challenge: {challenge}. "
                "Please ensure you're a live person performing the requested action."
            ),
            error_code="LIVENESS_CHECK_FAILED",
        )
        self.liveness_score = liveness_score
        self.min_threshold = min_threshold
        self.challenge = challenge

    def to_dict(self) -> dict:
        """Include liveness details in error response."""
        result = super().to_dict()
        result["liveness_score"] = self.liveness_score
        result["min_threshold"] = self.min_threshold
        result["challenge"] = self.challenge
        return result


class LivenessCheckError(BiometricProcessorError):
    """Raised when liveness check encounters an error during processing.

    This is different from LivenessCheckFailedError - it indicates
    a technical error rather than a failed liveness test.
    """

    def __init__(self, reason: str = "Unknown error") -> None:
        """Initialize liveness check error.

        Args:
            reason: Detailed reason for error
        """
        super().__init__(
            message=f"Liveness check error: {reason}",
            error_code="LIVENESS_CHECK_ERROR",
        )
        self.reason = reason

    def to_dict(self) -> dict:
        """Include failure reason in error response."""
        result = super().to_dict()
        result["reason"] = self.reason
        return result


class LivenessModelLoadError(BiometricProcessorError):
    """Raised when an anti-spoof / liveness ML model cannot be loaded.

    Background (2026-05-12 compound liveness bug, Team A fix branch
    ``fix/2026-05-12-deepface-error-handling``):
        DeepFace 0.0.98 attempts to download MiniFASNet weights from GitHub on
        first inference (see ``deepface/commons/weight_utils.py:62``). When the
        download fails the library raises ``ValueError`` whose ``str(exc)``
        contains the URL ``anti_spoof_models/...`` — the literal substring
        "spoof". Before this class existed the detector's error handler
        matched on the substring "spoof" and silently tagged every user as
        ``antispoof_label="spoof"``, which the conservative verdict policy
        then turned into ``is_live=False`` for every verify call until an
        operator manually placed the weights in the cache.

    This exception lets the detector distinguish "model unavailable" from
    "real spoof verdict" so the use case can apply an explicit, configurable
    policy (``LIVENESS_ANTISPOOF_MODEL_MISSING_POLICY``) instead of failing
    closed silently.
    """

    def __init__(
        self,
        model_name: str,
        cause: str | None = None,
        target_path: str | None = None,
    ) -> None:
        """Initialize the liveness model load error.

        Args:
            model_name: Friendly name of the missing model (e.g.
                ``"MiniFASNetV2"``). Used in logs and operator alerts.
            cause: Original exception message, useful when the underlying
                library wraps a network error or a file-permission error.
            target_path: Filesystem path where the model was expected. The
                operator can use this to drop the weights in manually.
        """
        message_parts = [
            f"Anti-spoof / liveness model '{model_name}' is unavailable."
        ]
        if target_path:
            message_parts.append(f"Expected at: {target_path}.")
        if cause:
            message_parts.append(f"Underlying cause: {cause}")
        super().__init__(
            message=" ".join(message_parts),
            error_code="LIVENESS_MODEL_UNAVAILABLE",
        )
        self.model_name = model_name
        self.cause = cause
        self.target_path = target_path

    def to_dict(self) -> dict:
        """Include model + cause details in error response."""
        result = super().to_dict()
        result["model_name"] = self.model_name
        if self.cause is not None:
            result["cause"] = self.cause
        if self.target_path is not None:
            result["target_path"] = self.target_path
        return result
