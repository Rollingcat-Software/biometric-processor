"""Webhook sender interface."""

from typing import Optional, Protocol

from app.domain.entities.webhook_event import WebhookEvent, WebhookResult


class IWebhookSender(Protocol):
    """Interface for sending webhook notifications.

    Implementations handle HTTP delivery of webhook events
    with retry logic and signature verification.
    """

    async def send(
        self,
        url: str,
        event: WebhookEvent,
        secret: Optional[str] = None,
    ) -> WebhookResult:
        """Send webhook notification.

        Args:
            url: Target webhook URL
            event: Event to send
            secret: Optional signing secret

        Returns:
            WebhookResult with delivery status
        """
        ...

    def sign_payload(self, payload: bytes, secret: str) -> str:
        """Generate HMAC signature for payload.

        Args:
            payload: JSON payload bytes
            secret: Signing secret

        Returns:
            HMAC signature string
        """
        ...
