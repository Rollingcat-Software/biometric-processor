"""DeepFace-based demographics analyzer implementation."""

import logging
from typing import Dict, List

import numpy as np
from deepface import DeepFace

from app.domain.entities.demographics import (
    AgeEstimate,
    DemographicsResult,
    EmotionEstimate,
    GenderEstimate,
    RaceEstimate,
)
from app.domain.exceptions.feature_errors import DemographicsError, DemographicsModelError

logger = logging.getLogger(__name__)


class DeepFaceDemographicsAnalyzer:
    """Demographics analyzer using DeepFace.

    Analyzes age, gender, and optionally race and emotion from face images.
    """

    def __init__(
        self,
        include_race: bool = False,
        include_emotion: bool = True,
    ) -> None:
        """Initialize DeepFace demographics analyzer.

        Args:
            include_race: Whether to include race estimation
            include_emotion: Whether to include emotion analysis
        """
        self._include_race = include_race
        self._include_emotion = include_emotion
        logger.info(
            f"DeepFaceDemographicsAnalyzer initialized: "
            f"race={include_race}, emotion={include_emotion}"
        )

    def analyze(self, image: np.ndarray) -> DemographicsResult:
        """Analyze demographics from face image.

        Args:
            image: Face image as numpy array (RGB format)

        Returns:
            DemographicsResult with demographics data

        Raises:
            DemographicsError: If analysis fails
        """
        logger.debug("Starting demographics analysis")

        try:
            # Build actions list
            actions = ["age", "gender"]
            if self._include_race:
                actions.append("race")
            if self._include_emotion:
                actions.append("emotion")

            # Analyze with DeepFace
            results = DeepFace.analyze(
                img_path=image,
                actions=actions,
                enforce_detection=False,
                silent=True,
            )

            # Handle list result (when multiple faces)
            if isinstance(results, list):
                results = results[0]

            # Extract age
            age_value = int(results.get("age", 25))
            age = AgeEstimate(
                value=age_value,
                range=(max(0, age_value - 3), age_value + 4),
                confidence=0.85,
            )

            # Extract gender
            gender_data = results.get("gender", {})
            if isinstance(gender_data, dict):
                woman_conf = gender_data.get("Woman", 0)
                man_conf = gender_data.get("Man", 0)
                gender_value = "female" if woman_conf > man_conf else "male"
                gender_conf = max(woman_conf, man_conf) / 100.0
            else:
                gender_value = str(gender_data).lower()
                gender_conf = 0.9

            gender = GenderEstimate(value=gender_value, confidence=gender_conf)

            # Extract race (optional)
            race = None
            if self._include_race and "race" in results:
                race_data = results["race"]
                dominant_race = results.get("dominant_race", "unknown")
                race_conf = race_data.get(dominant_race, 0) / 100.0 if race_data else 0.5

                race = RaceEstimate(
                    dominant=dominant_race.lower(),
                    confidence=race_conf,
                    all_probabilities={
                        k.lower(): v / 100.0 for k, v in race_data.items()
                    }
                    if race_data
                    else {},
                )

            # Extract emotion (optional)
            emotion = None
            if self._include_emotion and "emotion" in results:
                emotion_data = results["emotion"]
                dominant_emotion = results.get("dominant_emotion", "neutral")
                emotion_conf = (
                    emotion_data.get(dominant_emotion, 0) / 100.0 if emotion_data else 0.5
                )

                emotion = EmotionEstimate(
                    dominant=dominant_emotion.lower(),
                    confidence=emotion_conf,
                    all_probabilities={
                        k.lower(): v / 100.0 for k, v in emotion_data.items()
                    }
                    if emotion_data
                    else {},
                )

            result = DemographicsResult(
                age=age, gender=gender, race=race, emotion=emotion
            )

            logger.info(
                f"Demographics analysis complete: age={age.value}, gender={gender.value}"
            )

            return result

        except Exception as e:
            logger.error(f"Demographics analysis failed: {e}")
            raise DemographicsError(f"Demographics analysis failed: {str(e)}")

    def get_supported_attributes(self) -> List[str]:
        """Get list of analyzable attributes.

        Returns:
            List of supported attribute names
        """
        attributes = ["age", "gender"]
        if self._include_race:
            attributes.append("race")
        if self._include_emotion:
            attributes.append("emotion")
        return attributes
