"""Demographics analysis API routes."""

from io import BytesIO

import numpy as np
from fastapi import APIRouter, File, UploadFile
from PIL import Image

from app.core.container import get_analyze_demographics_use_case
from app.domain.entities.demographics import DemographicsResponse

router = APIRouter(
    prefix="/demographics",
    tags=["Demographics"],
)


@router.post(
    "/analyze",
    response_model=DemographicsResponse,
    summary="Analyze face demographics",
    description=(
        "Estimates age, gender, and optionally emotion from a face image. "
        "Race estimation can be enabled via configuration."
    ),
)
async def analyze_demographics(
    file: UploadFile = File(...),
) -> DemographicsResponse:
    """Analyze demographics from face image.

    Args:
        file: Uploaded image file

    Returns:
        DemographicsResponse with age, gender, and optional attributes
    """
    # Read file content
    content = await file.read()

    # Convert to RGB numpy array
    image = Image.open(BytesIO(content)).convert("RGB")
    img_np = np.array(image)

    # Get use case from container
    use_case = get_analyze_demographics_use_case()

    # Execute analysis
    result = await use_case.execute(img_np)

    return DemographicsResponse.from_result(result)
