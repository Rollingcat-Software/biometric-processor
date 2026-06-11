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

import logging
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.schemas.biometric_response import BiometricResponse as _SharedBiometricResponse
from app.core.container import (
    get_speaker_embedder,
    get_thread_pool,
    get_voice_replay_detector,
    get_voice_repository,
)
from app.core.validation import validate_user_id
from app.infrastructure.ml.voice.replay_detector import compute_spectral_fingerprint
from app.infrastructure.ml.voice.speaker_embedder import compute_voice_quality_score

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Voice"])


def _l2_normalize(vec: np.ndarray) -> np.ndarray:
    """Return ``vec`` scaled to unit L2 norm (zero-norm vectors pass through).

    P1-10: the default enroll path persists the centroid as ``AVG(embedding)``
    (see ``PgVectorVoiceRepository.save``). Averaging unit-norm speaker
    embeddings yields a vector whose norm is **< 1** and shrinks as more
    (slightly divergent) enrollments are accumulated. A raw ``np.dot`` against
    such a centroid is therefore NOT a cosine similarity — it under-reports
    proportionally to ``||centroid||``, so genuine users get false-rejected as
    their enrollment count grows (≈0.71 @2 → ≈0.47 @5 enrollments). Normalising
    both operands to unit length before the dot product makes the result a true
    cosine similarity that is invariant to the number of enrollments, without
    touching the accept threshold.
    """
    norm = float(np.linalg.norm(vec))
    if norm == 0.0:
        return vec
    return vec / norm


# -- Request / Response schemas ------------------------------------------------


class VoiceRequest(BaseModel):
    user_id: str = Field(..., max_length=255)
    voice_data: str = Field(..., max_length=50_000_000)  # ~37MB decoded max
    # Re-enroll & optimize: when True (and the user already has a voiceprint),
    # the new sample is fused into the existing centroid instead of a plain
    # append/average. Optional + default False, so the normal enroll JSON body
    # is unchanged and older callers keep working.
    optimize: bool = Field(False)


class BiometricResponse(_SharedBiometricResponse):
    """Voice-specific biometric response with modality default."""
    modality: str = "voice"


# -- Helpers -------------------------------------------------------------------


async def _extract_voice_embedding(voice_data: str) -> np.ndarray:
    """Extract speaker embedding off the event loop via thread pool."""
    embedder = get_speaker_embedder()
    pool = get_thread_pool()
    return await pool.run_blocking(embedder.extract_embedding_from_base64, voice_data)


async def _compute_replay_fingerprint(voice_data: str) -> np.ndarray:
    """Decode audio and compute the replay spectral fingerprint off the loop."""
    embedder = get_speaker_embedder()
    pool = get_thread_pool()
    samples = await pool.run_blocking(embedder.decode_samples_from_base64, voice_data)
    return await pool.run_blocking(compute_spectral_fingerprint, samples)


async def _compute_voice_quality(voice_data: str) -> float:
    """Decode audio and compute the 0..100 voice quality score off the loop.

    Best-effort: any decode/analysis failure falls back to a neutral 50.0 so a
    quality hiccup never blocks an otherwise-successful enrollment.
    """
    embedder = get_speaker_embedder()
    pool = get_thread_pool()
    try:
        samples = await pool.run_blocking(embedder.decode_samples_from_base64, voice_data)
        return await pool.run_blocking(compute_voice_quality_score, samples)
    except Exception as e:  # noqa: BLE001 — quality scoring must never break enroll
        logger.warning(f"Voice quality scoring skipped (error): {e}")
        return 50.0


async def _run_replay_check(
    voice_data: str,
    user_id: str,
    tenant_id: Optional[str] = None,
) -> bool:
    """Run the voice replay-attack detector (ML-H4).

    Mirrors how the face verify path runs its anti-spoof check: the detector is
    invoked on the verification/search path, is gated by the
    ``VOICE_REPLAY_DETECTION_ENABLED`` config flag (default off), and is
    **advisory + log-only** — a replay suspicion is logged and metered but does
    not block the request. Any failure here must never break voice auth, so all
    errors are swallowed and treated as "not a replay".

    Returns:
        True if the sample is a suspected replay, False otherwise (including
        when detection is disabled or the detector errors out).
    """
    detector = get_voice_replay_detector()
    if not detector.enabled:
        return False
    try:
        fingerprint = await _compute_replay_fingerprint(voice_data)
        return await detector.check_and_record(
            user_id=user_id,
            fingerprint=fingerprint,
            tenant_id=tenant_id,
        )
    except Exception as e:  # noqa: BLE001 — replay check is non-blocking
        logger.warning(f"Voice replay check skipped (error): {e}")
        return False


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

        # Real signal-quality metric (0..100), CPU-only, computed from the
        # decoded audio (duration / loudness / SNR). Replaces the old hardcoded
        # placeholder so the admin Enrollments table + downstream gates see a
        # real number (P1-3).
        quality_score = await _compute_voice_quality(voice_data)

        # Store in database (async I/O -- safe on event loop). The DB column is
        # 0..1, so rescale the 0..100 metric.
        repo = get_voice_repository()
        await repo.save(
            user_id=user_id,
            embedding=embedding,
            quality_score=round(quality_score / 100.0, 4),
            fuse_with_existing=request.optimize,
        )

        logger.info(
            f"Voice enrolled: user_id={user_id}, dim={len(embedding)}, "
            f"quality={quality_score:.1f}, optimize={request.optimize}"
        )

        return BiometricResponse(
            success=True,
            message="Voice enrolled successfully",
            user_id=user_id,
            embedding_dimension=len(embedding),
            # 0..100 — identity-core-api rescales to 0..1 for user_enrollments.
            quality_score=round(quality_score, 2),
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

        # ML-H4: voice replay-attack detection (advisory + log-only, gated by
        # VOICE_REPLAY_DETECTION_ENABLED). Mirrors the face verify path running
        # its anti-spoof check. Never blocks verification today.
        await _run_replay_check(voice_data, user_id=user_id)

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

        # Cosine similarity. P1-10: the stored centroid (default enroll path) is
        # AVG(embedding) and is NOT unit-norm, so a raw dot product decays with
        # enrollment count. L2-normalize BOTH operands here so the result is a
        # true cosine similarity regardless of how many samples were enrolled.
        # (The probe is already unit-norm from the embedder; normalizing it too
        # is a harmless no-op and keeps the path robust to any future change.)
        unit_probe = _l2_normalize(probe_embedding)
        unit_centroid = _l2_normalize(enrolled_embedding)
        similarity = float(np.dot(unit_probe, unit_centroid))
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
    # F10: tenant scoping for 1:N voice identification. Mirrors the face
    # /search ``tenant_id`` parameter ("defense-in-depth isolation"). When
    # supplied the query is scoped to the tenant at the SQL layer so a voice
    # sample can never match enrollments belonging to OTHER tenants. Optional
    # for backward compatibility with callers that have not yet been updated to
    # forward it (see PR notes re: identity-core-api BiometricServiceAdapter).
    tenant_id: Optional[str] = Field(None, max_length=255)


@router.post("/voice/search")
async def search_voice(request: VoiceSearchRequest):
    """Search for a speaker in enrolled database (1:N identification)."""
    SEARCH_THRESHOLD = 0.6

    try:
        voice_data = request.voice_data.strip()
        if not voice_data:
            raise HTTPException(status_code=400, detail="voice_data is required")

        tenant_id = request.tenant_id
        logger.info(f"Voice search request: tenant_id={tenant_id}")

        # CPU-bound extraction offloaded to thread pool
        probe_embedding = await _extract_voice_embedding(voice_data)

        # ML-H4: voice replay-attack detection on the search path (advisory +
        # log-only, gated by VOICE_REPLAY_DETECTION_ENABLED). 1:N search has no
        # claimed user_id, so we key the per-sample fingerprint cache by tenant.
        await _run_replay_check(
            voice_data,
            user_id=f"search:{tenant_id or 'global'}",
            tenant_id=tenant_id,
        )

        # F10: scope the 1:N search to the requesting tenant. The repository
        # adds an ``AND tenant_id = $N`` predicate when tenant_id is provided
        # (same as the face repository), preventing cross-tenant matches.
        repo = get_voice_repository()
        matches = await repo.find_similar(
            probe_embedding,
            threshold=SEARCH_THRESHOLD,
            tenant_id=tenant_id,
        )

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
