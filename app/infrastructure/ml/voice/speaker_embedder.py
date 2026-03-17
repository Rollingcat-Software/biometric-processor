"""Speaker embedding extraction using Resemblyzer.

Resemblyzer provides a pretrained speaker encoder that produces
256-dimensional speaker embeddings from audio. It is lightweight (~50MB)
and runs efficiently on CPU.

Usage:
    embedder = SpeakerEmbedder()
    embedding = embedder.extract_embedding(audio_bytes, content_type="audio/webm")
"""

import io
import logging
import tempfile
import wave
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Resemblyzer embedding dimension (fixed by the pretrained model)
VOICE_EMBEDDING_DIM = 256

# Minimum audio duration in seconds for reliable embedding
MIN_AUDIO_DURATION_SECS = 0.5

# Target sample rate for Resemblyzer
TARGET_SAMPLE_RATE = 16000


class SpeakerEmbedder:
    """Extracts speaker embeddings from audio using Resemblyzer.

    The pretrained encoder (GE2E loss on LibriSpeech + VoxCeleb) produces
    a 256-dimensional vector that captures speaker identity, regardless of
    what is being said.

    Thread Safety:
        The encoder is loaded once at init and is read-only during inference,
        so it is safe for concurrent use from multiple async tasks dispatched
        to a thread pool.
    """

    def __init__(self) -> None:
        """Load the Resemblyzer voice encoder model."""
        logger.info("Loading Resemblyzer speaker encoder...")
        from resemblyzer import VoiceEncoder

        self._encoder = VoiceEncoder(device="cpu")
        self._embedding_dim = VOICE_EMBEDDING_DIM
        logger.info(
            f"Resemblyzer speaker encoder loaded (dim={self._embedding_dim})"
        )

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
                If None, attempts auto-detection.

        Returns:
            numpy array of shape (256,) — the speaker embedding.

        Raises:
            ValueError: If audio is too short or cannot be decoded.
        """
        wav_samples = self._decode_to_wav_samples(audio_bytes, content_type)
        return self._embed(wav_samples)

    def extract_embedding_from_base64(self, base64_data: str) -> np.ndarray:
        """Extract a speaker embedding from a base64-encoded audio string.

        The base64 string may optionally include a data URI prefix
        (e.g. "data:audio/webm;base64,...").

        Args:
            base64_data: Base64-encoded audio.

        Returns:
            numpy array of shape (256,).
        """
        import base64

        content_type = None

        # Strip data URI prefix if present
        if base64_data.startswith("data:"):
            header, base64_data = base64_data.split(",", 1)
            # e.g. "data:audio/webm;base64"
            content_type = header.split(":")[1].split(";")[0]

        audio_bytes = base64.b64decode(base64_data)
        return self.extract_embedding(audio_bytes, content_type)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _decode_to_wav_samples(
        self, audio_bytes: bytes, content_type: Optional[str]
    ) -> np.ndarray:
        """Decode audio bytes to a 16 kHz mono float32 numpy array.

        Uses pydub (with ffmpeg backend) to handle format conversion.
        Falls back to direct WAV parsing for plain WAV files.
        """
        from pydub import AudioSegment

        try:
            # Determine format hint for pydub
            fmt = self._guess_format(audio_bytes, content_type)
            logger.debug(f"Decoding audio: content_type={content_type}, detected_fmt={fmt}")

            if fmt == "wav":
                # Try direct WAV load first (faster, no ffmpeg needed)
                try:
                    return self._load_wav_direct(audio_bytes)
                except Exception:
                    pass  # Fall through to pydub

            # Use pydub + ffmpeg for all other formats (WebM, Opus, OGG, etc.)
            seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format=fmt)
            seg = seg.set_channels(1).set_frame_rate(TARGET_SAMPLE_RATE).set_sample_width(2)

            samples = np.array(seg.get_array_of_samples(), dtype=np.float32)
            samples = samples / 32768.0  # int16 -> float32 [-1, 1]

            duration = len(samples) / TARGET_SAMPLE_RATE
            if duration < MIN_AUDIO_DURATION_SECS:
                raise ValueError(
                    f"Audio too short ({duration:.2f}s). "
                    f"Minimum is {MIN_AUDIO_DURATION_SECS}s."
                )

            logger.debug(
                f"Audio decoded: {duration:.2f}s, {len(samples)} samples @ {TARGET_SAMPLE_RATE}Hz"
            )
            return samples

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to decode audio: {e}") from e

    def _load_wav_direct(self, audio_bytes: bytes) -> np.ndarray:
        """Load a WAV file directly without pydub/ffmpeg."""
        import struct

        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            frame_rate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

        if sample_width == 2:
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        elif sample_width == 4:
            samples = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            raise ValueError(f"Unsupported WAV sample width: {sample_width}")

        # Convert to mono if stereo
        if n_channels > 1:
            samples = samples.reshape(-1, n_channels).mean(axis=1)

        # Resample to 16kHz if needed
        if frame_rate != TARGET_SAMPLE_RATE:
            from scipy.signal import resample

            target_len = int(len(samples) * TARGET_SAMPLE_RATE / frame_rate)
            samples = resample(samples, target_len).astype(np.float32)

        duration = len(samples) / TARGET_SAMPLE_RATE
        if duration < MIN_AUDIO_DURATION_SECS:
            raise ValueError(
                f"Audio too short ({duration:.2f}s). "
                f"Minimum is {MIN_AUDIO_DURATION_SECS}s."
            )

        return samples

    def _embed(self, wav_samples: np.ndarray) -> np.ndarray:
        """Run the Resemblyzer encoder on preprocessed samples."""
        from resemblyzer import preprocess_wav

        # Resemblyzer's preprocess_wav expects float32 mono @ 16kHz
        # It applies voice activity detection internally
        processed = preprocess_wav(wav_samples, source_sr=TARGET_SAMPLE_RATE)

        if len(processed) < int(TARGET_SAMPLE_RATE * MIN_AUDIO_DURATION_SECS):
            raise ValueError(
                "Not enough speech detected in audio after VAD preprocessing. "
                "Please record a longer sample with clear speech."
            )

        embedding = self._encoder.embed_utterance(processed)

        # Normalize to unit vector for cosine similarity
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        logger.debug(
            f"Speaker embedding extracted: dim={len(embedding)}, norm={np.linalg.norm(embedding):.4f}"
        )
        return embedding.astype(np.float32)

    @staticmethod
    def _guess_format(
        audio_bytes: bytes, content_type: Optional[str]
    ) -> str:
        """Guess audio format from content type or magic bytes."""
        # Check content type first
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

        # Fall back to magic bytes
        if audio_bytes[:4] == b"RIFF":
            return "wav"
        if audio_bytes[:4] == b"fLaC":
            return "flac"
        if audio_bytes[:4] == b"\x1aE\xdf\xa3":  # EBML header (WebM/MKV)
            return "webm"
        if audio_bytes[:4] == b"OggS":
            return "ogg"

        # Default to webm (most common from browser MediaRecorder)
        return "webm"
