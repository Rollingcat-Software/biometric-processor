"""Card type detection API routes."""

import asyncio
from io import BytesIO

import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile
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
        "Detects the card type from the provided image."
        "Supported classes: tc_kimlik, ehliyet, pasaport, ogrenci_karti,akademisyen_karti."
        "Designed for real-time mobile camera preview (0.5-1 second intervals)."
    ),
)
async def detect_live(file: UploadFile = File(...)) -> CardTypeResponse:
    """Detect card type from uploaded image.

    Supported classes: tc_kimlik, ehliyet, pasaport, ogrenci_karti, akademisyen_karti.
    Designed for real-time mobile preview (0.5-1s frame intervals).
    """
    content = await file.read()
    image = Image.open(BytesIO(content)).convert("RGB")

    max_dim = 1280
    if max(image.size) > max_dim:
        image.thumbnail((max_dim, max_dim))

    img_np = np.array(image)

    use_case = get_detect_card_type_use_case()
    try:
        result = await asyncio.wait_for(use_case.execute_from_array(img_np), timeout=30)
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Card type detection timed out") from exc

    return CardTypeResponse.from_result(result)
