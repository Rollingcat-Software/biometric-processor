"""Batch processing API routes."""

import json
import logging
from typing import List

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.schemas.batch import (
    BatchEnrollmentItemRequest,
    BatchEnrollmentResponse,
    BatchItemResultResponse,
    BatchVerificationItemRequest,
    BatchVerificationResponse,
)
from app.application.use_cases.batch_process import (
    BatchEnrollmentUseCase,
    BatchVerificationUseCase,
    EnrollmentItem,
    VerificationItem,
)
from app.core.container import (
    get_batch_enrollment_use_case,
    get_batch_verification_use_case,
    get_file_storage,
)
from app.domain.interfaces.file_storage import IFileStorage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/batch", tags=["batch"])


@router.post("/enroll", response_model=BatchEnrollmentResponse)
async def batch_enroll(
    files: List[UploadFile] = File(..., description="Image files for enrollment"),
    items: str = Form(..., description="JSON array of enrollment items"),
    skip_duplicates: bool = Form(True, description="Skip users that already exist"),
    use_case: BatchEnrollmentUseCase = Depends(get_batch_enrollment_use_case),
    storage: IFileStorage = Depends(get_file_storage),
) -> BatchEnrollmentResponse:
    """Batch enroll multiple faces.

    Upload multiple image files along with a JSON array mapping each file
    to its user_id and optional tenant_id.

    Args:
        files: List of image files (must match items array order)
        items: JSON array of BatchEnrollmentItemRequest objects
        skip_duplicates: Whether to skip users that already exist
        use_case: Batch enrollment use case
        storage: File storage service

    Returns:
        BatchEnrollmentResponse with results for each item

    Example items JSON:
        [
            {"user_id": "user1", "tenant_id": "tenant1"},
            {"user_id": "user2", "tenant_id": "tenant1"},
            {"user_id": "user3"}
        ]
    """
    logger.info(f"Batch enrollment request: {len(files)} files")

    # Parse items JSON
    try:
        items_data = json.loads(items)
        item_requests = [BatchEnrollmentItemRequest(**item) for item in items_data]
    except json.JSONDecodeError as e:
        return BatchEnrollmentResponse(
            total_items=0,
            successful=0,
            failed=0,
            skipped=0,
            results=[],
            message=f"Invalid items JSON: {str(e)}",
        )
    except Exception as e:
        return BatchEnrollmentResponse(
            total_items=0,
            successful=0,
            failed=0,
            skipped=0,
            results=[],
            message=f"Invalid items format: {str(e)}",
        )

    # Validate files count matches items count
    if len(files) != len(item_requests):
        return BatchEnrollmentResponse(
            total_items=0,
            successful=0,
            failed=0,
            skipped=0,
            results=[],
            message=f"Files count ({len(files)}) does not match items count ({len(item_requests)})",
        )

    # Save files and create enrollment items
    enrollment_items: List[EnrollmentItem] = []
    temp_paths: List[str] = []

    try:
        for file, item_req in zip(files, item_requests):
            # Save file to temp storage
            temp_path = await storage.save_temp(file)
            temp_paths.append(temp_path)

            enrollment_items.append(
                EnrollmentItem(
                    user_id=item_req.user_id,
                    image_path=temp_path,
                    tenant_id=item_req.tenant_id,
                )
            )

        # Execute batch enrollment
        result = await use_case.execute(
            items=enrollment_items,
            skip_duplicates=skip_duplicates,
        )

        # Convert results to response format
        item_results = [
            BatchItemResultResponse(
                item_id=r.item_id,
                status=r.status.value,
                data=r.data,
                error=r.error,
                error_code=r.error_code,
            )
            for r in result.results
        ]

        return BatchEnrollmentResponse(
            total_items=result.total_items,
            successful=result.successful,
            failed=result.failed,
            skipped=result.skipped,
            results=item_results,
            message=f"Batch enrollment completed: {result.successful} successful, "
            f"{result.failed} failed, {result.skipped} skipped",
        )

    finally:
        # Cleanup temp files
        for temp_path in temp_paths:
            await storage.cleanup(temp_path)


@router.post("/verify", response_model=BatchVerificationResponse)
async def batch_verify(
    files: List[UploadFile] = File(..., description="Image files for verification"),
    items: str = Form(..., description="JSON array of verification items"),
    threshold: float = Form(0.6, ge=0.0, le=2.0, description="Similarity threshold"),
    use_case: BatchVerificationUseCase = Depends(get_batch_verification_use_case),
    storage: IFileStorage = Depends(get_file_storage),
) -> BatchVerificationResponse:
    """Batch verify multiple faces.

    Upload multiple image files along with a JSON array mapping each file
    to its item_id, user_id, and optional tenant_id.

    Args:
        files: List of image files (must match items array order)
        items: JSON array of BatchVerificationItemRequest objects
        threshold: Similarity threshold for matching
        use_case: Batch verification use case
        storage: File storage service

    Returns:
        BatchVerificationResponse with results for each item

    Example items JSON:
        [
            {"item_id": "verify1", "user_id": "user1", "tenant_id": "tenant1"},
            {"item_id": "verify2", "user_id": "user2", "tenant_id": "tenant1"},
            {"item_id": "verify3", "user_id": "user3"}
        ]
    """
    logger.info(f"Batch verification request: {len(files)} files")

    # Parse items JSON
    try:
        items_data = json.loads(items)
        item_requests = [BatchVerificationItemRequest(**item) for item in items_data]
    except json.JSONDecodeError as e:
        return BatchVerificationResponse(
            total_items=0,
            successful=0,
            failed=0,
            results=[],
            message=f"Invalid items JSON: {str(e)}",
        )
    except Exception as e:
        return BatchVerificationResponse(
            total_items=0,
            successful=0,
            failed=0,
            results=[],
            message=f"Invalid items format: {str(e)}",
        )

    # Validate files count matches items count
    if len(files) != len(item_requests):
        return BatchVerificationResponse(
            total_items=0,
            successful=0,
            failed=0,
            results=[],
            message=f"Files count ({len(files)}) does not match items count ({len(item_requests)})",
        )

    # Save files and create verification items
    verification_items: List[VerificationItem] = []
    temp_paths: List[str] = []

    try:
        for file, item_req in zip(files, item_requests):
            # Save file to temp storage
            temp_path = await storage.save_temp(file)
            temp_paths.append(temp_path)

            verification_items.append(
                VerificationItem(
                    item_id=item_req.item_id,
                    user_id=item_req.user_id,
                    image_path=temp_path,
                    tenant_id=item_req.tenant_id,
                )
            )

        # Execute batch verification
        result = await use_case.execute(
            items=verification_items,
            threshold=threshold,
        )

        # Convert results to response format
        item_results = [
            BatchItemResultResponse(
                item_id=r.item_id,
                status=r.status.value,
                data=r.data,
                error=r.error,
                error_code=r.error_code,
            )
            for r in result.results
        ]

        return BatchVerificationResponse(
            total_items=result.total_items,
            successful=result.successful,
            failed=result.failed,
            results=item_results,
            message=f"Batch verification completed: {result.successful} successful, "
            f"{result.failed} failed",
        )

    finally:
        # Cleanup temp files
        for temp_path in temp_paths:
            await storage.cleanup(temp_path)
