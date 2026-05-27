"""Verification API routes."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile

from app.api.schemas.verification import VerificationResponse
from app.application.services.device_spoof_risk_evaluator import (
    DeviceSpoofRiskEvaluator,
)
from app.application.use_cases.check_liveness import CheckLivenessUseCase
from app.application.use_cases.verify_face import VerifyFaceUseCase
from app.core.container import (
    get_check_liveness_use_case,
    get_client_embedding_observation_repository,
    get_file_storage,
    get_verify_face_use_case,
)
from app.core.config import get_settings
from app.core.validation import ValidationError, validate_image_file, validate_user_id, validate_tenant_id
from app.domain.exceptions.face_errors import PoorImageQualityError
from app.domain.interfaces.file_storage import IFileStorage
from app.infrastructure.persistence.client_embedding_observation_repository import (
    ClientEmbeddingObservationRepository,
)

settings = get_settings()

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Verification"])


# ---------------------------------------------------------------------------
# Anti-spoof wiring (replaces #85 + #86; algorithms now live in spoof-detector)
# ---------------------------------------------------------------------------
#
# Per architecture decision 2026-05-09: algorithms live in the standalone
# `spoof-detector` repo (gates, fusion, pipeline assembler). This module only
# owns the `/verify` wiring. All flags default OFF — prod behaviour is
# unchanged until an operator opts in.
#
# The imports from `spoof_detector` are wrapped in a try/except so the service
# can still boot if the optional dependency is not installed (e.g. CI lane
# that doesn't install git-URL deps). When unavailable, every flag-gated path
# becomes a no-op and the response fields are `None`.

_device_spoof_risk_evaluator: Optional[DeviceSpoofRiskEvaluator] = None
_antispoof_assembler: Optional[Any] = None  # AntispoofPipelineAssembler when available
_antispoof_assembler_init_failed = False

# Bug 2 (2026-05-12) — single-frame EAR liveness signal. Wires the
# spoof-detector EAR computation into /verify so the closed-eye signal can
# veto a verification. Multi-frame BlinkAnalyzer state (cache + per-face
# history) is out of scope here because /verify only receives one still
# frame; that wiring belongs in the multi-frame /liveness/verify route
# which already runs the puzzle pipeline.
_face_landmarker_for_ear: Optional[Any] = None
_face_landmarker_for_ear_init_failed = False


def _get_device_spoof_risk_evaluator() -> DeviceSpoofRiskEvaluator:
    """Lazy-init singleton — DeviceSpoofRiskEvaluator constructs cv2 detectors
    at import time; we delay until the flag is first observed true."""
    global _device_spoof_risk_evaluator
    if _device_spoof_risk_evaluator is None:
        _device_spoof_risk_evaluator = DeviceSpoofRiskEvaluator()
    return _device_spoof_risk_evaluator


def _evaluate_device_spoof_risk_safe(image_path: str) -> Optional[dict]:
    """Run the device-spoof risk evaluator on an on-disk image.

    Failures here MUST NOT break verification — wrapped in a broad except;
    any exception returns None so the response can still return its primary
    verdict.
    """
    try:
        import cv2  # local to avoid hard import at module load
        frame_bgr = cv2.imread(image_path)
        if frame_bgr is None or frame_bgr.size == 0:
            return None
        evaluator = _get_device_spoof_risk_evaluator()
        assessment = evaluator.evaluate(frame_bgr=frame_bgr)
        return assessment.to_dict()
    except Exception as exc:  # noqa: BLE001
        logger.warning("device_spoof_risk evaluation failed: %s", exc)
        return None


def _get_antispoof_assembler() -> Optional[Any]:
    """Lazy-init the AntispoofPipelineAssembler from spoof_detector.

    Returns None if the optional `spoof-detector` package is not installed.
    Initialisation failures are logged once and cached so we don't spam logs
    on every request.
    """
    global _antispoof_assembler, _antispoof_assembler_init_failed
    if _antispoof_assembler is not None:
        return _antispoof_assembler
    if _antispoof_assembler_init_failed:
        return None
    try:
        from spoof_detector.fusion import HybridFusionEvaluator
        from spoof_detector.gates import FaceUsabilityGate
        from spoof_detector.pipeline import AntispoofPipelineAssembler
    except ImportError as exc:  # pragma: no cover - exercised only when dep missing
        logger.warning(
            "spoof_detector package not importable; AntispoofPipelineAssembler "
            "disabled (cause: %s)",
            exc,
        )
        _antispoof_assembler_init_failed = True
        return None

    try:
        face_gate = (
            FaceUsabilityGate()
            if settings.ANTISPOOF_USABILITY_GATE_ENABLED
            else None
        )
        fuser = (
            HybridFusionEvaluator() if settings.ANTISPOOF_FUSION_ENABLED else None
        )
        device_evaluator = _get_device_spoof_risk_evaluator()
        _antispoof_assembler = AntispoofPipelineAssembler(
            face_usability_gate=face_gate,
            device_spoof_risk_evaluator=device_evaluator,
            hybrid_fusion_evaluator=fuser,
        )
        return _antispoof_assembler
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "AntispoofPipelineAssembler init failed; disabling: %s", exc
        )
        _antispoof_assembler_init_failed = True
        return None


def _get_face_landmarker_for_ear() -> Optional[Any]:
    """Lazy-init a MediaPipe FaceLandmarker for single-frame EAR extraction.

    Returns None if MediaPipe is not importable or the asset isn't present.
    The result is cached so we don't pay model-init cost on every request.
    Failures are recorded so we don't spam logs on every request.
    """
    global _face_landmarker_for_ear, _face_landmarker_for_ear_init_failed
    if _face_landmarker_for_ear is not None:
        return _face_landmarker_for_ear
    if _face_landmarker_for_ear_init_failed:
        return None
    try:
        import os
        from pathlib import Path
        import mediapipe as mp

        # Reuse the same model path the active_liveness_manager loader uses,
        # honouring FACE_LANDMARKER_MODEL_PATH so ops can override per-env.
        default_path = (
            Path(__file__).parent.parent.parent.parent / "models" / "face_landmarker.task"
        )
        model_path = Path(os.getenv("FACE_LANDMARKER_MODEL_PATH", str(default_path)))
        if not model_path.exists():
            logger.info(
                "EAR check disabled — face_landmarker.task not found at %s "
                "(set FACE_LANDMARKER_MODEL_PATH to a deployed asset to enable)",
                model_path,
            )
            _face_landmarker_for_ear_init_failed = True
            return None

        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=0.4,
            min_tracking_confidence=0.4,
        )
        _face_landmarker_for_ear = mp.tasks.vision.FaceLandmarker.create_from_options(
            options
        )
        logger.info("FaceLandmarker initialised for single-frame EAR liveness check")
        return _face_landmarker_for_ear
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "FaceLandmarker init for EAR failed; closed-eye veto disabled: %s",
            exc,
        )
        _face_landmarker_for_ear_init_failed = True
        return None


def _evaluate_ear_liveness_safe(image_path: str) -> Optional[dict]:
    """Run a one-shot Eye Aspect Ratio check on a single still frame.

    Uses the EAR computation from the spoof-detector library (paper-P0
    calibration 2026-05-11: EAR_THRESHOLD=0.18). A frame where BOTH eyes
    are clearly closed is treated as a strong spoof signal — single photos
    of closed eyes are rare in legitimate verification flows, but they
    matter as a defensive complement to texture-based liveness.

    Returns a dict with shape:
        {
            "eyes_closed": bool,
            "left_ear": float,
            "right_ear": float,
            "avg_ear": float,
            "threshold": float,
        }
    or None when the check can't run (no MediaPipe, no model, no face).
    """
    if not settings.ANTISPOOF_EAR_VETO_ENABLED:
        return None
    try:
        import cv2
        import numpy as np
        import mediapipe as mp
        from spoof_detector.infrastructure.analyzers.blink_analyzer import (
            BlinkAnalyzer,
            LEFT_EYE,
            RIGHT_EYE,
            compute_ear,
        )
    except ImportError as exc:  # pragma: no cover - dep missing in CI
        logger.warning("EAR check unavailable; import failed: %s", exc)
        return None
    try:
        landmarker = _get_face_landmarker_for_ear()
        if landmarker is None:
            return None

        frame_bgr = cv2.imread(image_path)
        if frame_bgr is None or frame_bgr.size == 0:
            return None

        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = landmarker.detect(mp_image)
        face_landmarks = result.face_landmarks or []
        if not face_landmarks:
            return None

        # Use the first detected face. The pixel-space conversion matches
        # the spoof-detector blink_analyzer contract.
        lm = np.array(
            [[pt.x * w, pt.y * h, pt.z] for pt in face_landmarks[0]]
        )
        if len(lm) < 468:
            return None

        left = compute_ear(lm, LEFT_EYE)
        right = compute_ear(lm, RIGHT_EYE)
        avg = (left + right) / 2.0
        threshold = BlinkAnalyzer.EAR_THRESHOLD
        return {
            "eyes_closed": bool(avg < threshold),
            "left_ear": round(left, 4),
            "right_ear": round(right, 4),
            "avg_ear": round(avg, 4),
            "threshold": threshold,
        }
    except Exception as exc:  # noqa: BLE001 — fail-soft
        logger.warning("EAR liveness check failed: %s", exc)
        return None


def _merge_block_verdict(
    *,
    antispoof_pipeline: Optional[dict],
    ear_liveness: Optional[dict],
) -> Optional[str]:
    """Conservative veto — any spoof-leaning signal wins.

    Returns a reason category string when verification MUST be blocked, or
    ``None`` when the request is allowed to proceed. The reason category is
    surfaced in the 403 body so callers can branch on it.

    Veto rules (any one triggers a block):
      * ``antispoof_pipeline.recommended_action == "block"``
      * EAR check says ``eyes_closed=True`` (single still frame of closed
        eyes is a strong spoof indicator).
    """
    if antispoof_pipeline is not None:
        action = str(antispoof_pipeline.get("recommended_action", "")).lower()
        if action == "block":
            # Use the most specific reason the assembler attached.
            if antispoof_pipeline.get("face_usability_block"):
                return "FACE_UNUSABLE"
            if antispoof_pipeline.get("hybrid_fusion_is_spoof"):
                return "HYBRID_FUSION_SPOOF"
            return "ANTISPOOF_BLOCK"
    if ear_liveness is not None and ear_liveness.get("eyes_closed") is True:
        return "EYES_CLOSED"
    return None


def _evaluate_antispoof_pipeline_safe(image_path: str) -> Optional[dict]:
    """Run the full anti-spoof assembler on an on-disk image.

    Returns None when:
      - the spoof_detector package isn't installed, or
      - all relevant flags are off, or
      - any exception is raised inside the assembler (fail-soft).
    """
    if not (
        settings.ANTISPOOF_USABILITY_GATE_ENABLED
        or settings.ANTISPOOF_FUSION_ENABLED
        or settings.ANTISPOOF_CUTOUT_ENABLED
    ):
        return None
    assembler = _get_antispoof_assembler()
    if assembler is None:
        return None
    try:
        import cv2
        frame_bgr = cv2.imread(image_path)
        if frame_bgr is None or frame_bgr.size == 0:
            return None
        result = assembler.evaluate(
            frame_bgr=frame_bgr,
            cutout_enabled=settings.ANTISPOOF_CUTOUT_ENABLED,
        )
        return result.to_dict()
    except Exception as exc:  # noqa: BLE001
        logger.warning("antispoof_pipeline evaluation failed: %s", exc)
        return None


@router.post("/verify", response_model=VerificationResponse, status_code=200)
async def verify_face(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: str = Form(..., description="User identifier to verify against"),
    file: UploadFile = File(..., description="Face image file"),
    tenant_id: str = Form(None, description="Optional tenant identifier"),
    client_embedding: Optional[str] = Form(None, description="Optional client-side pre-filter embedding (JSON array, 128-dim, D1 log-only)"),
    client_embeddings: Optional[str] = Form(None, description="Optional client-side embeddings (JSON array-of-arrays, D1 log-only)"),
    client_model_version: Optional[str] = Form(None, description="Optional client model version tag"),
    session_id: Optional[str] = Form(None, description="Optional session identifier"),
    device_platform: Optional[str] = Form(None, description="Optional device platform ('web', 'android', ...)"),
    use_case: VerifyFaceUseCase = Depends(get_verify_face_use_case),
    liveness_use_case: CheckLivenessUseCase = Depends(get_check_liveness_use_case),
    storage: IFileStorage = Depends(get_file_storage),
    observation_repo: ClientEmbeddingObservationRepository = Depends(
        get_client_embedding_observation_repository
    ),
) -> VerificationResponse:
    """Verify a user's face (1:1 matching).

    This endpoint:
    1. Detects face in uploaded image
    2. Extracts face embedding
    3. Retrieves stored embedding for user
    4. Compares embeddings
    5. Returns verification result

    Args:
        user_id: User identifier to verify against
        file: Face image file (JPEG/PNG)
        tenant_id: Optional tenant identifier for multi-tenancy
        use_case: Injected verification use case
        storage: Injected file storage

    Returns:
        VerificationResponse with verification result

    Raises:
        HTTPException 400: Bad request (no face, multiple faces)
        HTTPException 404: User not enrolled
        HTTPException 500: Internal server error
    """
    image_path = None

    try:
        # Validate input parameters for security
        try:
            user_id = validate_user_id(user_id)
            tenant_id = validate_tenant_id(tenant_id)
        except ValidationError as e:
            logger.warning(f"Input validation failed: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")

        logger.info(f"Verification request: user_id={user_id}, tenant_id={tenant_id}")

        # Validate file type
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Save uploaded file temporarily
        image_path = await storage.save_temp(file)

        # SECURITY: Validate actual file type using magic bytes (not just Content-Type header)
        try:
            detected_format = validate_image_file(image_path, allowed_formats=settings.ALLOWED_IMAGE_FORMATS)
            logger.debug(f"File type validated: {detected_format}")
        except ValidationError as e:
            logger.warning(f"File type validation failed: {str(e)}")
            await storage.cleanup(image_path)
            raise HTTPException(status_code=400, detail=str(e))

        # Liveness check — use a slightly more lenient minimum score (0.4) for
        # verification vs enrollment (default threshold 0.5).  The use case uses
        # LIVENESS_THRESHOLD from settings for the is_live decision, so we only
        # add a floor here: if the score is below 0.4 we reject even if
        # is_live happened to be True (e.g. a very marginal borderline case).
        VERIFY_MIN_LIVENESS_SCORE = 0.4
        liveness_result = await liveness_use_case.execute(image_path=image_path)
        if not liveness_result.is_live or liveness_result.score < VERIFY_MIN_LIVENESS_SCORE:
            logger.warning(
                f"Verification rejected — liveness check failed: "
                f"user_id={user_id}, is_live={liveness_result.is_live}, "
                f"score={liveness_result.score:.2f}"
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "error_code": "LIVENESS_FAILED",
                    "message": "Liveness check failed",
                    "score": liveness_result.score,
                },
            )

        # Execute verification use case
        try:
            result = await use_case.execute(user_id=user_id, image_path=image_path, tenant_id=tenant_id)
        except PoorImageQualityError as e:
            logger.warning(f"Verification rejected due to poor image quality: {e.message}")
            return VerificationResponse(
                verified=False,
                confidence=0.0,
                distance=1.0,
                threshold=0.0,
                message=f"Image quality too low for verification (score: {e.quality_score:.0f}/100). "
                "Please ensure good lighting and face the camera directly.",
            )

        message = "Face verified successfully" if result.verified else "Face does not match"

        # Anti-spoof attachments. Both fields default None and are populated
        # only when their respective flags are on. The helpers swallow any
        # exception — they never block verification by raising.
        device_spoof_risk: Optional[dict] = None
        if settings.ANTISPOOF_DEVICE_RISK_ENABLED:
            device_spoof_risk = _evaluate_device_spoof_risk_safe(image_path)
        antispoof_pipeline = _evaluate_antispoof_pipeline_safe(image_path)
        ear_liveness = _evaluate_ear_liveness_safe(image_path)

        # Bug 1 (2026-05-12) — enforce assembler's `recommended_action="block"`
        # and the EAR single-frame closed-eye signal. Previously the assembler
        # verdict was advisory: a "block" recommendation was attached to the
        # response but the route still returned `verified=true`. With
        # ANTISPOOF_BLOCK_ENFORCE=true (the default) we now return 403 with
        # a structured body. An operator can flip the flag to false for
        # observation-only / canary rollout.
        block_reason = _merge_block_verdict(
            antispoof_pipeline=antispoof_pipeline,
            ear_liveness=ear_liveness,
        )
        if block_reason is not None and settings.ANTISPOOF_BLOCK_ENFORCE:
            logger.warning(
                "Verification BLOCKED by anti-spoof veto: user_id=%s reason=%s "
                "assembler_action=%s ear_avg=%s",
                user_id,
                block_reason,
                (antispoof_pipeline or {}).get("recommended_action"),
                (ear_liveness or {}).get("avg_ear"),
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "error_code": "ANTISPOOF_BLOCKED",
                    "reason": block_reason,
                    "antispoof_pipeline": antispoof_pipeline,
                    "ear_liveness": ear_liveness,
                    "message": "Verification rejected by anti-spoof checks",
                },
            )
        if block_reason is not None:
            # Enforcement disabled: log the bypass loudly so it's visible in
            # production log streams when an operator runs in observation mode.
            logger.warning(
                "Verification anti-spoof veto SUPPRESSED (ANTISPOOF_BLOCK_ENFORCE=false): "
                "user_id=%s reason=%s",
                user_id,
                block_reason,
            )

        response = VerificationResponse(
            verified=result.verified,
            confidence=result.confidence,
            distance=result.distance,
            threshold=result.threshold,
            message=message,
            device_spoof_risk=device_spoof_risk,
            antispoof_pipeline=antispoof_pipeline,
            ear_liveness=ear_liveness,
        )

        # D1 log-only: persist client pre-filter embedding for offline analysis.
        # Must never affect primary flow — scheduled via BackgroundTasks.
        _observation_embedding = _pick_single_client_embedding(
            client_embedding, client_embeddings
        )
        background_tasks.add_task(
            observation_repo.record,
            user_id=user_id,
            tenant_id=tenant_id,
            session_id=session_id,
            modality="face",
            flow="verify",
            client_embedding_json=_observation_embedding,
            client_model_version=client_model_version,
            server_embedding_ref=None,
            device_platform=device_platform,
            user_agent=request.headers.get("user-agent"),
        )

        return response

    finally:
        # Cleanup temporary file
        if image_path:
            await storage.cleanup(image_path)


def _pick_single_client_embedding(
    client_embedding: Optional[str],
    client_embeddings: Optional[str],
) -> Optional[str]:
    """Pick a single JSON-encoded embedding to log.

    Prefers the single `client_embedding` field; otherwise the first entry
    of `client_embeddings` (array-of-arrays). Returns a JSON-encoded string
    or None. Never raises.
    """
    if client_embedding:
        return client_embedding
    if not client_embeddings:
        return None
    try:
        import json as _json
        parsed = _json.loads(client_embeddings)
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], list):
            return _json.dumps(parsed[0])
    except Exception:
        return None
    return None
