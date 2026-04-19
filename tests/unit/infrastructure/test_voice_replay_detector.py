"""Unit tests for VoiceReplayDetector (ML-H4).

The detector is log-only today, so tests assert:
    * The same audio fingerprint played twice is flagged as a suspect.
    * A log line ``voice_replay_suspect`` is emitted on the second call.
    * Detection is a no-op when the feature flag is disabled.
"""

import logging

import numpy as np
import pytest

from app.infrastructure.ml.voice.replay_detector import (
    VoiceReplayDetector,
    compute_spectral_fingerprint,
)


class _InMemoryRedis:
    """Minimal async Redis stand-in — only the methods the detector uses."""

    def __init__(self):
        self._lists: dict[str, list[bytes]] = {}

    async def lrange(self, key, start, end):
        items = self._lists.get(key, [])
        # Redis: end inclusive; python slicing: end exclusive
        if end == -1:
            return items[start:]
        return items[start : end + 1]

    async def lpush(self, key, value):
        payload = value.encode("utf-8") if isinstance(value, str) else value
        self._lists.setdefault(key, []).insert(0, payload)
        return len(self._lists[key])

    async def ltrim(self, key, start, end):
        if key not in self._lists:
            return "OK"
        items = self._lists[key]
        if end == -1:
            self._lists[key] = items[start:]
        else:
            self._lists[key] = items[start : end + 1]
        return "OK"


def _fake_samples(seed: int = 0, n: int = 16000) -> np.ndarray:
    """Build a deterministic tone of a distinct frequency per seed.

    Using tones (rather than white noise) makes the spectral fingerprints
    genuinely distinguishable — averaged spectra of independent white noise
    are nearly identical at this fingerprint resolution.
    """
    # Seed -> distinct fundamental frequency
    freq = 200 + (seed % 50) * 40  # 200 Hz, 240 Hz, ...
    t = np.arange(n, dtype=np.float32) / 16000.0
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


@pytest.mark.asyncio
async def test_replay_detected_when_same_audio_fed_twice(caplog):
    redis = _InMemoryRedis()
    detector = VoiceReplayDetector(
        redis_client=redis,
        cache_size=5,
        similarity_threshold=0.95,
        enabled=True,
    )

    samples = _fake_samples(seed=42)
    fp = compute_spectral_fingerprint(samples)

    # First call — nothing cached yet
    suspect_first = await detector.check_and_record(
        user_id="user-1", fingerprint=fp, tenant_id="tenant-x"
    )
    assert suspect_first is False

    # Second call — same fingerprint, must be flagged
    with caplog.at_level(logging.WARNING, logger="app.infrastructure.ml.voice.replay_detector"):
        suspect_second = await detector.check_and_record(
            user_id="user-1", fingerprint=fp, tenant_id="tenant-x"
        )

    assert suspect_second is True
    assert any("voice_replay_suspect" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_replay_detection_disabled_is_noop():
    redis = _InMemoryRedis()
    detector = VoiceReplayDetector(
        redis_client=redis,
        cache_size=5,
        similarity_threshold=0.95,
        enabled=False,
    )

    fp = compute_spectral_fingerprint(_fake_samples(seed=7))
    for _ in range(3):
        suspect = await detector.check_and_record(
            user_id="user-2", fingerprint=fp, tenant_id=None
        )
        assert suspect is False

    # Nothing should have been written when disabled
    assert redis._lists == {}


@pytest.mark.asyncio
async def test_different_audio_not_flagged():
    redis = _InMemoryRedis()
    detector = VoiceReplayDetector(
        redis_client=redis,
        cache_size=5,
        similarity_threshold=0.95,
        enabled=True,
    )

    fp_a = compute_spectral_fingerprint(_fake_samples(seed=1))
    fp_b = compute_spectral_fingerprint(_fake_samples(seed=999))

    await detector.check_and_record(user_id="user-3", fingerprint=fp_a)
    suspect = await detector.check_and_record(user_id="user-3", fingerprint=fp_b)
    assert suspect is False
