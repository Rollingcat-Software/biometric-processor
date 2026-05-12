"""Unit tests for new infrastructure components.

Refreshed 2026-05-12 to match current production signatures (issue #91).
The earlier copy of this file was written against an older draft API
(``storage.get_info``, ``InMemoryRateLimitStorage(limit=...)``,
``MockWebhookSender.send(event_type=...)``, ``Factory.create(analyzer_type=...)``,
etc.) that drifted out from under it when the production classes settled
on async + protocol-driven signatures. Tests below exercise the *current*
API only; they are deliberately mechanical (no behaviour changes).
"""

from datetime import datetime, timezone

import pytest

from app.domain.entities.webhook_event import (
    WebhookEvent,
    WebhookResult,
)
from app.domain.interfaces.rate_limit_storage import RateLimitInfo
from app.infrastructure.rate_limit.memory_storage import InMemoryRateLimitStorage
from app.infrastructure.webhooks.mock_webhook_sender import MockWebhookSender


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _event(event_type: str = "test.event", tenant_id: str = "default") -> WebhookEvent:
    """Build a minimal valid WebhookEvent for tests."""
    return WebhookEvent(
        event_id="evt_test",
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        tenant_id=tenant_id,
        data={"message": "test"},
    )


# ============================================================================
# InMemoryRateLimitStorage Tests
# ============================================================================


class TestInMemoryRateLimitStorage:
    """Test the current async InMemoryRateLimitStorage surface."""

    async def test_increment_returns_rate_limit_info(self) -> None:
        storage = InMemoryRateLimitStorage()

        info = await storage.increment("test_key", limit=10, window_seconds=60)

        assert isinstance(info, RateLimitInfo)
        assert info.limit == 10
        assert info.remaining == 9

    async def test_multiple_increments_decrement_remaining(self) -> None:
        storage = InMemoryRateLimitStorage()

        for _ in range(5):
            await storage.increment("k", limit=10, window_seconds=60)
        info = await storage.increment("k", limit=10, window_seconds=60)

        assert info.remaining == 4

    async def test_different_keys_isolated(self) -> None:
        storage = InMemoryRateLimitStorage()

        await storage.increment("a", limit=10, window_seconds=60)
        await storage.increment("a", limit=10, window_seconds=60)
        await storage.increment("b", limit=10, window_seconds=60)

        info_a = await storage.increment("a", limit=10, window_seconds=60)
        info_b = await storage.increment("b", limit=10, window_seconds=60)

        # a now consumed 3 of 10, b consumed 2 of 10
        assert info_a.remaining == 7
        assert info_b.remaining == 8

    async def test_increment_floors_remaining_at_zero(self) -> None:
        storage = InMemoryRateLimitStorage()

        info = None
        for _ in range(15):
            info = await storage.increment("burst", limit=10, window_seconds=60)

        assert info is not None
        assert info.remaining == 0

    async def test_reset_clears_counter(self) -> None:
        storage = InMemoryRateLimitStorage()

        for _ in range(3):
            await storage.increment("k", limit=10, window_seconds=60)
        await storage.reset("k")
        info = await storage.increment("k", limit=10, window_seconds=60)

        # After reset, the next increment should report 9 remaining (1 used).
        assert info.remaining == 9

    async def test_get_returns_none_for_unknown_key(self) -> None:
        storage = InMemoryRateLimitStorage()

        assert await storage.get("never-seen") is None

    async def test_get_all_keys_lists_tracked(self) -> None:
        storage = InMemoryRateLimitStorage()

        await storage.increment("alpha", limit=10, window_seconds=60)
        await storage.increment("beta", limit=10, window_seconds=60)
        keys = await storage.get_all_keys()

        assert set(keys) == {"alpha", "beta"}

    def test_set_tier_does_not_raise(self) -> None:
        storage = InMemoryRateLimitStorage()
        storage.set_tier("k", "premium")  # smoke: stores tier on entry


# ============================================================================
# MockWebhookSender Tests
# ============================================================================


class TestMockWebhookSender:
    """Test the current MockWebhookSender surface."""

    async def test_successful_send_returns_success_result(self) -> None:
        sender = MockWebhookSender()

        result = await sender.send(
            url="https://example.com/webhook",
            event=_event(),
        )

        assert isinstance(result, WebhookResult)
        assert result.success is True
        assert result.status_code == 200
        assert result.error is None

    async def test_send_with_secret_succeeds(self) -> None:
        sender = MockWebhookSender()

        result = await sender.send(
            url="https://example.com/webhook",
            event=_event(),
            secret="my_secret",
        )

        assert result.success is True

    async def test_configured_failure_returns_500(self) -> None:
        sender = MockWebhookSender()
        sender.set_should_fail(True)

        result = await sender.send(
            url="https://example.com/webhook",
            event=_event(),
        )

        assert result.success is False
        assert result.status_code == 500
        assert result.error is not None
        assert sender.get_fail_count() == 1

    async def test_records_calls(self) -> None:
        sender = MockWebhookSender()

        await sender.send(url="https://example.com/w1", event=_event("event1", "t1"))
        await sender.send(url="https://example.com/w2", event=_event("event2", "t2"))

        sent = sender.get_sent_webhooks()
        assert len(sent) == 2
        assert sent[0]["url"] == "https://example.com/w1"
        assert sent[1]["event"].event_type == "event2"

    async def test_clear_webhooks(self) -> None:
        sender = MockWebhookSender()

        await sender.send(url="https://example.com/w", event=_event())
        assert len(sender.get_sent_webhooks()) == 1

        sender.clear_webhooks()
        assert sender.get_sent_webhooks() == []

    def test_sign_payload_returns_hmac_hex(self) -> None:
        sender = MockWebhookSender()
        sig = sender.sign_payload(b"payload", "secret")
        # HMAC-SHA256 hex is 64 chars
        assert isinstance(sig, str)
        assert len(sig) == 64


# ============================================================================
# Factory Tests
# ============================================================================


class TestDemographicsAnalyzerFactory:
    def test_create_deepface_analyzer(self) -> None:
        from app.infrastructure.ml.factories.demographics_factory import (
            DemographicsAnalyzerFactory,
        )

        analyzer = DemographicsAnalyzerFactory.create(
            backend="deepface",
            include_race=False,
            include_emotion=True,
        )
        assert analyzer is not None

    def test_invalid_backend_raises(self) -> None:
        from app.infrastructure.ml.factories.demographics_factory import (
            DemographicsAnalyzerFactory,
        )

        with pytest.raises(ValueError):
            DemographicsAnalyzerFactory.create(backend="invalid")  # type: ignore[arg-type]


class TestLandmarkDetectorFactory:
    def test_create_mediapipe_detector(self) -> None:
        from app.infrastructure.ml.factories.landmark_factory import (
            LandmarkDetectorFactory,
        )

        detector = LandmarkDetectorFactory.create(model="mediapipe_468")
        assert detector is not None

    def test_invalid_model_raises(self) -> None:
        from app.infrastructure.ml.factories.landmark_factory import (
            LandmarkDetectorFactory,
        )

        with pytest.raises(ValueError):
            LandmarkDetectorFactory.create(model="invalid")  # type: ignore[arg-type]


class TestWebhookSenderFactory:
    def test_create_http_sender(self) -> None:
        from app.infrastructure.webhooks.webhook_factory import WebhookSenderFactory

        sender = WebhookSenderFactory.create(transport="http", retry_count=3)
        assert sender is not None

    def test_create_mock_sender(self) -> None:
        from app.infrastructure.webhooks.webhook_factory import WebhookSenderFactory

        sender = WebhookSenderFactory.create(transport="mock")
        assert sender is not None
        assert isinstance(sender, MockWebhookSender)

    def test_invalid_transport_raises(self) -> None:
        from app.infrastructure.webhooks.webhook_factory import WebhookSenderFactory

        with pytest.raises(ValueError):
            WebhookSenderFactory.create(transport="invalid")  # type: ignore[arg-type]


class TestRateLimitStorageFactory:
    def test_create_memory_storage(self) -> None:
        from app.infrastructure.rate_limit.storage_factory import (
            RateLimitStorageFactory,
        )

        storage = RateLimitStorageFactory.create(backend="memory")
        assert storage is not None
        assert isinstance(storage, InMemoryRateLimitStorage)

    def test_invalid_backend_raises(self) -> None:
        from app.infrastructure.rate_limit.storage_factory import (
            RateLimitStorageFactory,
        )

        with pytest.raises(ValueError):
            RateLimitStorageFactory.create(backend="invalid")  # type: ignore[arg-type]

    def test_redis_backend_requires_url(self) -> None:
        from app.infrastructure.rate_limit.storage_factory import (
            RateLimitStorageFactory,
        )

        with pytest.raises(ValueError):
            RateLimitStorageFactory.create(backend="redis", redis_url=None)


class TestImagePreprocessorFactory:
    def test_create_opencv_preprocessor(self) -> None:
        from app.infrastructure.ml.factories.preprocessor_factory import (
            ImagePreprocessorFactory,
        )

        preprocessor = ImagePreprocessorFactory.create(
            auto_rotate=True,
            max_size=1920,
            normalize=True,
        )
        assert preprocessor is not None

    def test_default_args(self) -> None:
        from app.infrastructure.ml.factories.preprocessor_factory import (
            ImagePreprocessorFactory,
        )

        preprocessor = ImagePreprocessorFactory.create()
        assert preprocessor is not None
