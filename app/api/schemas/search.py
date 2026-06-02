"""Search endpoint schemas."""

from typing import List, Optional

from pydantic import BaseModel, Field


class SearchMatchResponse(BaseModel):
    """Individual search match response."""

    user_id: str = Field(..., description="Matched user identifier")
    distance: float = Field(..., ge=0, le=2, description="Cosine distance (0=identical); raw engineering value")
    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description=(
            "Threshold-anchored match confidence (0-1): accept boundary ~0.5, "
            "identical match ~1.0. Not the naive 1 - distance."
        ),
    )

    model_config = {
        "json_schema_extra": {
            # confidence is threshold-anchored on the default 0.6 search threshold:
            # 1 - distance / (2 * 0.6). distance 0.15 -> 0.875, 0.25 -> 0.7917.
            "example": {
                "user_id": "user_123",
                "distance": 0.15,
                "confidence": 0.875,
            }
        }
    }


class SearchResponse(BaseModel):
    """Face search response."""

    found: bool = Field(..., description="Whether any matches were found")
    matches: List[SearchMatchResponse] = Field(
        default_factory=list, description="List of matching users"
    )
    total_searched: int = Field(..., ge=0, description="Total users searched")
    threshold: float = Field(..., ge=0, le=2, description="Distance threshold used")
    best_match: Optional[SearchMatchResponse] = Field(
        None, description="Best match (lowest distance)"
    )
    message: str = Field(..., description="Result message")

    model_config = {
        "json_schema_extra": {
            # confidence is threshold-anchored: 1 - distance / (2 * threshold).
            # With threshold 0.6: distance 0.15 -> 0.875, 0.25 -> 0.7917.
            "example": {
                "found": True,
                "matches": [
                    {"user_id": "user_123", "distance": 0.15, "confidence": 0.875},
                    {"user_id": "user_456", "distance": 0.25, "confidence": 0.7917},
                ],
                "total_searched": 100,
                "threshold": 0.6,
                "best_match": {
                    "user_id": "user_123",
                    "distance": 0.15,
                    "confidence": 0.875,
                },
                "message": "Found 2 matches",
            }
        }
    }
