"""Unit tests for new infrastructure components."""

import pytest
import numpy as np
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
import time

from app.infrastructure.rate_limit.memory_storage import InMemoryRateLimitStorage
from app.infrastructure.webhooks.mock_webhook_sender import MockWebhookSender

from app.domain.interfaces.rate_limit_storage import RateLimitInfo


# ============================================================================
# InMemoryRateLimitStorage Tests
# ============================================================================


class TestInMemoryRateLimitStorage:
    """Test InMemoryRateLimitStorage."""

    def test_initial_state(self):
        """Test initial storage state."""
        storage = InMemoryRateLimitStorage()
        info = storage.get_info("test_key")

        assert isinstance(info, RateLimitInfo)
        assert info.remaining >= 0

    def test_increment_count(self):
        """Test incrementing request count."""
        storage = InMemoryRateLimitStorage()

        initial = storage.get_info("test_key")
        storage.increment("test_key")
        after = storage.get_info("test_key")

        # Remaining should decrease by 1
        assert after.remaining == initial.remaining - 1

    def test_multiple_increments(self):
        """Test multiple increments."""
        storage = InMemoryRateLimitStorage()

        for _ in range(5):
            storage.increment("test_key")

        info = storage.get_info("test_key")
        assert info.count == 5

    def test_different_keys_isolated(self):
        """Test that different keys are isolated."""
        storage = InMemoryRateLimitStorage()

        storage.increment("key_a")
        storage.increment("key_a")
        storage.increment("key_b")

        info_a = storage.get_info("key_a")
        info_b = storage.get_info("key_b")

        assert info_a.count == 2
        assert info_b.count == 1

    def test_is_rate_limited(self):
        """Test rate limit detection."""
        storage = InMemoryRateLimitStorage(limit=3)

        assert storage.is_rate_limited("test_key") is False

        storage.increment("test_key")
        storage.increment("test_key")
        storage.increment("test_key")

        assert storage.is_rate_limited("test_key") is True

    def test_reset(self):
        """Test resetting a key."""
        storage = InMemoryRateLimitStorage()

        storage.increment("test_key")
        storage.increment("test_key")
        storage.reset("test_key")

        info = storage.get_info("test_key")
        assert info.count == 0


# ============================================================================
# MockWebhookSender Tests
# ============================================================================


class TestMockWebhookSender:
    """Test MockWebhookSender."""

    @pytest.mark.asyncio
    async def test_successful_send(self):
        """Test successful webhook send."""
        sender = MockWebhookSender()

        result = await sender.send(
            url="https://example.com/webhook",
            event_type="test.event",
            data={"message": "test"},
            tenant_id="default",
        )

        assert result.success is True
        assert result.status_code == 200
        assert result.response_time_ms > 0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_send_with_secret(self):
        """Test webhook send with HMAC secret."""
        sender = MockWebhookSender()

        result = await sender.send(
            url="https://example.com/webhook",
            event_type="test.event",
            data={"message": "test"},
            tenant_id="default",
            secret="my_secret",
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_configured_failure(self):
        """Test configurable failure mode."""
        sender = MockWebhookSender(should_fail=True, fail_status_code=503)

        result = await sender.send(
            url="https://example.com/webhook",
            event_type="test.event",
            data={},
            tenant_id="default",
        )

        assert result.success is False
        assert result.status_code == 503
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_records_calls(self):
        """Test that mock records all calls."""
        sender = MockWebhookSender()

        await sender.send(
            url="https://example.com/webhook1",
            event_type="event1",
            data={"key": "value1"},
            tenant_id="tenant1",
        )

        await sender.send(
            url="https://example.com/webhook2",
            event_type="event2",
            data={"key": "value2"},
            tenant_id="tenant2",
        )

        assert len(sender.calls) == 2
        assert sender.calls[0]["url"] == "https://example.com/webhook1"
        assert sender.calls[1]["event_type"] == "event2"

    @pytest.mark.asyncio
    async def test_clear_calls(self):
        """Test clearing recorded calls."""
        sender = MockWebhookSender()

        await sender.send(
            url="https://example.com/webhook",
            event_type="test",
            data={},
            tenant_id="default",
        )

        assert len(sender.calls) == 1

        sender.clear_calls()

        assert len(sender.calls) == 0


# ============================================================================
# Factory Tests
# ============================================================================


class TestDemographicsAnalyzerFactory:
    """Test DemographicsAnalyzerFactory."""

    def test_create_deepface_analyzer(self):
        """Test creating deepface analyzer."""
        from app.infrastructure.ml.factories.demographics_factory import DemographicsAnalyzerFactory

        analyzer = DemographicsAnalyzerFactory.create(
            analyzer_type="deepface",
            include_race=False,
            include_emotion=True,
        )

        assert analyzer is not None

    def test_invalid_analyzer_type(self):
        """Test creating with invalid type raises error."""
        from app.infrastructure.ml.factories.demographics_factory import DemographicsAnalyzerFactory

        with pytest.raises(ValueError):
            DemographicsAnalyzerFactory.create(
                analyzer_type="invalid",
            )


class TestLandmarkDetectorFactory:
    """Test LandmarkDetectorFactory."""

    def test_create_mediapipe_detector(self):
        """Test creating mediapipe landmark detector."""
        from app.infrastructure.ml.factories.landmark_factory import LandmarkDetectorFactory

        detector = LandmarkDetectorFactory.create(
            detector_type="mediapipe_468",
        )

        assert detector is not None

    def test_invalid_detector_type(self):
        """Test creating with invalid type raises error."""
        from app.infrastructure.ml.factories.landmark_factory import LandmarkDetectorFactory

        with pytest.raises(ValueError):
            LandmarkDetectorFactory.create(
                detector_type="invalid",
            )


class TestWebhookSenderFactory:
    """Test WebhookSenderFactory."""

    def test_create_http_sender(self):
        """Test creating HTTP webhook sender."""
        from app.infrastructure.webhooks.webhook_factory import WebhookSenderFactory

        sender = WebhookSenderFactory.create(
            sender_type="http",
            retry_count=3,
        )

        assert sender is not None

    def test_create_mock_sender(self):
        """Test creating mock webhook sender."""
        from app.infrastructure.webhooks.webhook_factory import WebhookSenderFactory

        sender = WebhookSenderFactory.create(
            sender_type="mock",
        )

        assert sender is not None
        assert isinstance(sender, MockWebhookSender)

    def test_invalid_sender_type(self):
        """Test creating with invalid type raises error."""
        from app.infrastructure.webhooks.webhook_factory import WebhookSenderFactory

        with pytest.raises(ValueError):
            WebhookSenderFactory.create(
                sender_type="invalid",
            )


class TestRateLimitStorageFactory:
    """Test RateLimitStorageFactory."""

    def test_create_memory_storage(self):
        """Test creating in-memory rate limit storage."""
        from app.infrastructure.rate_limit.storage_factory import RateLimitStorageFactory

        storage = RateLimitStorageFactory.create(
            storage_type="memory",
        )

        assert storage is not None
        assert isinstance(storage, InMemoryRateLimitStorage)

    def test_invalid_storage_type(self):
        """Test creating with invalid type raises error."""
        from app.infrastructure.rate_limit.storage_factory import RateLimitStorageFactory

        with pytest.raises(ValueError):
            RateLimitStorageFactory.create(
                storage_type="invalid",
            )


class TestImagePreprocessorFactory:
    """Test ImagePreprocessorFactory."""

    def test_create_opencv_preprocessor(self):
        """Test creating OpenCV image preprocessor."""
        from app.infrastructure.ml.factories.preprocessor_factory import ImagePreprocessorFactory

        preprocessor = ImagePreprocessorFactory.create(
            preprocessor_type="opencv",
            auto_rotate=True,
            max_size=1920,
            normalize=True,
        )

        assert preprocessor is not None

    def test_invalid_preprocessor_type(self):
        """Test creating with invalid type raises error."""
        from app.infrastructure.ml.factories.preprocessor_factory import ImagePreprocessorFactory

        with pytest.raises(ValueError):
            ImagePreprocessorFactory.create(
                preprocessor_type="invalid",
            )
