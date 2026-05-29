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
    # 0..100 enrollment quality score (voice: computed from signal duration /
    # loudness / SNR). identity-core-api reads this off the JSON and rescales
    # 0..100 → 0..1 for the user_enrollments.quality_score column (P1-3).
    quality_score: Optional[float] = None
