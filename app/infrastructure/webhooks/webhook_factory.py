"""Webhook sender factory."""

from typing import Literal

from app.domain.interfaces.webhook_sender import IWebhookSender

WebhookTransport = Literal["http", "mock"]


class WebhookSenderFactory:
    """Factory for creating webhook sender instances.

    Follows Open/Closed Principle: Add new transports without modifying existing code.
    """

    @staticmethod
    def create(
        transport: WebhookTransport = "http",
        timeout: int = 10,
        retry_count: int = 3,
    ) -> IWebhookSender:
        """Create webhook sender instance.

        Args:
            transport: Transport type (http or mock)
            timeout: Request timeout in seconds
            retry_count: Number of retries on failure

        Returns:
            IWebhookSender implementation

        Raises:
            ValueError: If unknown transport specified
        """
        if transport == "http":
            from app.infrastructure.webhooks.http_webhook_sender import (
                HttpWebhookSender,
            )

            return HttpWebhookSender(timeout=timeout, retry_count=retry_count)

        elif transport == "mock":
            from app.infrastructure.webhooks.mock_webhook_sender import (
                MockWebhookSender,
            )

            return MockWebhookSender()

        raise ValueError(f"Unknown webhook transport: {transport}")
