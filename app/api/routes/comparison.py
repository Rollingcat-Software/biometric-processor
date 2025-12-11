"""Face comparison API routes."""

from io import BytesIO
from typing import Optional

import numpy as np
from fastapi import APIRouter, File, Query, UploadFile
from PIL import Image

from app.core.container import get_compare_faces_use_case
from app.domain.entities.face_comparison import FaceComparisonResponse

router = APIRouter(
    prefix="/compare",
    tags=["Comparison"],
)


@router.post(
    "",
    response_model=FaceComparisonResponse,
    summary="Compare two face images",
    description=(
        "Compares two face images directly without enrollment. "
        "Returns similarity score and match determination."
    ),
)
async def compare_faces(
    file1: UploadFile = File(..., description="First face image"),
    file2: UploadFile = File(..., description="Second face image"),
    threshold: Optional[float] = Query(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Similarity threshold for match determination",
    ),
) -> FaceComparisonResponse:
    """Compare two face images.

    Args:
        file1: First face image
        file2: Second face image
        threshold: Similarity threshold for match

    Returns:
        FaceComparisonResponse with comparison results
    """
    # Read file contents
    content1 = await file1.read()
    content2 = await file2.read()

    # Convert to RGB numpy arrays
    image1 = Image.open(BytesIO(content1)).convert("RGB")
    image2 = Image.open(BytesIO(content2)).convert("RGB")

    img_np1 = np.array(image1)
    img_np2 = np.array(image2)

    # Get use case from container
    use_case = get_compare_faces_use_case()

    # Execute comparison
    result = await use_case.execute(img_np1, img_np2, threshold=threshold)

    return FaceComparisonResponse.from_result(result)
