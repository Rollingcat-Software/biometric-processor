"""Facial landmarks API routes."""

from io import BytesIO

import numpy as np
from fastapi import APIRouter, File, Query, UploadFile
from PIL import Image

from app.core.container import get_detect_landmarks_use_case
from app.domain.entities.face_landmarks import LandmarkResultResponse

router = APIRouter(
    prefix="/landmarks",
    tags=["Landmarks"],
)


@router.post(
    "/detect",
    response_model=LandmarkResultResponse,
    summary="Detect facial landmarks",
    description=(
        "Detects detailed facial landmarks (468 points with MediaPipe). "
        "Includes facial regions mapping and head pose estimation."
    ),
)
async def detect_landmarks(
    file: UploadFile = File(...),
    include_3d: bool = Query(
        default=False,
        description="Include 3D coordinates for landmarks",
    ),
) -> LandmarkResultResponse:
    """Detect facial landmarks in image.

    Args:
        file: Uploaded image file
        include_3d: Whether to include 3D coordinates

    Returns:
        LandmarkResultResponse with detected landmarks
    """
    # Read file content
    content = await file.read()

    # Convert to RGB numpy array
    image = Image.open(BytesIO(content)).convert("RGB")
    img_np = np.array(image)

    # Get use case from container
    use_case = get_detect_landmarks_use_case()

    # Execute detection
    result = await use_case.execute(img_np, include_3d=include_3d)

    return LandmarkResultResponse.from_result(result)
