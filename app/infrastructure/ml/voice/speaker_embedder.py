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
        import base64

        content_type: Optional[str] = None

        if base64_data.startswith("data:"):
            header, base64_data = base64_data.split(",", 1)
            content_type = header.split(":")[1].split(";")[0]

        audio_bytes = base64.b64decode(base64_data)
        return self.extract_embedding(audio_bytes, content_type)

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
