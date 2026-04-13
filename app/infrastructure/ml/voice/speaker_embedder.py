"""Speaker embedding extraction — numba-free MFCC + torch projection.

Replaces the Resemblyzer-based implementation which crashed on Python 3.12
due to a numba 0.65.0 / librosa @guvectorize incompatibility.

Architecture:
    1. Decode raw audio bytes → 16 kHz mono float32 PCM (via stdlib wave or pydub)
    2. Pre-emphasis + framing + Hamming window
    3. Mel-filterbank energies via pure numpy/scipy FFT (no numba)
    4. Log mel → DCT (MFCC, 40 coefficients, 80 mel bins)
    5. Aggregate statistics: per-coeff mean + std → 80-dim feature vector
    6. Fixed seeded torch.nn.Linear projection → 256-dim speaker embedding
    7. L2 normalise for cosine similarity in pgvector

The projection matrix is initialised with a fixed seed (42) so embeddings
are reproducible across restarts.  All previously enrolled voice vectors
were computed with Resemblyzer and are stored in the database; the migration
note below explains how to handle the rollover.

Migration note (for future reference):
    Resemblyzer and this embedder produce *incompatible* 256-dim vectors.
    Any user enrolled with Resemblyzer must re-enroll.  The schema and DB
    column widths are unchanged (vector(256)), so no migration SQL is needed.

Usage:
    embedder = SpeakerEmbedder()
    embedding = embedder.extract_embedding(audio_bytes, content_type="audio/wav")
    # embedding.shape == (256,), dtype float32, L2 norm == 1.0
"""

import io
import logging
import wave
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Output embedding dimension — must match pgvector column and enrolled data
VOICE_EMBEDDING_DIM = 256

# MFCC hyper-parameters
_N_MFCC = 40        # Number of cepstral coefficients kept
_N_MELS = 80        # Mel filterbank resolution
_FRAME_LEN_MS = 25  # Frame length in milliseconds
_FRAME_STEP_MS = 10  # Frame hop in milliseconds
_FFT_SIZE = 512      # Must be >= frame_len samples
_PREEMPH_COEFF = 0.97
_MEL_FMIN = 80.0
_MEL_FMAX = 7600.0

# Minimum audio duration for a reliable embedding
MIN_AUDIO_DURATION_SECS = 0.5

# Target sample rate (speaker encoder convention)
TARGET_SAMPLE_RATE = 16000

# Fixed random seed for the projection matrix
_PROJECTION_SEED = 42


class SpeakerEmbedder:
    """Extracts 256-dim speaker embeddings from audio — fully numba-free.

    The pipeline is:
        audio → MFCC (scipy FFT, no numba) → mean+std stats → torch linear → L2 norm

    Thread Safety:
        The torch projection layer is read-only after __init__, so instances
        are safe for concurrent use from multiple async tasks dispatched to
        a thread pool executor.
    """

    def __init__(self) -> None:
        """Initialise the MFCC extractor and fixed projection layer."""
        import torch

        logger.info(
            "Loading numba-free speaker embedder "
            f"(MFCC-{_N_MFCC} + Linear → {VOICE_EMBEDDING_DIM}d)..."
        )

        # Feature vector dimension: mean + std for each MFCC coefficient
        feature_dim = _N_MFCC * 2  # 80

        # Seeded projection: same weights every time → reproducible embeddings
        torch.manual_seed(_PROJECTION_SEED)
        self._proj_weight: np.ndarray = (
            torch.nn.init.kaiming_uniform_(
                torch.empty(VOICE_EMBEDDING_DIM, feature_dim)
            )
            .detach()
            .numpy()
        )  # shape (256, 80)

        self._embedding_dim = VOICE_EMBEDDING_DIM
        logger.info(
            f"Speaker embedder ready: feature_dim={feature_dim}, "
            f"output_dim={VOICE_EMBEDDING_DIM}"
        )

    # ------------------------------------------------------------------
    # Public API (same interface as the old Resemblyzer-based embedder)
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
        wav_samples = self._decode_to_wav_samples(audio_bytes, content_type)
        return self._embed(wav_samples)

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
    # Internal audio decoding helpers
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
            if duration < MIN_AUDIO_DURATION_SECS:
                raise ValueError(
                    f"Audio too short ({duration:.2f}s). "
                    f"Minimum is {MIN_AUDIO_DURATION_SECS}s."
                )

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

        duration = len(samples) / TARGET_SAMPLE_RATE
        if duration < MIN_AUDIO_DURATION_SECS:
            raise ValueError(
                f"Audio too short ({duration:.2f}s). "
                f"Minimum is {MIN_AUDIO_DURATION_SECS}s."
            )

        return samples

    # ------------------------------------------------------------------
    # Core embedding pipeline (numba-free)
    # ------------------------------------------------------------------

    def _embed(self, wav_samples: np.ndarray) -> np.ndarray:
        """Compute the 256-dim speaker embedding from 16 kHz mono PCM.

        Pipeline: pre-emphasis → framing → windowing → FFT power spectrum
                  → mel filterbank → log → DCT (MFCC) → mean+std → linear
                  projection → L2 normalise.
        """
        samples = wav_samples.astype(np.float32)

        # 1. Pre-emphasis filter
        samples = self._preemphasis(samples)

        # 2. Framing
        frames = self._frame_signal(samples)
        if frames.shape[0] == 0:
            raise ValueError(
                "Audio too short for MFCC extraction after framing. "
                "Please record at least 1 second of audio."
            )

        # 3. Hamming window + FFT power spectrum
        window = np.hamming(frames.shape[1]).astype(np.float32)
        frames = frames * window

        padded = np.zeros((frames.shape[0], _FFT_SIZE), dtype=np.float32)
        padded[:, : frames.shape[1]] = frames

        # scipy.fft.rfft — pure C, no numba
        from scipy.fft import rfft as scipy_rfft

        mag = np.abs(scipy_rfft(padded, axis=1))
        power = (1.0 / _FFT_SIZE) * (mag ** 2)  # shape (T, FFT_SIZE//2 + 1)

        # 4. Mel filterbank
        mel_filters = self._mel_filterbank()  # (n_mels, fft_bins)
        mel_energy = np.dot(power, mel_filters.T)  # (T, n_mels)
        mel_energy = np.maximum(mel_energy, np.finfo(np.float32).eps)
        log_mel = np.log(mel_energy)  # (T, n_mels)

        # 5. DCT (type-II) → MFCC
        dct_matrix = self._dct_matrix()  # (n_mfcc, n_mels)
        mfcc = np.dot(log_mel, dct_matrix.T)  # (T, n_mfcc)

        # 6. Utterance-level statistics: mean + std across time
        mu = mfcc.mean(axis=0)          # (n_mfcc,)
        std = mfcc.std(axis=0) + 1e-8   # (n_mfcc,)
        features = np.concatenate([mu, std]).astype(np.float32)  # (2*n_mfcc,)

        # 7. Fixed linear projection → 256-dim
        embedding = self._proj_weight @ features  # (256,)

        # 8. L2 normalise for cosine similarity
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm

        embedding = embedding.astype(np.float32)

        logger.debug(
            f"Speaker embedding extracted: dim={len(embedding)}, "
            f"norm={np.linalg.norm(embedding):.4f}"
        )
        return embedding

    # ------------------------------------------------------------------
    # MFCC building blocks (all pure numpy/scipy, no numba)
    # ------------------------------------------------------------------

    @staticmethod
    def _preemphasis(signal: np.ndarray, coeff: float = _PREEMPH_COEFF) -> np.ndarray:
        return np.append(signal[0], signal[1:] - coeff * signal[:-1])

    @staticmethod
    def _frame_signal(signal: np.ndarray) -> np.ndarray:
        """Split signal into overlapping frames."""
        frame_len = int(TARGET_SAMPLE_RATE * _FRAME_LEN_MS / 1000)  # 400 samples
        frame_step = int(TARGET_SAMPLE_RATE * _FRAME_STEP_MS / 1000)  # 160 samples
        sig_len = len(signal)
        num_frames = max(1, 1 + (sig_len - frame_len) // frame_step)

        # Build index matrix efficiently
        col_idx = np.arange(frame_len)
        row_idx = np.arange(num_frames) * frame_step
        # Clip to avoid out-of-bounds on short signals
        indices = row_idx[:, None] + col_idx[None, :]
        indices = np.clip(indices, 0, sig_len - 1)
        return signal[indices]

    @staticmethod
    def _mel_filterbank() -> np.ndarray:
        """Return a (n_mels, fft_bins) triangular mel filterbank matrix."""
        fft_bins = _FFT_SIZE // 2 + 1  # 257
        mel_min = 2595.0 * np.log10(1.0 + _MEL_FMIN / 700.0)
        mel_max = 2595.0 * np.log10(1.0 + _MEL_FMAX / 700.0)
        mel_points = np.linspace(mel_min, mel_max, _N_MELS + 2)
        hz_points = 700.0 * (10.0 ** (mel_points / 2595.0) - 1.0)
        bin_points = np.floor((fft_bins - 1) * 2 * hz_points / TARGET_SAMPLE_RATE).astype(int)
        bin_points = np.clip(bin_points, 0, fft_bins - 1)

        filters = np.zeros((_N_MELS, fft_bins), dtype=np.float32)
        for m in range(1, _N_MELS + 1):
            f_left = bin_points[m - 1]
            f_center = bin_points[m]
            f_right = bin_points[m + 1]
            if f_center > f_left:
                for k in range(f_left, f_center + 1):
                    filters[m - 1, k] = (k - f_left) / (f_center - f_left)
            if f_right > f_center:
                for k in range(f_center, f_right + 1):
                    filters[m - 1, k] = (f_right - k) / (f_right - f_center)
        return filters

    @staticmethod
    def _dct_matrix() -> np.ndarray:
        """Return a (n_mfcc, n_mels) orthonormal DCT-II basis matrix."""
        n = _N_MELS
        k = np.arange(_N_MFCC)[:, None]      # (n_mfcc, 1)
        m = np.arange(n)[None, :] + 0.5      # (1, n_mels)
        dct = np.cos(np.pi / n * k * m).astype(np.float32)
        # Orthonormal scaling
        dct[0, :] *= np.sqrt(1.0 / n)
        dct[1:, :] *= np.sqrt(2.0 / n)
        return dct

    # ------------------------------------------------------------------
    # Format detection
    # ------------------------------------------------------------------

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
