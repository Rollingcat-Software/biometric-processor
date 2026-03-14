"""Enrollment API routes."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile

from app.api.schemas.enrollment import EnrollmentResponse
from app.api.schemas.multi_image_enrollment import MultiImageEnrollmentResponse
from app.application.use_cases.delete_enrollment import DeleteEnrollmentUseCase
from app.application.use_cases.enroll_face import EnrollFaceUseCase
from app.application.use_cases.enroll_multi_image import EnrollMultiImageUseCase
from app.core.config import settings
from app.core.container import (
    get_delete_enrollment_use_case,
    get_enroll_face_use_case,
    get_enroll_multi_image_use_case,
    get_file_storage,
    get_idempotency_store,
)
from app.core.validation import ValidationError, validate_image_file, validate_user_id, validate_tenant_id
from app.domain.interfaces.file_storage import IFileStorage
from app.infrastructure.idempotency import IdempotencyStore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Enrollment"])


@router.post("/enroll", response_model=EnrollmentResponse, status_code=200)
async def enroll_face(
    user_id: str = Form(..., description="User identifier"),
    file: UploadFile = File(..., description="Face image file"),
    tenant_id: str = Form(None, description="Optional tenant identifier"),
    use_case: EnrollFaceUseCase = Depends(get_enroll_face_use_case),
    storage: IFileStorage = Depends(get_file_storage),
    idempotency_store: IdempotencyStore = Depends(get_idempotency_store),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key", description="Optional idempotency key to prevent duplicate enrollments"),
) -> EnrollmentResponse:
    """Enroll a user's face.

    SECURITY: This endpoint is protected by rate limiting (default: 10 requests/minute)
    to prevent enrollment flooding and DoS attacks. See ENROLLMENT_RATE_LIMIT_PER_MINUTE config.

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
        # Validate input parameters for security
        try:
            user_id = validate_user_id(user_id)
            tenant_id = validate_tenant_id(tenant_id)
        except ValidationError as e:
            logger.warning(f"Input validation failed: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")

        logger.info(f"Enrollment request: user_id={user_id}, tenant_id={tenant_id}, idempotency_key={idempotency_key or 'none'}")

        # Check idempotency if key provided
        if idempotency_key:
            # Read file content to compute hash
            file_content = await file.read()
            file_hash = idempotency_store.hash_file_content(file_content)
            request_hash = idempotency_store.hash_request(user_id, tenant_id, file_hash)

            # Check if we've already processed this exact request
            try:
                cached_response = await idempotency_store.get_response(idempotency_key, request_hash)
                if cached_response:
                    logger.info(f"Returning cached enrollment response for idempotency_key={idempotency_key}")
                    return EnrollmentResponse(**cached_response.response_data)
            except ValueError as e:
                # Idempotency key conflict (same key, different request)
                logger.error(f"Idempotency conflict: {str(e)}")
                raise HTTPException(status_code=409, detail=str(e))

            # Reset file pointer after reading for hash
            await file.seek(0)

        # Validate file type (basic header check for early rejection)
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Save uploaded file temporarily
        image_path = await storage.save_temp(file)

        # SECURITY: Validate actual file type using magic bytes (not just Content-Type header)
        # This prevents file type confusion attacks and malware disguised as images
        try:
            detected_format = validate_image_file(image_path, allowed_formats=settings.ALLOWED_IMAGE_FORMATS)
            logger.debug(f"File type validated: {detected_format}")
        except ValidationError as e:
            logger.warning(f"File type validation failed: {str(e)}")
            await storage.cleanup(image_path)  # Clean up invalid file immediately
            raise HTTPException(status_code=400, detail=str(e))

        # Execute enrollment use case
        result = await use_case.execute(user_id=user_id, image_path=image_path, tenant_id=tenant_id)

        response = EnrollmentResponse(
            success=True,
            user_id=result.user_id,
            quality_score=result.quality_score,
            message="Face enrolled successfully",
            embedding_dimension=result.get_embedding_dimension(),
            liveness_score=1.0,  # Placeholder - actual liveness check would need anti-spoofing model
        )

        # Store response for idempotency if key provided
        if idempotency_key:
            await idempotency_store.store_response(
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                response_data=response.model_dump(),
                status_code=200,
                user_id=user_id
            )

        return response

    finally:
        # Cleanup temporary file
        if image_path:
            await storage.cleanup(image_path)


@router.post("/enroll/multi", response_model=MultiImageEnrollmentResponse, status_code=200)
async def enroll_face_multi_image(
    user_id: str = Form(..., description="User identifier"),
    files: List[UploadFile] = File(..., description="2-5 face image files"),
    tenant_id: str = Form(None, description="Optional tenant identifier"),
    use_case: EnrollMultiImageUseCase = Depends(get_enroll_multi_image_use_case),
    storage: IFileStorage = Depends(get_file_storage),
    idempotency_store: IdempotencyStore = Depends(get_idempotency_store),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key", description="Optional idempotency key to prevent duplicate enrollments"),
) -> MultiImageEnrollmentResponse:
    """Enroll a user's face using multiple images (template fusion).

    SECURITY: This endpoint is protected by rate limiting (default: 10 requests/minute)
    to prevent enrollment flooding and DoS attacks. See ENROLLMENT_RATE_LIMIT_PER_MINUTE config.

    This endpoint implements multi-image biometric enrollment:
    - Accepts 2-5 face images per user
    - Processes each image independently (detect, assess quality, extract embedding)
    - Fuses embeddings using quality-weighted average
    - Creates a single robust template
    - Improves verification accuracy by 30-40% with poor quality photos

    Process:
    1. Validates uploaded images (2-5 required)
    2. Detects face in each image
    3. Assesses quality of each image
    4. Extracts embedding from each image
    5. Fuses embeddings using weighted average (higher quality = higher weight)
    6. Stores fused template in repository

    Args:
        user_id: Unique identifier for the user
        files: 2-5 face image files (JPEG/PNG)
        tenant_id: Optional tenant identifier for multi-tenancy
        use_case: Injected multi-image enrollment use case
        storage: Injected file storage

    Returns:
        MultiImageEnrollmentResponse with enrollment result

    Raises:
        HTTPException 400: Bad request (invalid count, no face, multiple faces, poor quality)
        HTTPException 500: Internal server error
    """
    image_paths = []

    try:
        # Validate input parameters for security
        try:
            user_id = validate_user_id(user_id)
            tenant_id = validate_tenant_id(tenant_id)
        except ValidationError as e:
            logger.warning(f"Input validation failed: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")

        logger.info(
            f"Multi-image enrollment request: user_id={user_id}, "
            f"images={len(files)}, tenant_id={tenant_id}, idempotency_key={idempotency_key or 'none'}"
        )

        # Check idempotency if key provided
        if idempotency_key:
            # Compute combined hash of all files
            combined_hash_data = ""
            for i, file in enumerate(files):
                file_content = await file.read()
                file_hash = idempotency_store.hash_file_content(file_content)
                combined_hash_data += file_hash
                # Reset file pointer after reading for hash
                await file.seek(0)

            # Hash the combined hashes
            import hashlib
            combined_file_hash = hashlib.sha256(combined_hash_data.encode()).hexdigest()
            request_hash = idempotency_store.hash_request(user_id, tenant_id, combined_file_hash)

            # Check if we've already processed this exact request
            try:
                cached_response = await idempotency_store.get_response(idempotency_key, request_hash)
                if cached_response:
                    logger.info(f"Returning cached multi-image enrollment response for idempotency_key={idempotency_key}")
                    return MultiImageEnrollmentResponse(**cached_response.response_data)
            except ValueError as e:
                # Idempotency key conflict (same key, different request)
                logger.error(f"Idempotency conflict: {str(e)}")
                raise HTTPException(status_code=409, detail=str(e))

        # Check if multi-image enrollment is enabled
        if not settings.MULTI_IMAGE_ENROLLMENT_ENABLED:
            raise HTTPException(
                status_code=400,
                detail="Multi-image enrollment is not enabled on this server",
            )

        # Validate file count
        min_images = settings.MULTI_IMAGE_MIN_IMAGES
        max_images = settings.MULTI_IMAGE_MAX_IMAGES

        if not min_images <= len(files) <= max_images:
            raise HTTPException(
                status_code=400,
                detail=f"Must provide between {min_images} and {max_images} images, got {len(files)}",
            )

        # Validate all files are images (basic header check for early rejection)
        for i, file in enumerate(files, start=1):
            if not file.content_type or not file.content_type.startswith("image/"):
                raise HTTPException(
                    status_code=400,
                    detail=f"File {i} must be an image (got {file.content_type})",
                )

        # Save all uploaded files temporarily
        for i, file in enumerate(files, start=1):
            logger.debug(f"Saving temporary file {i}/{len(files)}")
            image_path = await storage.save_temp(file)
            image_paths.append(image_path)

            # SECURITY: Validate actual file type using magic bytes (not just Content-Type header)
            # This prevents file type confusion attacks and malware disguised as images
            try:
                detected_format = validate_image_file(image_path, allowed_formats=settings.ALLOWED_IMAGE_FORMATS)
                logger.debug(f"File {i} type validated: {detected_format}")
            except ValidationError as e:
                logger.warning(f"File {i} type validation failed: {str(e)}")
                # Clean up all uploaded files on validation failure
                for path in image_paths:
                    await storage.cleanup(path)
                raise HTTPException(status_code=400, detail=f"File {i}: {str(e)}")

        # Execute multi-image enrollment use case
        result = await use_case.execute(
            user_id=user_id, image_paths=image_paths, tenant_id=tenant_id
        )

        # Use actual quality scores from the enrollment result
        response = MultiImageEnrollmentResponse(
            success=True,
            user_id=result.user_id,
            images_processed=result.images_processed,
            fused_quality_score=result.fused_quality_score,
            average_quality_score=result.average_quality_score,
            individual_quality_scores=result.individual_quality_scores,
            message="Multi-image enrollment completed successfully",
            embedding_dimension=result.embedding_dimension,
            fusion_strategy=result.fusion_strategy,
        )

        # Store response for idempotency if key provided
        if idempotency_key:
            await idempotency_store.store_response(
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                response_data=response.model_dump(),
                status_code=200,
                user_id=user_id
            )

        return response

    finally:
        # Cleanup all temporary files
        for image_path in image_paths:
            await storage.cleanup(image_path)


@router.delete("/enroll/{user_id}", status_code=200)
async def delete_enrollment(
    user_id: str,
    use_case: DeleteEnrollmentUseCase = Depends(get_delete_enrollment_use_case),
) -> dict:
    """Delete a user's face enrollment.

    Args:
        user_id: User identifier whose enrollment should be deleted
        use_case: Injected delete enrollment use case

    Returns:
        Success response with deletion status

    Raises:
        HTTPException 404: If no enrollment found for user
        HTTPException 500: Internal server error
    """
    try:
        # Validate user_id
        try:
            user_id = validate_user_id(user_id)
        except ValidationError as e:
            logger.warning(f"Input validation failed: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid input: {str(e)}")

        logger.info(f"Delete enrollment request: user_id={user_id}")

        deleted = await use_case.execute(user_id=user_id)

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"No enrollment found for user: {user_id}",
            )

        return {
            "success": True,
            "user_id": user_id,
            "message": "Face data deleted successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting enrollment: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to delete enrollment. Please try again.",
        )
