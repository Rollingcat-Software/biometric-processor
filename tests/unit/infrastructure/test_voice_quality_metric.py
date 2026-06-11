"""Unit tests for compute_voice_quality_score (P1-3).

The voice enrollment quality metric is CPU-only and deterministic, derived
entirely from decoded 16 kHz mono PCM samples (no ML, no extra deps). These
tests pin the contract:

    * silence / too-short input  -> low (near-zero) score
    * a clean, loud, sufficiently long speech-like clip -> high score
    * the output is always bounded to [0, 100]
    * the function is deterministic (same input -> same output)
"""

import numpy as np

from app.infrastructure.ml.voice.speaker_embedder import (
    TARGET_SAMPLE_RATE,
    compute_voice_quality_score,
)


def _tone(secs: float, freq: float = 220.0, amplitude: float = 0.3) -> np.ndarray:
    """A clean sine tone — stands in for sustained, loud, low-noise speech."""
    n = int(secs * TARGET_SAMPLE_RATE)
    t = np.arange(n, dtype=np.float64) / TARGET_SAMPLE_RATE
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def _speech_then_silence(speech_secs: float, silence_secs: float) -> np.ndarray:
    """A loud tone followed by a near-silent (low-noise) tail.

    Gives the metric separable speech vs noise-floor frames so the SNR
    sub-score is exercised.
    """
    speech = _tone(speech_secs, amplitude=0.3)
    n_sil = int(silence_secs * TARGET_SAMPLE_RATE)
    rng = np.random.default_rng(0)
    silence = (1e-4 * rng.standard_normal(n_sil)).astype(np.float32)
    return np.concatenate([speech, silence])


def test_empty_input_scores_zero():
    assert compute_voice_quality_score(np.array([], dtype=np.float32)) == 0.0


def test_pure_silence_scores_low():
    silence = np.zeros(int(3 * TARGET_SAMPLE_RATE), dtype=np.float32)
    assert compute_voice_quality_score(silence) < 5.0


def test_too_short_clip_scores_low():
    # 0.3s of speech — well under the 3s target, so the 50%-weight duration
    # sub-score is small and drags the total down.
    score = compute_voice_quality_score(_tone(0.3))
    assert score < 50.0


def test_good_clip_scores_high():
    # 4s loud clean tone + a quiet tail: long enough (duration saturated),
    # loud enough, and high SNR -> should land in the upper range.
    score = compute_voice_quality_score(_speech_then_silence(4.0, 1.0))
    assert score >= 75.0
    assert score <= 100.0


def test_quiet_clip_scores_lower_than_loud():
    quiet = compute_voice_quality_score(_tone(4.0, amplitude=0.005))
    loud = compute_voice_quality_score(_tone(4.0, amplitude=0.3))
    assert quiet < loud


def test_score_is_bounded():
    # An aggressively clipped, max-amplitude square-ish wave must still be in range.
    n = int(4 * TARGET_SAMPLE_RATE)
    clipped = np.ones(n, dtype=np.float32)
    clipped[1::2] = -1.0
    score = compute_voice_quality_score(clipped)
    assert 0.0 <= score <= 100.0


def test_deterministic():
    clip = _speech_then_silence(3.0, 1.0)
    assert compute_voice_quality_score(clip) == compute_voice_quality_score(clip)
