"""Speaker embedding extraction using Resemblyzer.

Uses the pretrained GE2E speaker encoder from Resemblyzer to produce
256-dim L2-normalised speaker embeddings suitable for cosine similarity
in pgvector.

Compatibility notes:
    - librosa >= 0.10.0 introduced @stencil + @guvectorize in core/audio.py
      and util/utils.py that crash at import time on Python 3.12 with
      numba >= 0.59 (AttributeError: 'function' object has no attribute
      'get_call_template').  NUMBA_DISABLE_JIT=1 does NOT prevent this
      because @guvectorize compiles eagerly at module load.
    - Fix: pin librosa==0.9.2 in requirements.txt.  That version has no
      stencil/guvectorize usage and imports cleanly with any numba version.
"""

import io
import logging
import wave
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Output embedding dimension — matches pgvector column and enrolled data
VOICE_EMBEDDING_DIM = 256

# Minimum audio duration for a reliable embedding
MIN_AUDIO_DURATION_SECS = 0.5

# Target sample rate (Resemblyzer convention)
TARGET_SAMPLE_RATE = 16000

# --- Voice quality metric tuning (CPU-only, deterministic) --------------------
# Effective speech reaching this many seconds earns the full duration credit.
QUALITY_TARGET_SPEECH_SECS = 3.0
# A frame counts as "speech" when its RMS is at least this fraction of the
# clip's peak frame RMS. Cheap, level-independent energy-based VAD.
QUALITY_SPEECH_REL_THRESHOLD = 0.10
# RMS window for the energy / VAD / SNR analysis (20 ms @ 16 kHz = 320 samples).
QUALITY_FRAME_SAMPLES = 320
# Loudness sweet-spot: an overall RMS at/above this (in [0,1] PCM units) is
# treated as fully loud-enough. ~ -26 dBFS. Below it the score scales linearly.
QUALITY_GOOD_RMS = 0.05
# Fraction of samples at/above this magnitude that we treat as clipping. The
# loudness sub-score is penalised once clipping exceeds a small tolerance.
QUALITY_CLIP_MAGNITUDE = 0.99
QUALITY_CLIP_TOLERANCE = 0.01  # up to 1% clipped samples is unpenalised
# SNR (dB) at/above which the noise sub-score is full; at/below the floor it's 0.
QUALITY_SNR_FULL_DB = 25.0
QUALITY_SNR_FLOOR_DB = 5.0


def _frame_rms(samples: np.ndarray, frame: int) -> np.ndarray:
    """Per-frame RMS energy for non-overlapping ``frame``-sample windows."""
    n_full = len(samples) // frame
    if n_full == 0:
        return np.array([], dtype=np.float64)
    trimmed = samples[: n_full * frame].astype(np.float64).reshape(n_full, frame)
    return np.sqrt(np.mean(np.square(trimmed), axis=1))


def compute_voice_quality_score(samples: np.ndarray) -> float:
    """Compute a deterministic 0..100 voice-enrollment quality score.

    CPU-only, no ML, no extra dependencies — derived entirely from the decoded
    16 kHz mono PCM samples (``decode_samples_from_base64``). Replaces the old
    hardcoded ``quality_score=1.0`` placeholder so the admin Enrollments table
    and downstream gates see a real signal.

    The score is the weighted blend of three bounded sub-scores:

    * **Speech duration (50%)** — fraction of the clip that is energetic enough
      to be speech (relative-RMS VAD), credited up to
      ``QUALITY_TARGET_SPEECH_SECS``. Short or silent clips score near zero.
    * **Loudness (25%)** — overall RMS mapped into a sweet spot: too quiet
      scales down linearly toward ``QUALITY_GOOD_RMS``; heavy clipping
      (fraction of |sample| >= ``QUALITY_CLIP_MAGNITUDE`` over a small
      tolerance) is penalised.
    * **SNR (25%)** — a cheap speech-vs-noise-floor estimate: median RMS of the
      loud (speech) frames over the quiet (noise) frames, in dB, mapped from
      ``QUALITY_SNR_FLOOR_DB`` (0) to ``QUALITY_SNR_FULL_DB`` (1).

    Deterministic and bounded to [0, 100]. Empty/silent input → 0.0.

    Args:
        samples: 1-D float32/float64 mono PCM in [-1, 1] at 16 kHz.

    Returns:
        Quality score in [0.0, 100.0].
    """
    if samples is None or len(samples) == 0:
        return 0.0

    samples = np.asarray(samples, dtype=np.float64)
    frames = _frame_rms(samples, QUALITY_FRAME_SAMPLES)
    if frames.size == 0:
        return 0.0

    peak_frame_rms = float(frames.max())
    if peak_frame_rms <= 0.0:
        return 0.0  # pure silence

    # --- (a) effective speech duration -----------------------------------
    speech_mask = frames >= (QUALITY_SPEECH_REL_THRESHOLD * peak_frame_rms)
    speech_secs = float(speech_mask.sum() * QUALITY_FRAME_SAMPLES) / TARGET_SAMPLE_RATE
    duration_sub = min(1.0, speech_secs / QUALITY_TARGET_SPEECH_SECS)

    # --- (b) loudness (RMS sweet-spot, clipping-penalised) ---------------
    overall_rms = float(np.sqrt(np.mean(np.square(samples))))
    loudness_sub = min(1.0, overall_rms / QUALITY_GOOD_RMS)
    clip_fraction = float(np.mean(np.abs(samples) >= QUALITY_CLIP_MAGNITUDE))
    if clip_fraction > QUALITY_CLIP_TOLERANCE:
        # Linearly drop the loudness sub-score as clipping worsens past the
        # tolerance; fully clipped (100%) → 0.
        loudness_sub *= max(0.0, 1.0 - (clip_fraction - QUALITY_CLIP_TOLERANCE))

    # --- (c) SNR estimate (speech frames vs noise-floor frames) ----------
    if speech_mask.any() and (~speech_mask).any():
        speech_level = float(np.median(frames[speech_mask]))
        noise_level = float(np.median(frames[~speech_mask]))
        if noise_level <= 1e-9:
            snr_sub = 1.0  # essentially no measurable noise floor
        else:
            snr_db = 20.0 * np.log10(max(speech_level, 1e-9) / noise_level)
            snr_sub = (snr_db - QUALITY_SNR_FLOOR_DB) / (
                QUALITY_SNR_FULL_DB - QUALITY_SNR_FLOOR_DB
            )
            snr_sub = max(0.0, min(1.0, snr_sub))
    else:
        # No separable noise floor (all frames speech, or all silence already
        # handled above). Neutral SNR contribution.
        snr_sub = 0.5

    score = 100.0 * (0.50 * duration_sub + 0.25 * loudness_sub + 0.25 * snr_sub)
    return float(max(0.0, min(100.0, score)))


class SpeakerEmbedder:
    """Extracts 256-dim speaker embeddings from audio using Resemblyzer.

    The Resemblyzer GE2E encoder is a pretrained LSTM trained on thousands
    of speakers.  It produces speaker-discriminative embeddings: two
    utterances from the same speaker have high cosine similarity (~0.85+)
    while utterances from different speakers are distinctly lower (~0.3-0.6).

    Thread Safety:
        VoiceEncoder is read-only after __init__, so instances are safe for
        concurrent use from multiple async tasks dispatched to a thread pool.
    """

    def __init__(self) -> None:
        """Load the pretrained Resemblyzer GE2E encoder."""
        from resemblyzer import VoiceEncoder

        logger.info("Loading Resemblyzer GE2E speaker encoder...")
        self._encoder = VoiceEncoder()
        self._embedding_dim = VOICE_EMBEDDING_DIM
        logger.info(
            f"Resemblyzer encoder ready: output_dim={VOICE_EMBEDDING_DIM}"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def embedding_dim(self) -> int:
        """Return the embedding dimensionality."""
        return self._embedding_dim

    def extract_embedding(
        self,
        audio_bytes: bytes,
        content_type: Optional[str] = None,
    ) -> np.ndarray:
        """Extract a speaker embedding from raw audio bytes.

        Args:
            audio_bytes: Raw audio file content (WAV or WebM/Opus).
            content_type: MIME type hint (e.g. "audio/webm", "audio/wav").

        Returns:
            numpy array of shape (256,), dtype float32, L2 norm ≈ 1.0.

        Raises:
            ValueError: If audio is too short or cannot be decoded.
        """
        from resemblyzer import preprocess_wav

        wav_samples = self._decode_to_wav_samples(audio_bytes, content_type)

        duration = len(wav_samples) / TARGET_SAMPLE_RATE
        if duration < MIN_AUDIO_DURATION_SECS:
            raise ValueError(
                f"Audio too short ({duration:.2f}s). "
                f"Minimum is {MIN_AUDIO_DURATION_SECS}s."
            )

        wav = preprocess_wav(wav_samples, source_sr=TARGET_SAMPLE_RATE)

        if len(wav) == 0:
            raise ValueError(
                "Audio contains no speech (VAD removed all frames). "
                "Please record at least 1 second of clear speech."
            )

        embedding = self._encoder.embed_utterance(wav)
        return embedding.astype(np.float32)

    def extract_embedding_from_base64(self, base64_data: str) -> np.ndarray:
        """Extract a speaker embedding from a base64-encoded audio string.

        The base64 string may optionally include a data URI prefix
        (e.g. "data:audio/webm;base64,...").

        Args:
            base64_data: Base64-encoded audio.

        Returns:
            numpy array of shape (256,), dtype float32.
        """
        audio_bytes, content_type = self._decode_base64(base64_data)
        return self.extract_embedding(audio_bytes, content_type)

    def decode_samples_from_base64(self, base64_data: str) -> np.ndarray:
        """Decode base64 audio to a 16 kHz mono float32 PCM array.

        Exposes the same decode path used by ``extract_embedding`` so callers
        that need raw samples (e.g. the voice replay-attack fingerprint) can
        reuse the identical decoding without duplicating format detection.

        Args:
            base64_data: Base64-encoded audio (optionally with a data URI
                prefix such as "data:audio/webm;base64,...").

        Returns:
            1-D float32 numpy array of mono PCM samples at 16 kHz.
        """
        audio_bytes, content_type = self._decode_base64(base64_data)
        return self._decode_to_wav_samples(audio_bytes, content_type)

    @staticmethod
    def _decode_base64(base64_data: str) -> "tuple[bytes, Optional[str]]":
        """Strip an optional data-URI prefix and base64-decode the payload."""
        import base64

        content_type: Optional[str] = None

        if base64_data.startswith("data:"):
            header, base64_data = base64_data.split(",", 1)
            content_type = header.split(":")[1].split(";")[0]

        return base64.b64decode(base64_data), content_type

    # ------------------------------------------------------------------
    # Audio decoding helpers
    # ------------------------------------------------------------------

    def _decode_to_wav_samples(
        self, audio_bytes: bytes, content_type: Optional[str]
    ) -> np.ndarray:
        """Decode audio bytes to a 16 kHz mono float32 numpy array."""
        from pydub import AudioSegment

        try:
            fmt = self._guess_format(audio_bytes, content_type)
            logger.debug(
                f"Decoding audio: content_type={content_type}, detected_fmt={fmt}"
            )

            if fmt == "wav":
                try:
                    return self._load_wav_direct(audio_bytes)
                except Exception:
                    pass  # Fall through to pydub

            seg = (
                AudioSegment.from_file(io.BytesIO(audio_bytes), format=fmt)
                .set_channels(1)
                .set_frame_rate(TARGET_SAMPLE_RATE)
                .set_sample_width(2)
            )

            samples = np.array(seg.get_array_of_samples(), dtype=np.float32)
            samples = samples / 32768.0  # int16 → float32 [-1, 1]

            duration = len(samples) / TARGET_SAMPLE_RATE
            logger.debug(
                f"Audio decoded: {duration:.2f}s, {len(samples)} samples "
                f"@ {TARGET_SAMPLE_RATE}Hz"
            )
            return samples

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to decode audio: {e}") from e

    def _load_wav_direct(self, audio_bytes: bytes) -> np.ndarray:
        """Load a WAV file directly without pydub/ffmpeg."""
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            frame_rate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

        if sample_width == 2:
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        elif sample_width == 4:
            samples = (
                np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
            )
        else:
            raise ValueError(f"Unsupported WAV sample width: {sample_width}")

        if n_channels > 1:
            samples = samples.reshape(-1, n_channels).mean(axis=1)

        if frame_rate != TARGET_SAMPLE_RATE:
            from scipy.signal import resample as scipy_resample

            target_len = int(len(samples) * TARGET_SAMPLE_RATE / frame_rate)
            samples = scipy_resample(samples, target_len).astype(np.float32)

        return samples

    @staticmethod
    def _guess_format(audio_bytes: bytes, content_type: Optional[str]) -> str:
        """Guess audio format from content type or magic bytes."""
        if content_type:
            ct = content_type.lower()
            if "webm" in ct:
                return "webm"
            if "ogg" in ct or "opus" in ct:
                return "ogg"
            if "wav" in ct or "wave" in ct:
                return "wav"
            if "mp3" in ct or "mpeg" in ct:
                return "mp3"
            if "flac" in ct:
                return "flac"

        if audio_bytes[:4] == b"RIFF":
            return "wav"
        if audio_bytes[:4] == b"fLaC":
            return "flac"
        if audio_bytes[:4] == b"\x1aE\xdf\xa3":
            return "webm"
        if audio_bytes[:4] == b"OggS":
            return "ogg"

        return "webm"
