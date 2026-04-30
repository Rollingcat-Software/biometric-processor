"""Liveness check API routes."""

import logging

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, Response, UploadFile

from app.api.schemas.active_liveness import ActiveLivenessResponse, ActiveLivenessStartRequest
from app.api.schemas.gesture_liveness import (
    GestureFramePayload,
    GestureSessionStartRequest,
    ShapeTemplateCatalog,
)
from app.api.schemas.liveness import LivenessResponse
from app.application.services.active_gesture_liveness_manager import (
    load_shape_template_catalog,
)
from app.application.use_cases.process_active_gesture_liveness_frame import (
    ActiveLivenessSessionExpiredError as GestureSessionExpiredError,
    ActiveLivenessSessionNotFoundError as GestureSessionNotFoundError,
    InvalidModalityError as GestureInvalidModalityError,
    ProcessActiveGestureLivenessFrameUseCase,
)
from app.application.use_cases.process_active_liveness_frame import (
    ActiveLivenessSessionExpiredError,
    ActiveLivenessSessionNotFoundError,
    ProcessActiveLivenessFrameUseCase,
)
from app.application.use_cases.start_active_gesture_liveness import (
    StartActiveGestureLivenessUseCase,
)
from app.application.use_cases.start_active_liveness import StartActiveLivenessUseCase
from app.application.use_cases.check_liveness import CheckLivenessUseCase
from app.core.container import (
    get_check_liveness_use_case,
    get_file_storage,
    get_process_active_gesture_liveness_frame_use_case,
    get_process_active_liveness_frame_use_case,
    get_start_active_gesture_liveness_use_case,
    get_start_active_liveness_use_case,
)
from app.core.config import get_settings
from app.core.validation import ValidationError, validate_image_file
from app.domain.interfaces.file_storage import IFileStorage

settings = get_settings()

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Liveness"])


def _ensure_gesture_feature_enabled() -> None:
    """Return 404 (not 403) if the feature flag is off.

    A 404 keeps the route indistinguishable from an unimplemented one so
    a disabled feature does not leak its own existence to callers.
    """

    if not settings.ACTIVE_GESTURE_LIVENESS_ENABLED:
        raise HTTPException(status_code=404, detail="Not Found")


@router.post("/liveness", response_model=LivenessResponse, status_code=200)
async def check_liveness(
    file: UploadFile = File(..., description="Face image file"),
    use_case: CheckLivenessUseCase = Depends(get_check_liveness_use_case),
    storage: IFileStorage = Depends(get_file_storage),
) -> LivenessResponse:
    """Check liveness of a face.

    This endpoint:
    1. Detects face in image
    2. Performs liveness check
    3. Returns liveness result

    Args:
        file: Face image file (JPEG/PNG)
        use_case: Injected liveness check use case
        storage: Injected file storage

    Returns:
        LivenessResponse with liveness check result

    Raises:
        HTTPException 400: Bad request (no face, multiple faces)
        HTTPException 500: Internal server error

    Note:
        Currently uses stub liveness detector.
        Will be updated in Sprint 3 with real smile/blink detection.
    """
    image_path = None

    try:
        logger.info("Liveness check request")

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

        # Execute liveness check use case
        result = await use_case.execute(image_path=image_path)

        message = "Liveness check passed" if result.is_live else "Liveness check failed"

        return LivenessResponse(
            is_live=result.is_live,
            score=result.score,
            confidence=result.confidence,
            challenge=result.challenge,
            challenge_completed=result.challenge_completed,
            message=message,
        )

    finally:
        # Cleanup temporary file
        if image_path:
            await storage.cleanup(image_path)


@router.post("/liveness/active/start", response_model=ActiveLivenessResponse, status_code=200)
async def start_active_liveness(
    request: ActiveLivenessStartRequest | None = Body(default=None),
    use_case: StartActiveLivenessUseCase = Depends(get_start_active_liveness_use_case),
) -> ActiveLivenessResponse:
    """Start a new active liveness session."""

    return await use_case.execute(config=request)


@router.post("/liveness/active/frame", response_model=ActiveLivenessResponse, status_code=200)
async def process_active_liveness_frame(
    session_id: str = Form(..., description="Active liveness session ID"),
    frame_timestamp: float = Form(..., description="Client frame capture time as Unix seconds or milliseconds"),
    image: UploadFile = File(..., description="Frame image file"),
    use_case: ProcessActiveLivenessFrameUseCase = Depends(get_process_active_liveness_frame_use_case),
    storage: IFileStorage = Depends(get_file_storage),
) -> ActiveLivenessResponse:
    """Process a frame for an existing active liveness session."""

    image_path = None
    try:
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        image_path = await storage.save_temp(image)

        try:
            validate_image_file(image_path, allowed_formats=settings.ALLOWED_IMAGE_FORMATS)
        except ValidationError as exc:
            await storage.cleanup(image_path)
            raise HTTPException(status_code=400, detail=str(exc))

        return await use_case.execute(
            session_id=session_id,
            image_path=image_path,
            frame_timestamp=frame_timestamp,
        )
    except ActiveLivenessSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ActiveLivenessSessionExpiredError as exc:
        raise HTTPException(status_code=410, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        if image_path:
            await storage.cleanup(image_path)


# ============================================================================
# Active Gesture Liveness (Phase 1, 2026-04-24)
# ============================================================================
# Server-side gesture liveness accepts landmarks + anti-spoof scores as JSON
# (no raw image upload, no server MediaPipe). Feature-gated by
# ACTIVE_GESTURE_LIVENESS_ENABLED; disabled routes return 404.


@router.post(
    "/liveness/active/gesture/start",
    response_model=ActiveLivenessResponse,
    status_code=200,
    summary="Start an active gesture liveness session (landmarks-only).",
)
async def start_active_gesture_liveness(
    request: GestureSessionStartRequest | None = Body(default=None),
) -> ActiveLivenessResponse:
    _ensure_gesture_feature_enabled()
    use_case: StartActiveGestureLivenessUseCase = (
        get_start_active_gesture_liveness_use_case()
    )
    return await use_case.execute(config=request)


@router.post(
    "/liveness/active/gesture/frame",
    response_model=ActiveLivenessResponse,
    status_code=200,
    summary="Submit a gesture frame (client-extracted hand landmarks + anti-spoof scores).",
)
async def process_active_gesture_liveness_frame(
    session_id: str = Body(..., description="Active gesture liveness session ID"),
    payload: GestureFramePayload = Body(..., description="Landmarks + anti-spoof telemetry"),
) -> ActiveLivenessResponse:
    _ensure_gesture_feature_enabled()
    use_case: ProcessActiveGestureLivenessFrameUseCase = (
        get_process_active_gesture_liveness_frame_use_case()
    )
    try:
        return await use_case.execute(session_id=session_id, payload=payload)
    except GestureSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except GestureInvalidModalityError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except GestureSessionExpiredError as exc:
        raise HTTPException(status_code=410, detail=str(exc))


@router.get(
    "/liveness/active/gesture/shape-templates",
    response_model=ShapeTemplateCatalog,
    status_code=200,
    summary="Fetch the shape-template catalog used for SHAPE_TRACE challenges.",
)
async def get_gesture_shape_templates(
    request: Request,
    response: Response,
) -> ShapeTemplateCatalog | Response:
    _ensure_gesture_feature_enabled()
    catalog = load_shape_template_catalog()
    etag = f'W/"{catalog.version}"'
    client_etag = request.headers.get("if-none-match")
    if client_etag and client_etag == etag:
        # 304 Not Modified keeps this endpoint cheap for repeat callers.
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "max-age=300"})
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "max-age=300"
    return catalog
