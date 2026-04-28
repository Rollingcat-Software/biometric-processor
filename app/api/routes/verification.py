"""Verification API routes."""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile

from app.api.schemas.verification import VerificationResponse
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

        response = VerificationResponse(
            verified=result.verified,
            confidence=result.confidence,
            distance=result.distance,
            threshold=result.threshold,
            message=message,
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
