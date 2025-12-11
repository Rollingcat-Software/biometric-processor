"""HTTP webhook sender implementation."""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from typing import Optional

import httpx

from app.domain.entities.webhook_event import WebhookEvent, WebhookResult
from app.domain.exceptions.feature_errors import WebhookDeliveryError, WebhookTimeoutError

logger = logging.getLogger(__name__)


class HttpWebhookSender:
    """HTTP-based webhook sender.

    Sends webhook notifications via HTTP with retry logic
    and HMAC signature verification.
    """

    def __init__(
        self,
        timeout: int = 10,
        retry_count: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """Initialize HTTP webhook sender.

        Args:
            timeout: Request timeout in seconds
            retry_count: Number of retries on failure
            retry_delay: Base delay between retries (exponential backoff)
        """
        self._timeout = timeout
        self._retry_count = retry_count
        self._retry_delay = retry_delay
        logger.info(
            f"HttpWebhookSender initialized: "
            f"timeout={timeout}s, retries={retry_count}"
        )

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
        logger.debug(f"Sending webhook to {url}: {event.event_type}")

        # Prepare payload
        payload = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat() + "Z",
            "tenant_id": event.tenant_id,
            "data": event.data,
        }

        payload_bytes = json.dumps(payload).encode("utf-8")

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "BiometricProcessor-Webhook/1.0",
            "X-Event-ID": event.event_id,
            "X-Event-Type": event.event_type,
        }

        if secret:
            signature = self.sign_payload(payload_bytes, secret)
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        # Send with retries
        last_error = None
        retry_count = 0

        for attempt in range(self._retry_count + 1):
            start_time = time.time()

            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        url,
                        content=payload_bytes,
                        headers=headers,
                    )

                response_time = int((time.time() - start_time) * 1000)

                # Success (2xx status)
                if 200 <= response.status_code < 300:
                    return WebhookResult(
                        success=True,
                        status_code=response.status_code,
                        response_time_ms=response_time,
                        retry_count=retry_count,
                    )

                # Retry on 5xx errors
                if response.status_code >= 500:
                    last_error = f"Server error: {response.status_code}"
                    retry_count += 1

                    if attempt < self._retry_count:
                        delay = self._retry_delay * (2**attempt)
                        logger.warning(
                            f"Webhook failed (attempt {attempt + 1}), "
                            f"retrying in {delay}s: {last_error}"
                        )
                        await asyncio.sleep(delay)
                        continue

                # Client error (4xx) - don't retry
                return WebhookResult(
                    success=False,
                    status_code=response.status_code,
                    response_time_ms=response_time,
                    error=f"Client error: {response.status_code}",
                    retry_count=retry_count,
                )

            except httpx.TimeoutException as e:
                response_time = int((time.time() - start_time) * 1000)
                last_error = f"Timeout: {str(e)}"
                retry_count += 1

                if attempt < self._retry_count:
                    delay = self._retry_delay * (2**attempt)
                    logger.warning(
                        f"Webhook timeout (attempt {attempt + 1}), "
                        f"retrying in {delay}s"
                    )
                    await asyncio.sleep(delay)
                    continue

            except Exception as e:
                response_time = int((time.time() - start_time) * 1000)
                last_error = str(e)
                retry_count += 1

                if attempt < self._retry_count:
                    delay = self._retry_delay * (2**attempt)
                    logger.warning(
                        f"Webhook error (attempt {attempt + 1}), "
                        f"retrying in {delay}s: {last_error}"
                    )
                    await asyncio.sleep(delay)
                    continue

        # All retries exhausted
        logger.error(f"Webhook delivery failed after {retry_count} retries: {last_error}")

        return WebhookResult(
            success=False,
            status_code=None,
            response_time_ms=0,
            error=last_error,
            retry_count=retry_count,
        )

    def sign_payload(self, payload: bytes, secret: str) -> str:
        """Generate HMAC signature for payload.

        Args:
            payload: JSON payload bytes
            secret: Signing secret

        Returns:
            HMAC-SHA256 signature hex string
        """
        return hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
