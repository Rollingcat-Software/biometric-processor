"""Voice biometric endpoints — enrollment, verification, deletion.

Uses Resemblyzer for 256-dimensional speaker embeddings with a centroid-based
storage pattern (same as face enrollment). Audio from the browser arrives as
base64-encoded WebM (Opus codec) and is converted to 16 kHz mono WAV for the
embedding model.

Integration:
    Called by identity-core-api BiometricServiceAdapter via JSON:
        POST /voice/enroll  {"user_id": "...", "voice_data": "<base64>"}
        POST /voice/verify  {"user_id": "...", "voice_data": "<base64>"}
        DELETE /voice/{user_id}
"""

import logging
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.container import get_speaker_embedder, get_voice_repository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Voice"])

# ── Request / Response schemas ──────────────────────────────────────


class VoiceRequest(BaseModel):
    user_id: str
    voice_data: str  # base64-encoded audio (WebM/WAV)


class BiometricResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[str] = None
    confidence: Optional[float] = None
    modality: str = "voice"
    implemented: bool = True
    embedding_dimension: Optional[int] = None
    verified: Optional[bool] = None


# ── POST /voice/enroll ──────────────────────────────────────────────


@router.post("/voice/enroll", response_model=BiometricResponse)
async def enroll_voice(request: VoiceRequest) -> BiometricResponse:
    """Enroll a user's voice biometric.

    Accepts base64-encoded audio, extracts a 256-dim speaker embedding via
    Resemblyzer, stores it as an INDIVIDUAL enrollment row, and recomputes
    the CENTROID.
    """
    try:
        user_id = request.user_id.strip()
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        voice_data = request.voice_data.strip()
        if not voice_data:
            raise HTTPException(status_code=400, detail="voice_data is required")

        logger.info(f"Voice enrollment request: user_id={user_id}")

        # Extract speaker embedding
        embedder = get_speaker_embedder()
        embedding = embedder.extract_embedding_from_base64(voice_data)

        # Store in database
        repo = get_voice_repository()
        await repo.save(
            user_id=user_id,
            embedding=embedding,
            quality_score=1.0,  # Voice has no quality metric yet
        )

        logger.info(
            f"Voice enrolled: user_id={user_id}, dim={len(embedding)}"
        )

        return BiometricResponse(
            success=True,
            message="Voice enrolled successfully",
            user_id=user_id,
            embedding_dimension=len(embedding),
        )

    except ValueError as e:
        logger.warning(f"Voice enrollment validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice enrollment failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Voice enrollment failed: {e}",
        )


# ── POST /voice/verify ─────────────────────────────────────────────


@router.post("/voice/verify", response_model=BiometricResponse)
async def verify_voice(request: VoiceRequest) -> BiometricResponse:
    """Verify a user's voice against their enrolled centroid.

    Returns cosine similarity as confidence. Threshold is 0.75 by default.
    """
    VERIFY_THRESHOLD = 0.65

    try:
        user_id = request.user_id.strip()
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        voice_data = request.voice_data.strip()
        if not voice_data:
            raise HTTPException(status_code=400, detail="voice_data is required")

        logger.info(f"Voice verification request: user_id={user_id}")

        # Extract speaker embedding from probe audio
        embedder = get_speaker_embedder()
        probe_embedding = embedder.extract_embedding_from_base64(voice_data)

        # Load enrolled centroid
        repo = get_voice_repository()
        enrolled_embedding = await repo.find_by_user_id(user_id)

        if enrolled_embedding is None:
            return BiometricResponse(
                success=False,
                verified=False,
                message="No voice enrollment found for this user",
                user_id=user_id,
                confidence=0.0,
            )

        # Cosine similarity (both vectors are already L2-normalized)
        similarity = float(np.dot(probe_embedding, enrolled_embedding))
        # Clamp to [0, 1]
        similarity = max(0.0, min(1.0, similarity))

        verified = similarity >= VERIFY_THRESHOLD

        logger.info(
            f"Voice verification: user_id={user_id}, "
            f"similarity={similarity:.4f}, threshold={VERIFY_THRESHOLD}, "
            f"verified={verified}"
        )

        return BiometricResponse(
            success=True,
            verified=verified,
            confidence=round(similarity, 4),
            message="Voice verified successfully" if verified else "Voice verification failed",
            user_id=user_id,
        )

    except ValueError as e:
        logger.warning(f"Voice verification validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice verification failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Voice verification failed: {e}",
        )


# ── POST /voice/search ────────────────────────────────────────────


class VoiceSearchRequest(BaseModel):
    voice_data: str  # base64-encoded audio


@router.post("/voice/search")
async def search_voice(request: VoiceSearchRequest):
    """Search for a speaker in enrolled database (1:N identification)."""
    SEARCH_THRESHOLD = 0.6

    try:
        voice_data = request.voice_data.strip()
        if not voice_data:
            raise HTTPException(status_code=400, detail="voice_data is required")

        logger.info("Voice search request")

        embedder = get_speaker_embedder()
        probe_embedding = embedder.extract_embedding_from_base64(voice_data)

        repo = get_voice_repository()
        matches = await repo.find_similar(probe_embedding, threshold=SEARCH_THRESHOLD)

        logger.info(f"Voice search complete: {len(matches)} matches")

        return {
            "matches": [
                {"user_id": m[0], "similarity": round(1.0 - m[1], 4)}
                for m in matches
            ],
            "total_matches": len(matches),
        }

    except ValueError as e:
        logger.warning(f"Voice search validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Voice search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Voice search failed: {e}")


# ── DELETE /voice/{user_id} ────────────────────────────────────────


@router.delete("/voice/{user_id}", response_model=BiometricResponse)
async def delete_voice(user_id: str) -> BiometricResponse:
    """Soft-delete all voice enrollments for a user."""
    try:
        user_id = user_id.strip()
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        logger.info(f"Voice deletion request: user_id={user_id}")

        repo = get_voice_repository()
        deleted = await repo.delete_by_user_id(user_id)

        if not deleted:
            return BiometricResponse(
                success=True,
                message="No voice enrollment found to delete",
                user_id=user_id,
            )

        logger.info(f"Voice data deleted: user_id={user_id}")

        return BiometricResponse(
            success=True,
            message="Voice data deleted successfully",
            user_id=user_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice deletion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Voice deletion failed: {e}",
        )
