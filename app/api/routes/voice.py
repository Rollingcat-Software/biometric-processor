"""Voice biometric endpoints -- enrollment, verification, deletion.

Uses Resemblyzer for 256-dimensional speaker embeddings with a centroid-based
storage pattern (same as face enrollment). Audio from the browser arrives as
base64-encoded WebM (Opus codec) and is converted to 16 kHz mono WAV for the
embedding model.

CPU-bound embedding extraction is offloaded to the shared thread pool via
``run_in_executor`` so the FastAPI event loop is never blocked.

Integration:
    Called by identity-core-api BiometricServiceAdapter via JSON:
        POST /voice/enroll  {"user_id": "...", "voice_data": "<base64>"}
        POST /voice/verify  {"user_id": "...", "voice_data": "<base64>"}
        DELETE /voice/{user_id}
"""

import asyncio
import logging
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.schemas.biometric_response import BiometricResponse as _SharedBiometricResponse
from app.core.container import get_speaker_embedder, get_voice_repository, get_thread_pool
from app.core.validation import validate_user_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Voice"])

# -- Request / Response schemas ------------------------------------------------


class VoiceRequest(BaseModel):
    user_id: str = Field(..., max_length=255)
    voice_data: str = Field(..., max_length=50_000_000)  # ~37MB decoded max


class BiometricResponse(_SharedBiometricResponse):
    """Voice-specific biometric response with modality default."""
    modality: str = "voice"


# -- Helpers -------------------------------------------------------------------


async def _extract_voice_embedding(voice_data: str) -> np.ndarray:
    """Extract speaker embedding off the event loop via thread pool."""
    embedder = get_speaker_embedder()
    pool = get_thread_pool()
    return await pool.run_blocking(embedder.extract_embedding_from_base64, voice_data)


# -- POST /voice/enroll --------------------------------------------------------


@router.post("/voice/enroll", response_model=BiometricResponse)
async def enroll_voice(request: VoiceRequest) -> BiometricResponse:
    """Enroll a user's voice biometric.

    Accepts base64-encoded audio, extracts a 256-dim speaker embedding via
    Resemblyzer, stores it as an INDIVIDUAL enrollment row, and recomputes
    the CENTROID.  Re-enrolling the same user adds a new sample and updates
    the centroid (idempotent accumulation).
    """
    try:
        user_id = validate_user_id(request.user_id)

        voice_data = request.voice_data.strip()
        if not voice_data:
            raise HTTPException(status_code=400, detail="voice_data is required")

        logger.info(f"Voice enrollment request: user_id={user_id}")

        # Extract speaker embedding (CPU-bound -- offloaded to thread pool)
        embedding = await _extract_voice_embedding(voice_data)

        # Store in database (async I/O -- safe on event loop)
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
            detail="Voice enrollment failed. Please try again.",
        )


# -- POST /voice/verify -------------------------------------------------------


@router.post("/voice/verify", response_model=BiometricResponse)
async def verify_voice(request: VoiceRequest) -> BiometricResponse:
    """Verify a user's voice against their enrolled centroid.

    Returns cosine similarity as confidence. Threshold is 0.65.
    """
    VERIFY_THRESHOLD = 0.65

    try:
        user_id = validate_user_id(request.user_id)

        voice_data = request.voice_data.strip()
        if not voice_data:
            raise HTTPException(status_code=400, detail="voice_data is required")

        logger.info(f"Voice verification request: user_id={user_id}")

        # Extract speaker embedding from probe audio (CPU-bound)
        probe_embedding = await _extract_voice_embedding(voice_data)

        # Load enrolled centroid (async I/O)
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
            detail="Voice verification failed. Please try again.",
        )


# -- POST /voice/search -------------------------------------------------------


class VoiceSearchRequest(BaseModel):
    voice_data: str = Field(..., max_length=50_000_000)  # base64-encoded audio


@router.post("/voice/search")
async def search_voice(request: VoiceSearchRequest):
    """Search for a speaker in enrolled database (1:N identification)."""
    SEARCH_THRESHOLD = 0.6

    try:
        voice_data = request.voice_data.strip()
        if not voice_data:
            raise HTTPException(status_code=400, detail="voice_data is required")

        logger.info("Voice search request")

        # CPU-bound extraction offloaded to thread pool
        probe_embedding = await _extract_voice_embedding(voice_data)

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
        raise HTTPException(status_code=500, detail="Voice search failed. Please try again.")


# -- DELETE /voice/{user_id} ---------------------------------------------------


@router.delete("/voice/{user_id}", response_model=BiometricResponse)
async def delete_voice(user_id: str) -> BiometricResponse:
    """Soft-delete all voice enrollments for a user."""
    try:
        user_id = validate_user_id(user_id)

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

    except ValueError as e:
        logger.warning(f"Voice deletion validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice deletion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Voice deletion failed. Please try again.",
        )
