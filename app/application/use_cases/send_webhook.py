"""Send webhook use case."""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from app.domain.entities.webhook_event import WebhookEvent, WebhookResult
from app.domain.exceptions.feature_errors import WebhookConfigError
from app.domain.interfaces.webhook_sender import IWebhookSender

logger = logging.getLogger(__name__)


class SendWebhookUseCase:
    """Use case for sending webhook notifications.

    Handles webhook delivery with proper formatting and error handling.
    """

    def __init__(self, webhook_sender: IWebhookSender) -> None:
        """Initialize send webhook use case.

        Args:
            webhook_sender: Webhook sender implementation
        """
        self._sender = webhook_sender
        logger.info("SendWebhookUseCase initialized")

    async def execute(
        self,
        url: str,
        event_type: str,
        data: Dict[str, Any],
        tenant_id: str = "default",
        secret: Optional[str] = None,
    ) -> WebhookResult:
        """Execute webhook send.

        Args:
            url: Target webhook URL
            event_type: Type of event (e.g., enrollment.success)
            data: Event payload data
            tenant_id: Tenant identifier
            secret: Optional signing secret

        Returns:
            WebhookResult with delivery status

        Raises:
            WebhookConfigError: If URL is invalid
        """
        logger.info(f"Sending webhook: {event_type} to {url}")

        # Validate URL
        if not url or not url.startswith(("http://", "https://")):
            raise WebhookConfigError(f"Invalid webhook URL: {url}")

        # Create event
        event = WebhookEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            timestamp=datetime.utcnow(),
            tenant_id=tenant_id,
            data=data,
        )

        # Send webhook
        result = await self._sender.send(url, event, secret)

        if result.success:
            logger.info(
                f"Webhook delivered: {event.event_id}, "
                f"status={result.status_code}, time={result.response_time_ms}ms"
            )
        else:
            logger.warning(
                f"Webhook failed: {event.event_id}, "
                f"error={result.error}, retries={result.retry_count}"
            )

        return result

    async def send_enrollment_event(
        self,
        url: str,
        user_id: str,
        success: bool,
        quality_score: float = None,
        tenant_id: str = "default",
        secret: Optional[str] = None,
    ) -> WebhookResult:
        """Send enrollment event webhook."""
        event_type = "enrollment.success" if success else "enrollment.failed"
        data = {"user_id": user_id}
        if quality_score is not None:
            data["quality_score"] = quality_score

        return await self.execute(url, event_type, data, tenant_id, secret)

    async def send_verification_event(
        self,
        url: str,
        user_id: str,
        match: bool,
        similarity: float = None,
        tenant_id: str = "default",
        secret: Optional[str] = None,
    ) -> WebhookResult:
        """Send verification event webhook."""
        event_type = "verification.match" if match else "verification.mismatch"
        data = {"user_id": user_id}
        if similarity is not None:
            data["similarity"] = similarity

        return await self.execute(url, event_type, data, tenant_id, secret)

    async def send_liveness_event(
        self,
        url: str,
        is_live: bool,
        score: float = None,
        tenant_id: str = "default",
        secret: Optional[str] = None,
    ) -> WebhookResult:
        """Send liveness event webhook."""
        event_type = "liveness.pass" if is_live else "liveness.fail"
        data = {"is_live": is_live}
        if score is not None:
            data["score"] = score

        return await self.execute(url, event_type, data, tenant_id, secret)
