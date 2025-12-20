"""Webhook management API routes."""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.container import get_send_webhook_use_case
from app.domain.entities.webhook_event import (
    WebhookConfigResponse,
    WebhookRegisterRequest,
    WebhookTestResponse,
)

router = APIRouter(
    prefix="/webhooks",
    tags=["Webhooks"],
)

# In-memory webhook storage (would use database in production)
_webhooks: Dict[str, dict] = {}


class WebhookListResponse(BaseModel):
    """Response model for webhook list."""

    webhooks: List[WebhookConfigResponse]
    count: int


@router.post(
    "/register",
    response_model=WebhookConfigResponse,
    summary="Register webhook",
    description="Register a new webhook endpoint for receiving notifications.",
)
async def register_webhook(request: WebhookRegisterRequest) -> WebhookConfigResponse:
    """Register a new webhook.

    Args:
        request: Webhook registration request

    Returns:
        Created webhook configuration
    """
    webhook_id = f"wh_{uuid.uuid4().hex[:12]}"

    webhook = {
        "webhook_id": webhook_id,
        "url": request.url,
        "secret": request.secret,
        "events": request.events,
        "enabled": True,
        "created_at": datetime.utcnow(),
    }

    _webhooks[webhook_id] = webhook

    return WebhookConfigResponse(
        webhook_id=webhook_id,
        url=request.url,
        events=request.events,
        enabled=True,
        created_at=webhook["created_at"].isoformat(),
    )


@router.get(
    "",
    response_model=WebhookListResponse,
    summary="List webhooks",
    description="List all registered webhooks.",
)
async def list_webhooks() -> WebhookListResponse:
    """List all registered webhooks.

    Returns:
        List of webhook configurations
    """
    webhooks = [
        WebhookConfigResponse(
            webhook_id=wh["webhook_id"],
            url=wh["url"],
            events=wh["events"],
            enabled=wh["enabled"],
            created_at=wh["created_at"].isoformat(),
        )
        for wh in _webhooks.values()
    ]

    return WebhookListResponse(webhooks=webhooks, count=len(webhooks))


@router.delete(
    "/{webhook_id}",
    summary="Delete webhook",
    description="Delete a registered webhook.",
)
async def delete_webhook(webhook_id: str) -> Dict[str, str]:
    """Delete a webhook.

    Args:
        webhook_id: Webhook identifier

    Returns:
        Deletion confirmation
    """
    if webhook_id not in _webhooks:
        raise HTTPException(status_code=404, detail="Webhook not found")

    del _webhooks[webhook_id]

    return {"message": "Webhook deleted", "webhook_id": webhook_id}


@router.post(
    "/{webhook_id}/test",
    response_model=WebhookTestResponse,
    summary="Test webhook",
    description="Send a test event to the webhook endpoint.",
)
async def test_webhook(webhook_id: str) -> WebhookTestResponse:
    """Test webhook delivery.

    Args:
        webhook_id: Webhook identifier

    Returns:
        Test result
    """
    if webhook_id not in _webhooks:
        raise HTTPException(status_code=404, detail="Webhook not found")

    webhook = _webhooks[webhook_id]

    # Get use case from container
    use_case = get_send_webhook_use_case()

    # Send test event
    result = await use_case.execute(
        url=webhook["url"],
        event_type="test.ping",
        data={"message": "Test webhook delivery"},
        tenant_id="default",
        secret=webhook.get("secret"),
    )

    return WebhookTestResponse(
        success=result.success,
        status_code=result.status_code,
        response_time_ms=result.response_time_ms,
        error=result.error,
    )
