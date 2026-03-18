"""Basic audio analyzer for proctoring.

Analyzes audio streams for:
- Voice activity detection
- Multiple speaker detection
- Suspicious audio patterns

Uses numpy-based analysis with optional webrtcvad/librosa enhancements.
"""

import logging
from datetime import datetime
from typing import List, Tuple

import numpy as np

from app.domain.entities.proctor_analysis import AudioAnalysisResult
from app.domain.interfaces.audio_analyzer import IAudioAnalyzer

logger = logging.getLogger(__name__)

# Audio analysis constants
DEFAULT_SAMPLE_RATE = 16000
FRAME_DURATION_MS = 30
VOICE_FREQ_LOW = 85
VOICE_FREQ_HIGH = 3000


class BasicAudioAnalyzer(IAudioAnalyzer):
    """Audio analyzer using basic signal processing.

    Analyzes audio for:
    1. Voice Activity Detection (VAD) using energy and ZCR
    2. Speaker count estimation using pitch variation
    3. Suspicious patterns (background voices, audio playback)
    """

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        energy_threshold: float = 0.01,
        zcr_threshold: float = 0.1,
        vad_threshold: float = 0.5,
    ) -> None:
        """Initialize audio analyzer.

        Args:
            sample_rate: Audio sample rate in Hz
            energy_threshold: Minimum energy for voice detection
            zcr_threshold: Zero-crossing rate threshold
            vad_threshold: Overall VAD confidence threshold
        """
        self._sample_rate = sample_rate
        self._energy_threshold = energy_threshold
        self._zcr_threshold = zcr_threshold
        self._vad_threshold = vad_threshold

        # Optional enhanced libraries
        self._webrtcvad = None
        self._has_scipy = False

        self._init_optional_libs()

        logger.info(
            f"BasicAudioAnalyzer initialized: "
            f"sample_rate={sample_rate}, "
            f"webrtcvad={'available' if self._webrtcvad else 'not available'}"
        )

    def _init_optional_libs(self) -> None:
        """Initialize optional audio libraries."""
        # Try webrtcvad for better VAD
        try:
            import webrtcvad
            self._webrtcvad = webrtcvad.Vad(2)  # Aggressiveness 0-3
            logger.info("webrtcvad available for enhanced VAD")
        except ImportError:
            logger.debug("webrtcvad not installed, using basic VAD")

        # Check for scipy
        try:
            import scipy.signal
            self._has_scipy = True
        except ImportError:
            logger.debug("scipy not installed, using basic analysis")

    async def analyze(
        self,
        audio_data: np.ndarray,
        session_id,
    ) -> AudioAnalysisResult:
        """Analyze audio segment for proctoring.

        Args:
            audio_data: Audio samples as float array (-1 to 1)
            session_id: Session being analyzed

        Returns:
            AudioAnalysisResult with analysis results
        """
        timestamp = datetime.utcnow()

        # Normalize audio
        audio = self._normalize_audio(audio_data)

        # Calculate audio level
        audio_level_db = self._calculate_db_level(audio)

        # Voice Activity Detection
        has_voice, vad_confidence = self._detect_voice_activity(audio)

        # Speaker count estimation
        speaker_count = 0
        if has_voice:
            speaker_count = self._estimate_speaker_count(audio)

        # Check for suspicious patterns
        is_suspicious = self._detect_suspicious_patterns(
            audio, speaker_count, audio_level_db
        )

        # Overall confidence
        confidence = vad_confidence

        logger.debug(
            f"Audio analysis: voice={has_voice}, speakers={speaker_count}, "
            f"suspicious={is_suspicious}, level={audio_level_db:.1f}dB"
        )

        return AudioAnalysisResult(
            session_id=session_id,
            timestamp=timestamp,
            has_voice_activity=has_voice,
            speaker_count=speaker_count,
            confidence=round(confidence, 3),
            is_suspicious=is_suspicious,
            audio_level_db=round(audio_level_db, 1),
        )

    def _normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        """Normalize audio to float range."""
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype == np.int32:
            audio = audio.astype(np.float32) / 2147483648.0

        # Ensure mono
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)

        return audio.astype(np.float32)

    def _calculate_db_level(self, audio: np.ndarray) -> float:
        """Calculate audio level in dB."""
        rms = np.sqrt(np.mean(audio ** 2))
        if rms < 1e-10:
            return -100.0
        return 20 * np.log10(rms)

    def _detect_voice_activity(
        self,
        audio: np.ndarray,
    ) -> Tuple[bool, float]:
        """Detect voice activity in audio.

        Returns:
            (has_voice, confidence)
        """
        # Use webrtcvad if available
        if self._webrtcvad is not None:
            return self._vad_webrtc(audio)

        # Basic energy + ZCR based VAD
        return self._vad_basic(audio)

    def _vad_webrtc(self, audio: np.ndarray) -> Tuple[bool, float]:
        """Voice detection using webrtcvad."""
        # Convert to 16-bit PCM
        pcm = (audio * 32767).astype(np.int16).tobytes()

        # Process in frames
        frame_size = int(self._sample_rate * FRAME_DURATION_MS / 1000)
        frame_bytes = frame_size * 2  # 16-bit

        voice_frames = 0
        total_frames = 0

        for i in range(0, len(pcm) - frame_bytes, frame_bytes):
            frame = pcm[i:i + frame_bytes]
            try:
                if self._webrtcvad.is_speech(frame, self._sample_rate):
                    voice_frames += 1
                total_frames += 1
            except Exception:
                continue

        if total_frames == 0:
            return False, 0.0

        voice_ratio = voice_frames / total_frames
        has_voice = voice_ratio > self._vad_threshold

        return has_voice, voice_ratio

    def _vad_basic(self, audio: np.ndarray) -> Tuple[bool, float]:
        """Basic voice detection using energy and ZCR."""
        # Frame size (30ms)
        frame_size = int(self._sample_rate * FRAME_DURATION_MS / 1000)

        voice_frames = 0
        total_frames = 0

        for i in range(0, len(audio) - frame_size, frame_size):
            frame = audio[i:i + frame_size]

            # Energy
            energy = np.mean(frame ** 2)

            # Zero-crossing rate
            zcr = np.mean(np.abs(np.diff(np.sign(frame)))) / 2

            # Voice typically has moderate energy and lower ZCR than noise
            is_voice_frame = (
                energy > self._energy_threshold and
                zcr < self._zcr_threshold
            )

            if is_voice_frame:
                voice_frames += 1
            total_frames += 1

        if total_frames == 0:
            return False, 0.0

        voice_ratio = voice_frames / total_frames
        has_voice = voice_ratio > self._vad_threshold

        return has_voice, voice_ratio

    def _estimate_speaker_count(self, audio: np.ndarray) -> int:
        """Estimate number of speakers in audio.

        Uses pitch variation analysis as a simple heuristic.
        For accurate speaker diarization, use pyannote.audio.
        """
        # Extract pitch using autocorrelation
        pitches = self._extract_pitches(audio)

        if len(pitches) < 10:
            return 1 if len(pitches) > 0 else 0

        # Analyze pitch distribution
        pitch_std = np.std(pitches)
        pitch_range = np.max(pitches) - np.min(pitches)

        # Single speaker: relatively stable pitch
        # Multiple speakers: higher pitch variation
        if pitch_std < 20 and pitch_range < 100:
            return 1
        elif pitch_std < 40 and pitch_range < 200:
            # Could be 1 speaker with varied speech or 2 speakers
            return 1
        else:
            # High variation suggests multiple speakers
            # This is a rough heuristic
            estimated = min(3, int(pitch_std / 30) + 1)
            return estimated

    def _extract_pitches(self, audio: np.ndarray) -> List[float]:
        """Extract pitch values from audio using autocorrelation."""
        frame_size = int(self._sample_rate * 0.03)  # 30ms
        hop_size = int(self._sample_rate * 0.01)   # 10ms hop

        pitches = []

        for i in range(0, len(audio) - frame_size, hop_size):
            frame = audio[i:i + frame_size]

            # Skip low energy frames
            if np.mean(frame ** 2) < self._energy_threshold:
                continue

            # Autocorrelation
            corr = np.correlate(frame, frame, mode='full')
            corr = corr[len(corr) // 2:]

            # Find first peak after initial decline
            # This corresponds to the pitch period
            min_period = int(self._sample_rate / VOICE_FREQ_HIGH)
            max_period = int(self._sample_rate / VOICE_FREQ_LOW)

            if max_period >= len(corr):
                continue

            search_region = corr[min_period:max_period]
            if len(search_region) == 0:
                continue

            peak_idx = np.argmax(search_region) + min_period

            # Convert to frequency
            if peak_idx > 0:
                pitch = self._sample_rate / peak_idx
                if VOICE_FREQ_LOW <= pitch <= VOICE_FREQ_HIGH:
                    pitches.append(pitch)

        return pitches

    def _detect_suspicious_patterns(
        self,
        audio: np.ndarray,
        speaker_count: int,
        audio_level_db: float,
    ) -> bool:
        """Detect suspicious audio patterns.

        Suspicious patterns include:
        - Multiple speakers (possible external help)
        - Unusual background audio
        - Audio playback artifacts
        """
        # Multiple speakers is suspicious
        if speaker_count > 1:
            return True

        # Check for playback artifacts (if scipy available)
        if self._has_scipy:
            if self._detect_playback_artifacts(audio):
                return True

        # Very loud or very quiet audio in presence of voice
        if speaker_count > 0:
            if audio_level_db > -10 or audio_level_db < -50:
                return True

        return False

    def _detect_playback_artifacts(self, audio: np.ndarray) -> bool:
        """Detect audio playback artifacts.

        Playback through speakers and re-recorded can show:
        - Specific frequency dropouts
        - Room acoustics artifacts
        """
        try:
            from scipy import signal

            # Compute spectrogram
            f, t, Sxx = signal.spectrogram(
                audio,
                self._sample_rate,
                nperseg=256,
                noverlap=128,
            )

            # Look for unusual frequency patterns
            # Playback often shows specific resonances or dropouts

            # Calculate frequency band energies
            low_band = np.mean(Sxx[(f >= 100) & (f < 500), :])
            mid_band = np.mean(Sxx[(f >= 500) & (f < 2000), :])
            high_band = np.mean(Sxx[(f >= 2000) & (f < 4000), :])

            # Unusual ratio could indicate playback
            if high_band > 0 and low_band > 0:
                ratio = mid_band / (low_band + high_band)
                # Very narrow or very wide mid-band is suspicious
                if ratio < 0.1 or ratio > 10:
                    return True

            return False

        except Exception as e:
            logger.debug(f"Playback detection error: {e}")
            return False

    def is_available(self) -> bool:
        """Check if audio analyzer is available."""
        return True  # Basic analysis always available

    def get_sample_rate(self) -> int:
        """Get expected sample rate."""
        return self._sample_rate
