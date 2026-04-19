"""Voice replay-attack detection (log-only skeleton).

ML-H4 (Audit 2026-04-19): implements the D2/D4 replay-detection skeleton that
was previously only present in docstrings. A spectral fingerprint is derived
from the incoming audio and compared against the last N fingerprints cached
per-user in Redis (LRU). When cosine similarity on the fingerprint exceeds
``VOICE_REPLAY_SIMILARITY_THRESHOLD`` (default 0.95) the request is flagged as
a replay suspect.

Behaviour:
    * Initially **log-only**: a structured log line ``voice_replay_suspect``
      is emitted and a Prometheus counter incremented; the request is NOT
      blocked.
    * Gated by ``settings.VOICE_REPLAY_DETECTION_ENABLED`` (default False).
    * If Redis is unreachable the detector degrades silently — an auth-path
      dependency on Redis must not break voice verification.

The fingerprint used here is an MFCC-style Mel-spectrogram summary reduced to
a fixed-size vector so that different-length utterances can be compared via
cosine similarity. We purposely avoid importing librosa at module load to
keep this file import-safe in test environments.
"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)

try:  # optional dependency — counter is best-effort
    from prometheus_client import Counter as _Counter

    _REPLAY_SUSPECT_COUNTER = _Counter(
        "voice_replay_suspect_total",
        "Number of voice verification requests flagged as replay suspects",
        ["tenant"],
    )
except Exception:  # pragma: no cover — prometheus_client missing
    _REPLAY_SUSPECT_COUNTER = None


# Length of the compact spectral fingerprint (fixed-size vector for cosine).
_FINGERPRINT_DIM = 128

# Redis key template — one LRU list per user.
_REDIS_KEY_TEMPLATE = "voice:replay:{user_id}"


def compute_spectral_fingerprint(
    samples: np.ndarray,
    sample_rate: int = 16000,
) -> np.ndarray:
    """Compute a compact spectral fingerprint from PCM float32 samples.

    The fingerprint is an STFT magnitude spectrum averaged over time and
    reduced to ``_FINGERPRINT_DIM`` bins. L2-normalised so that cosine
    similarity reduces to a dot product.

    Args:
        samples: Mono float32 PCM in [-1, 1].
        sample_rate: Sample rate in Hz (unused today, reserved for Mel scaling).

    Returns:
        1-D float32 numpy array of length ``_FINGERPRINT_DIM``, L2-normalised.
    """
    if samples.size == 0:
        return np.zeros(_FINGERPRINT_DIM, dtype=np.float32)

    # Simple non-windowed STFT via np.fft on overlapping frames.
    frame_size = 512
    hop = 256
    if samples.size < frame_size:
        # Short audio — pad
        padded = np.zeros(frame_size, dtype=np.float32)
        padded[: samples.size] = samples
        samples = padded

    # Build frames
    n_frames = 1 + (samples.size - frame_size) // hop
    if n_frames <= 0:
        n_frames = 1
    frames = np.stack(
        [
            samples[i * hop : i * hop + frame_size]
            for i in range(n_frames)
        ]
    )
    # Hann window
    window = np.hanning(frame_size).astype(np.float32)
    frames = frames * window

    # Magnitude spectrum (rfft -> bins of size frame_size/2 + 1 == 257)
    spec = np.abs(np.fft.rfft(frames, axis=1)).astype(np.float32)
    # Average across time
    avg = spec.mean(axis=0)

    # Reduce to _FINGERPRINT_DIM bins by bucket-averaging
    if avg.size != _FINGERPRINT_DIM:
        bucket = avg.size / _FINGERPRINT_DIM
        reduced = np.array(
            [
                avg[int(i * bucket) : int((i + 1) * bucket)].mean()
                for i in range(_FINGERPRINT_DIM)
            ],
            dtype=np.float32,
        )
    else:
        reduced = avg

    # L2 normalise
    norm = np.linalg.norm(reduced)
    if norm > 0:
        reduced = reduced / norm
    return reduced.astype(np.float32)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    if a.size != b.size:
        return 0.0
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class VoiceReplayDetector:
    """Log-only voice replay detector backed by a Redis LRU cache.

    The cache stores the last ``cache_size`` fingerprints per user as JSON-
    encoded float arrays. A cache miss or Redis error never blocks the
    request — replay detection is strictly additive.
    """

    def __init__(
        self,
        redis_client=None,
        cache_size: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        # Lazy settings import so tests can construct the detector without
        # a full app config.
        from app.core.config import settings

        self._redis = redis_client
        self._cache_size = (
            cache_size
            if cache_size is not None
            else int(settings.VOICE_REPLAY_CACHE_SIZE)
        )
        self._threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else float(settings.VOICE_REPLAY_SIMILARITY_THRESHOLD)
        )
        self._enabled = (
            enabled
            if enabled is not None
            else bool(settings.VOICE_REPLAY_DETECTION_ENABLED)
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def check_and_record(
        self,
        user_id: str,
        fingerprint: np.ndarray,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """Compare fingerprint against cached ones and record it.

        Returns:
            True if the incoming fingerprint is a suspected replay (cosine
            similarity > threshold vs any cached one), False otherwise. The
            return value is **advisory** — callers today do not block on it.
        """
        if not self._enabled:
            return False

        key = _REDIS_KEY_TEMPLATE.format(user_id=user_id)
        cached = await self._load_cache(key)

        suspect = False
        best_sim = 0.0
        for prior in cached:
            sim = _cosine(fingerprint, prior)
            if sim > best_sim:
                best_sim = sim
            if sim >= self._threshold:
                suspect = True
                # Do not break — we want the max-similarity for logging.

        if suspect:
            logger.warning(
                "voice_replay_suspect user_id=%s tenant_id=%s similarity=%.4f "
                "threshold=%.2f",
                user_id,
                tenant_id or "-",
                best_sim,
                self._threshold,
            )
            if _REPLAY_SUSPECT_COUNTER is not None:
                try:
                    _REPLAY_SUSPECT_COUNTER.labels(tenant=tenant_id or "unknown").inc()
                except Exception:
                    pass

        # Append current fingerprint to cache (LRU-style trim)
        await self._push_cache(key, fingerprint)
        return suspect

    async def _load_cache(self, key: str) -> List[np.ndarray]:
        if self._redis is None:
            return []
        try:
            raw = await self._redis.lrange(key, 0, self._cache_size - 1)
        except Exception as exc:  # Redis unreachable — degrade silently
            logger.debug("voice replay cache unavailable: %s", exc)
            return []
        out: List[np.ndarray] = []
        for item in raw or []:
            try:
                data = item.decode("utf-8") if isinstance(item, bytes) else item
                arr = np.array(json.loads(data), dtype=np.float32)
                out.append(arr)
            except Exception:
                continue
        return out

    async def _push_cache(self, key: str, fingerprint: np.ndarray) -> None:
        if self._redis is None:
            return
        try:
            payload = json.dumps(fingerprint.tolist())
            await self._redis.lpush(key, payload)
            await self._redis.ltrim(key, 0, self._cache_size - 1)
        except Exception as exc:
            logger.debug("voice replay cache write failed: %s", exc)
