"""Liveness check API routes."""

import logging
import time

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.schemas.liveness import LivenessCheck, LivenessResponse
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
    start_time = time.perf_counter()

    try:
        logger.info("Liveness check request")

        # Validate file type
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Save uploaded file temporarily
        image_path = await storage.save_temp(file)

        # Execute liveness check use case
        result = await use_case.execute(image_path=image_path)

        # Calculate processing time
        processing_time_ms = (time.perf_counter() - start_time) * 1000

        # Build message based on result
        if result.is_live:
            message = "Liveness check passed - live person detected"
        elif result.spoof_type:
            spoof_messages = {
                "screen_replay": "Screen replay attack detected",
                "printed_photo": "Printed photo detected",
                "digital_manipulation": "Digital manipulation detected",
                "static_image": "Static image detected - no natural features",
                "suspected_spoof": "Suspected spoof attempt",
            }
            message = f"Liveness check failed - {spoof_messages.get(result.spoof_type, 'Spoof detected')}"
        else:
            message = "Liveness check failed"

        # Convert domain checks to API checks
        api_checks = [
            LivenessCheck(
                name=check.name,
                passed=check.passed,
                score=check.score,
                details=check.details,
            )
            for check in result.checks
        ]

        return LivenessResponse(
            is_live=result.is_live,
            liveness_score=result.liveness_score,
            challenge=result.challenge,
            challenge_completed=result.challenge_completed,
            message=message,
            checks=api_checks,
            spoof_type=result.spoof_type,
            processing_time_ms=processing_time_ms,
        )

    finally:
        # Cleanup temporary file
        if image_path:
            await storage.cleanup(image_path)
