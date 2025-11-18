"""Liveness check API routes."""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.schemas.liveness import LivenessResponse
from app.application.use_cases.check_liveness import CheckLivenessUseCase
from app.core.container import get_check_liveness_use_case, get_file_storage
from app.domain.interfaces.file_storage import IFileStorage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Liveness"])


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

        # Execute liveness check use case
        result = await use_case.execute(image_path=image_path)

        message = "Liveness check passed" if result.is_live else "Liveness check failed"

        return LivenessResponse(
            is_live=result.is_live,
            liveness_score=result.liveness_score,
            challenge=result.challenge,
            challenge_completed=result.challenge_completed,
            message=message,
        )

    finally:
        # Cleanup temporary file
        if image_path:
            await storage.cleanup(image_path)
