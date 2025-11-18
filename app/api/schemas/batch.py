"""API schemas for batch operations."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BatchEnrollmentItemRequest(BaseModel):
    """Request model for a single enrollment item in batch."""

    user_id: str = Field(..., description="Unique user identifier")
    tenant_id: Optional[str] = Field(None, description="Optional tenant identifier")


class BatchItemResultResponse(BaseModel):
    """Response model for a single batch item result."""

    item_id: str = Field(..., description="Item identifier")
    status: str = Field(..., description="Status: success, failed, or skipped")
    data: Optional[Dict[str, Any]] = Field(None, description="Result data if successful")
    error: Optional[str] = Field(None, description="Error message if failed")
    error_code: Optional[str] = Field(None, description="Error code for programmatic handling")


class BatchEnrollmentResponse(BaseModel):
    """Response model for batch enrollment operation."""

    total_items: int = Field(..., description="Total number of items processed")
    successful: int = Field(..., description="Number of successful enrollments")
    failed: int = Field(..., description="Number of failed enrollments")
    skipped: int = Field(..., description="Number of skipped enrollments (duplicates)")
    results: List[BatchItemResultResponse] = Field(
        default_factory=list,
        description="Individual results for each item",
    )
    message: str = Field(..., description="Summary message")


class BatchVerificationItemRequest(BaseModel):
    """Request model for a single verification item in batch."""

    item_id: str = Field(..., description="Unique item identifier for this verification")
    user_id: str = Field(..., description="User to verify against")
    tenant_id: Optional[str] = Field(None, description="Optional tenant identifier")


class BatchVerificationResponse(BaseModel):
    """Response model for batch verification operation."""

    total_items: int = Field(..., description="Total number of items processed")
    successful: int = Field(..., description="Number of successful verifications")
    failed: int = Field(..., description="Number of failed verifications")
    results: List[BatchItemResultResponse] = Field(
        default_factory=list,
        description="Individual results for each item",
    )
    message: str = Field(..., description="Summary message")
