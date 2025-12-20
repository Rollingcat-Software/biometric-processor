# app/api/routes/card_type_router.py
from fastapi import APIRouter, UploadFile, File

from app.application.use_cases.detect_card_type import detect_card_type_use_case
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

async def detect_live(file: UploadFile = File(...)):
    return await detect_card_type_use_case(file)


