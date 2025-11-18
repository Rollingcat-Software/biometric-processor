"""Verification API routes."""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.schemas.verification import VerificationResponse
from app.application.use_cases.verify_face import VerifyFaceUseCase
from app.core.container import get_file_storage, get_verify_face_use_case
from app.domain.interfaces.file_storage import IFileStorage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Verification"])


@router.post("/verify", response_model=VerificationResponse, status_code=200)
async def verify_face(
    user_id: str = Form(..., description="User identifier to verify against"),
    file: UploadFile = File(..., description="Face image file"),
    tenant_id: str = Form(None, description="Optional tenant identifier"),
    use_case: VerifyFaceUseCase = Depends(get_verify_face_use_case),
    storage: IFileStorage = Depends(get_file_storage),
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
        logger.info(f"Verification request: user_id={user_id}, tenant_id={tenant_id}")

        # Validate file type
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Save uploaded file temporarily
        image_path = await storage.save_temp(file)

        # Execute verification use case
        result = await use_case.execute(user_id=user_id, image_path=image_path, tenant_id=tenant_id)

        message = "Face verified successfully" if result.verified else "Face does not match"

        return VerificationResponse(
            verified=result.verified,
            confidence=result.confidence,
            distance=result.distance,
            threshold=result.threshold,
            message=message,
        )

    finally:
        # Cleanup temporary file
        if image_path:
            await storage.cleanup(image_path)
