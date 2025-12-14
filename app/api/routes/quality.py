"""Quality feedback API routes."""

from io import BytesIO

import numpy as np
from fastapi import APIRouter, File, UploadFile
from PIL import Image

from app.core.container import get_analyze_quality_use_case
from app.domain.entities.quality_feedback import QualityFeedbackResponse

router = APIRouter(
    prefix="/quality",
    tags=["Quality"],
)


@router.post(
    "/analyze",
    response_model=QualityFeedbackResponse,
    summary="Analyze image quality",
    description=(
        "Analyzes image quality and returns detailed feedback including "
        "issues detected and actionable suggestions for improvement."
    ),
)
async def analyze_quality(file: UploadFile = File(...)) -> QualityFeedbackResponse:
    """Analyze image quality with detailed feedback.

    Args:
        file: Uploaded image file

    Returns:
        QualityFeedbackResponse with analysis results
    """
    # Read file content
    content = await file.read()

    # Convert to RGB numpy array
    image = Image.open(BytesIO(content)).convert("RGB")
    img_np = np.array(image)

    # Get use case from container
    use_case = get_analyze_quality_use_case()

    # Execute analysis
    result = await use_case.execute(img_np)

    return QualityFeedbackResponse.from_result(result)
