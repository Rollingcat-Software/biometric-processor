"""Shared biometric response schema for voice and fingerprint endpoints."""

from typing import Optional

from pydantic import BaseModel


class BiometricResponse(BaseModel):
    """Unified response model for voice and fingerprint biometric operations.

    Used by both voice.py and fingerprint.py routes to avoid duplication.
    """

    success: bool
    message: str
    user_id: Optional[str] = None
    confidence: Optional[float] = None
    modality: str = "biometric"
    implemented: bool = True
    embedding_dimension: Optional[int] = None
    verified: Optional[bool] = None
