"""Fingerprint biometric endpoints — enrollment, verification, deletion.

Uses a hash-based embedder to produce 256-dimensional embeddings from
fingerprint image data, stored in pgvector with a centroid-based pattern
(same as face/voice). When a real fingerprint scanner SDK is available,
only the embedding extraction layer needs to change.

Integration:
    Called by identity-core-api BiometricServiceAdapter via JSON:
        POST /fingerprint/enroll  {"user_id": "...", "fingerprint_data": "<base64>"}
        POST /fingerprint/verify  {"user_id": "...", "fingerprint_data": "<base64>"}
        DELETE /fingerprint/{user_id}
"""

import logging
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.container import get_fingerprint_embedder, get_fingerprint_repository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Fingerprint"])

# ── Request / Response schemas ──────────────────────────────────────


class FingerprintRequest(BaseModel):
    user_id: str
    fingerprint_data: str  # base64-encoded fingerprint image


class BiometricResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[str] = None
    confidence: Optional[float] = None
    modality: str = "fingerprint"
    implemented: bool = True
    embedding_dimension: Optional[int] = None
    verified: Optional[bool] = None


# ── POST /fingerprint/enroll ────────────────────────────────────────


@router.post("/fingerprint/enroll", response_model=BiometricResponse)
async def enroll_fingerprint(request: FingerprintRequest) -> BiometricResponse:
    """Enroll a user's fingerprint biometric.

    Accepts base64-encoded fingerprint image, extracts a 256-dim embedding
    via hash-based embedder, stores it as an INDIVIDUAL enrollment row,
    and recomputes the CENTROID.
    """
    try:
        user_id = request.user_id.strip()
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        fingerprint_data = request.fingerprint_data.strip()
        if not fingerprint_data:
            raise HTTPException(status_code=400, detail="fingerprint_data is required")

        logger.info(f"Fingerprint enrollment request: user_id={user_id}")

        # Extract fingerprint embedding
        embedder = get_fingerprint_embedder()
        embedding = embedder.extract_embedding_from_base64(fingerprint_data)

        # Store in database
        repo = get_fingerprint_repository()
        await repo.save(
            user_id=user_id,
            embedding=embedding,
            quality_score=1.0,
        )

        logger.info(
            f"Fingerprint enrolled: user_id={user_id}, dim={len(embedding)}"
        )

        return BiometricResponse(
            success=True,
            message="Fingerprint enrolled successfully",
            user_id=user_id,
            embedding_dimension=len(embedding),
        )

    except ValueError as e:
        logger.warning(f"Fingerprint enrollment validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fingerprint enrollment failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Fingerprint enrollment failed: {e}",
        )


# ── POST /fingerprint/verify ───────────────────────────────────────


@router.post("/fingerprint/verify", response_model=BiometricResponse)
async def verify_fingerprint(request: FingerprintRequest) -> BiometricResponse:
    """Verify a user's fingerprint against their enrolled centroid.

    Returns cosine similarity as confidence. Threshold is 0.70.
    """
    VERIFY_THRESHOLD = 0.70

    try:
        user_id = request.user_id.strip()
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        fingerprint_data = request.fingerprint_data.strip()
        if not fingerprint_data:
            raise HTTPException(status_code=400, detail="fingerprint_data is required")

        logger.info(f"Fingerprint verification request: user_id={user_id}")

        # Extract fingerprint embedding from probe image
        embedder = get_fingerprint_embedder()
        probe_embedding = embedder.extract_embedding_from_base64(fingerprint_data)

        # Load enrolled centroid
        repo = get_fingerprint_repository()
        enrolled_embedding = await repo.find_by_user_id(user_id)

        if enrolled_embedding is None:
            return BiometricResponse(
                success=False,
                verified=False,
                message="No fingerprint enrollment found for this user",
                user_id=user_id,
                confidence=0.0,
            )

        # Cosine similarity (both vectors are L2-normalized)
        similarity = float(np.dot(probe_embedding, enrolled_embedding))
        similarity = max(0.0, min(1.0, similarity))

        verified = similarity >= VERIFY_THRESHOLD

        logger.info(
            f"Fingerprint verification: user_id={user_id}, "
            f"similarity={similarity:.4f}, threshold={VERIFY_THRESHOLD}, "
            f"verified={verified}"
        )

        return BiometricResponse(
            success=True,
            verified=verified,
            confidence=round(similarity, 4),
            message="Fingerprint verified successfully" if verified else "Fingerprint verification failed",
            user_id=user_id,
        )

    except ValueError as e:
        logger.warning(f"Fingerprint verification validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fingerprint verification failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Fingerprint verification failed: {e}",
        )


# ── DELETE /fingerprint/{user_id} ──────────────────────────────────


@router.delete("/fingerprint/{user_id}", response_model=BiometricResponse)
async def delete_fingerprint(user_id: str) -> BiometricResponse:
    """Soft-delete all fingerprint enrollments for a user."""
    try:
        user_id = user_id.strip()
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        logger.info(f"Fingerprint deletion request: user_id={user_id}")

        repo = get_fingerprint_repository()
        deleted = await repo.delete_by_user_id(user_id)

        if not deleted:
            return BiometricResponse(
                success=True,
                message="No fingerprint enrollment found to delete",
                user_id=user_id,
            )

        logger.info(f"Fingerprint data deleted: user_id={user_id}")

        return BiometricResponse(
            success=True,
            message="Fingerprint data deleted successfully",
            user_id=user_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fingerprint deletion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Fingerprint deletion failed: {e}",
        )
