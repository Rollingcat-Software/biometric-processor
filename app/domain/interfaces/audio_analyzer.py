"""Audio analyzer interface."""

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.proctor_analysis import AudioAnalysisResult


class IAudioAnalyzer(ABC):
    """Interface for audio analysis."""

    @abstractmethod
    async def analyze(
        self,
        audio_data: bytes,
        sample_rate: int,
        session_id: UUID,
    ) -> AudioAnalysisResult:
        """Analyze audio chunk.

        Args:
            audio_data: Raw audio bytes (PCM format)
            sample_rate: Audio sample rate
            session_id: Session being analyzed

        Returns:
            AudioAnalysisResult with voice activity and speaker count
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if audio analyzer is available."""
        pass
