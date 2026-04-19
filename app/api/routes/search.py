"""Search API routes for 1:N face identification."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.schemas.search import SearchMatchResponse, SearchResponse
from app.application.use_cases.search_face import SearchFaceUseCase
from app.core.container import get_file_storage, get_search_face_use_case
from app.core.config import get_settings
from app.core.validation import ValidationError, validate_image_file
from app.domain.interfaces.file_storage import IFileStorage

settings = get_settings()

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Search"])


@router.post("/search", response_model=SearchResponse, status_code=200)
async def search_face(
    file: UploadFile = File(..., description="Face image file"),
    max_results: int = Form(5, ge=1, le=100, description="Maximum results to return"),
    threshold: Optional[float] = Form(None, ge=0.0, le=2.0, description="Distance threshold"),
    tenant_id: str = Form(..., min_length=1, description="Tenant identifier (required for defense-in-depth isolation)"),
    use_case: SearchFaceUseCase = Depends(get_search_face_use_case),
    storage: IFileStorage = Depends(get_file_storage),
) -> SearchResponse:
    """Search for a face across all enrolled users (1:N identification).

    This endpoint:
    1. Validates the uploaded image
    2. Detects face in the image
    3. Extracts face embedding
    4. Searches for similar embeddings
    5. Returns ranked list of matches

    Args:
        file: Face image file (JPEG/PNG)
        max_results: Maximum number of matches to return (1-100)
        threshold: Distance threshold for matching (None = use default 0.6)
        tenant_id: Optional tenant identifier for multi-tenancy
        use_case: Injected search use case
        storage: Injected file storage

    Returns:
        SearchResponse with list of matches

    Raises:
        HTTPException 400: Bad request (no face, multiple faces, invalid image)
        HTTPException 500: Internal server error
    """
    image_path = None

    try:
        logger.info(
            f"Search request: max_results={max_results}, "
            f"threshold={threshold}, tenant_id={tenant_id}"
        )

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

        # Execute search use case
        result = await use_case.execute(
            image_path=image_path,
            max_results=max_results,
            threshold=threshold,
            tenant_id=tenant_id,
        )

        # Build response
        matches = [
            SearchMatchResponse(
                user_id=m.user_id,
                distance=m.distance,
                confidence=m.confidence,
            )
            for m in result.matches
        ]

        best_match = None
        if result.best_match:
            best_match = SearchMatchResponse(
                user_id=result.best_match.user_id,
                distance=result.best_match.distance,
                confidence=result.best_match.confidence,
            )

        message = (
            f"Found {len(matches)} match{'es' if len(matches) != 1 else ''}"
            if result.found
            else "No matches found"
        )

        return SearchResponse(
            found=result.found,
            matches=matches,
            total_searched=result.total_searched,
            threshold=result.threshold,
            best_match=best_match,
            message=message,
        )

    finally:
        # Cleanup temporary file
        if image_path:
            await storage.cleanup(image_path)
