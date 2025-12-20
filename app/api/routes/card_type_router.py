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
        "Detects the card type from the provided image."
        "Supported classes: tc_kimlik, ehliyet, pasaport, ogrenci_karti,akademisyen_karti."
        "Designed for real-time mobile camera preview (0.5–1 second intervals)."
    ),
)


async def detect_live(file: UploadFile = File(...)) -> CardTypeResponse:
    """Detect card type from uploaded image.

    Supported classes: tc_kimlik, ehliyet, pasaport, ogrenci_karti, akademisyen_karti.
    Designed for real-time mobile preview (0.5–1s frame intervals).
    """
    return await detect_card_type_use_case(file)


