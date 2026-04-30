"""Shared biometric response schema for voice endpoints (and other future modalities)."""

from typing import Optional

from pydantic import BaseModel


class BiometricResponse(BaseModel):
    """Unified response model for voice biometric operations.

    Originally shared with fingerprint endpoints, which were removed in P1.4
    (SHA-256 hash placeholder was not a real biometric — platform fingerprint
    is now provided exclusively via WebAuthn in identity-core-api).
    """

    success: bool
    message: str
    user_id: Optional[str] = None
    confidence: Optional[float] = None
    modality: str = "biometric"
    implemented: bool = True
    embedding_dimension: Optional[int] = None
    verified: Optional[bool] = None
