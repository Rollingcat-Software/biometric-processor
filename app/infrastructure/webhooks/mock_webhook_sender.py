"""Mock webhook sender for testing."""

import logging
from typing import List, Optional

from app.domain.entities.webhook_event import WebhookEvent, WebhookResult

logger = logging.getLogger(__name__)


class MockWebhookSender:
    """Mock webhook sender for testing.

    Records all sent webhooks for verification in tests.
    """

    def __init__(self) -> None:
        """Initialize mock webhook sender."""
        self._sent_webhooks: List[dict] = []
        self._should_fail = False
        self._fail_count = 0
        logger.info("MockWebhookSender initialized")

    async def send(
        self,
        url: str,
        event: WebhookEvent,
        secret: Optional[str] = None,
    ) -> WebhookResult:
        """Mock send webhook notification.

        Args:
            url: Target webhook URL
            event: Event to send
            secret: Optional signing secret

        Returns:
            WebhookResult with mock delivery status
        """
        # Record the webhook
        self._sent_webhooks.append(
            {
                "url": url,
                "event": event,
                "secret": secret,
            }
        )

        # Simulate failure if configured
        if self._should_fail:
            self._fail_count += 1
            return WebhookResult(
                success=False,
                status_code=500,
                response_time_ms=100,
                error="Mock failure",
                retry_count=3,
            )

        logger.debug(f"Mock webhook sent: {event.event_type} to {url}")

        return WebhookResult(
            success=True,
            status_code=200,
            response_time_ms=50,
            retry_count=0,
        )

    def sign_payload(self, payload: bytes, secret: str) -> str:
        """Mock sign payload."""
        import hashlib
        import hmac

        return hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()

    # Test helper methods

    def get_sent_webhooks(self) -> List[dict]:
        """Get all sent webhooks for verification."""
        return self._sent_webhooks

    def clear_webhooks(self) -> None:
        """Clear recorded webhooks."""
        self._sent_webhooks = []

    def set_should_fail(self, should_fail: bool) -> None:
        """Configure mock to fail or succeed."""
        self._should_fail = should_fail

    def get_fail_count(self) -> int:
        """Get number of failed webhook attempts."""
        return self._fail_count
