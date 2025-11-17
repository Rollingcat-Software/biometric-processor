"""Enrollment API routes."""

import logging
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException

from app.api.schemas.enrollment import EnrollmentResponse
from app.core.container import get_enroll_face_use_case, get_file_storage
from app.application.use_cases.enroll_face import EnrollFaceUseCase
from app.domain.interfaces.file_storage import IFileStorage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Enrollment"])


@router.post("/enroll", response_model=EnrollmentResponse, status_code=200)
async def enroll_face(
    user_id: str = Form(..., description="User identifier"),
    file: UploadFile = File(..., description="Face image file"),
    tenant_id: str = Form(None, description="Optional tenant identifier"),
    use_case: EnrollFaceUseCase = Depends(get_enroll_face_use_case),
    storage: IFileStorage = Depends(get_file_storage),
) -> EnrollmentResponse:
    """Enroll a user's face.

    This endpoint:
    1. Validates the uploaded image
    2. Detects face in the image
    3. Assesses image quality
    4. Extracts face embedding
    5. Stores embedding in repository

    Args:
        user_id: Unique identifier for the user
        file: Face image file (JPEG/PNG)
        tenant_id: Optional tenant identifier for multi-tenancy
        use_case: Injected enrollment use case
        storage: Injected file storage

    Returns:
        EnrollmentResponse with enrollment result

    Raises:
        HTTPException 400: Bad request (no face, multiple faces, poor quality)
        HTTPException 500: Internal server error
    """
    image_path = None

    try:
        logger.info(f"Enrollment request: user_id={user_id}, tenant_id={tenant_id}")

        # Validate file type
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Save uploaded file temporarily
        image_path = await storage.save_temp(file)

        # Execute enrollment use case
        result = await use_case.execute(
            user_id=user_id, image_path=image_path, tenant_id=tenant_id
        )

        return EnrollmentResponse(
            success=True,
            user_id=result.user_id,
            quality_score=result.quality_score,
            message="Face enrolled successfully",
            embedding_dimension=result.get_embedding_dimension(),
        )

    finally:
        # Cleanup temporary file
        if image_path:
            await storage.cleanup(image_path)
