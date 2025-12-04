# app/domain/entities/card_type_result.py
from pydantic import BaseModel
from typing import Optional


class CardTypeResponse(BaseModel):
    detected: bool
    class_id: Optional[int] = None
    class_name: Optional[str] = None
    confidence: Optional[float] = None

