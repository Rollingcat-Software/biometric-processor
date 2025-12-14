"""Webhook event domain entities."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


@dataclass
class WebhookEvent:
    """Webhook event to be sent.

    Attributes:
        event_id: Unique event identifier
        event_type: Type of event (e.g., enrollment.success)
        timestamp: Event timestamp
        tenant_id: Tenant identifier
        data: Event payload data
    """

    event_id: str
    event_type: str
    timestamp: datetime
    tenant_id: str
    data: Dict[str, Any]


@dataclass
class WebhookResult:
    """Result of webhook delivery attempt.

    Attributes:
        success: Whether delivery was successful
        status_code: HTTP status code from target
        response_time_ms: Response time in milliseconds
        error: Error message if failed
        retry_count: Number of retries attempted
    """

    success: bool
    status_code: Optional[int] = None
    response_time_ms: int = 0
    error: Optional[str] = None
    retry_count: int = 0


@dataclass
class WebhookConfig:
    """Webhook configuration.

    Attributes:
        webhook_id: Unique webhook identifier
        url: Target URL
        secret: Signing secret
        events: List of subscribed events
        enabled: Whether webhook is enabled
        created_at: Creation timestamp
    """

    webhook_id: str
    url: str
    secret: Optional[str] = None
    events: List[str] = None
    enabled: bool = True
    created_at: datetime = None


# Pydantic models for API


class WebhookRegisterRequest(BaseModel):
    """Request model for webhook registration."""

    url: str
    secret: Optional[str] = None
    events: List[str] = ["enrollment", "verification", "liveness"]


class WebhookConfigResponse(BaseModel):
    """API response model for webhook config."""

    webhook_id: str
    url: str
    events: List[str]
    enabled: bool
    created_at: str

    @classmethod
    def from_config(cls, config: WebhookConfig) -> "WebhookConfigResponse":
        """Create response from config."""
        return cls(
            webhook_id=config.webhook_id,
            url=config.url,
            events=config.events or [],
            enabled=config.enabled,
            created_at=config.created_at.isoformat() if config.created_at else "",
        )


class WebhookTestResponse(BaseModel):
    """API response model for webhook test."""

    success: bool
    status_code: Optional[int] = None
    response_time_ms: int
    error: Optional[str] = None
