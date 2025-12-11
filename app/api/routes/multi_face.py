"""Multi-face detection API routes."""

from io import BytesIO
from typing import Optional

import numpy as np
from fastapi import APIRouter, File, Query, UploadFile
from PIL import Image

from app.core.container import get_detect_multi_face_use_case
from app.domain.entities.multi_face_result import MultiFaceResponse

router = APIRouter(
    prefix="/faces",
    tags=["Face Detection"],
)


@router.post(
    "/detect-all",
    response_model=MultiFaceResponse,
    summary="Detect all faces in image",
    description=(
        "Detects all faces in the image and returns bounding boxes, "
        "quality scores, and basic landmarks for each face."
    ),
)
async def detect_all_faces(
    file: UploadFile = File(...),
    max_faces: Optional[int] = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of faces to return",
    ),
) -> MultiFaceResponse:
    """Detect all faces in uploaded image.

    Args:
        file: Uploaded image file
        max_faces: Maximum number of faces to return

    Returns:
        MultiFaceResponse with all detected faces
    """
    # Read file content
    content = await file.read()

    # Convert to RGB numpy array
    image = Image.open(BytesIO(content)).convert("RGB")
    img_np = np.array(image)

    # Get use case from container
    use_case = get_detect_multi_face_use_case()

    # Execute detection
    result = await use_case.execute(img_np, max_faces=max_faces)

    return MultiFaceResponse.from_result(result)
