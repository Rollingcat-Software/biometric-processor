# app/application/use_cases/detect_card_type.py
from io import BytesIO

import numpy as np
from PIL import Image
from fastapi import UploadFile

from app.core.card_type_model.detector import detect_card_type
from app.domain.entities.card_type_result import CardTypeResponse


async def detect_card_type_use_case(file: UploadFile) -> CardTypeResponse:
    content = await file.read()

    image = Image.open(BytesIO(content)).convert("RGB")
    img_np = np.array(image)

    result = detect_card_type(img_np)

    return CardTypeResponse(
        detected=result.detected,
        class_id=result.class_id,
        class_name=result.class_name,
        confidence=result.confidence,
    )

