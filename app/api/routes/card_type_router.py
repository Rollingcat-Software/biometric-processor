"""Card type detection API routes."""

import os
import tempfile
from io import BytesIO

import numpy as np
from fastapi import APIRouter, File, UploadFile
from PIL import Image

from app.core.container import get_detect_card_type_use_case
from app.domain.entities.card_type_result import CardTypeResponse

router = APIRouter(
    prefix="/card-type",
    tags=["Card Type"],
)


@router.post(
    "/detect-live",
    response_model=CardTypeResponse,
    summary="Detect card type from image",
    description=(
        "Detects the card type from the provided image. "
        "Supported classes: tc_kimlik, ehliyet, pasaport, ogrenci_karti. "
        "Designed for real-time mobile camera preview (0.5–1 second intervals)."
    ),
)
async def detect_live(file: UploadFile = File(...)) -> CardTypeResponse:
    """Detect card type from uploaded image.

    Args:
        file: Uploaded image file

    Returns:
        CardTypeResponse with detection result
    """
    # Read file content
    content = await file.read()

    # Convert to RGB numpy array
    image = Image.open(BytesIO(content)).convert("RGB")
    img_np = np.array(image)

    # Get use case from container (dependency injection)
    use_case = get_detect_card_type_use_case()

    # Execute detection
    result = await use_case.execute_from_array(img_np)

    # Return response
    return CardTypeResponse.from_result(result)
