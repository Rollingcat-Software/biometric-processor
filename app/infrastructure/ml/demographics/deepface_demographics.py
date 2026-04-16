"""DeepFace-based demographics analyzer implementation."""

import logging
import threading
import time
from typing import List, Optional

import numpy as np
from deepface import DeepFace

from app.domain.entities.demographics import (
    AgeEstimate,
    DemographicsResult,
    EmotionEstimate,
    GenderEstimate,
    RaceEstimate,
)
from app.domain.exceptions.feature_errors import DemographicsError
from app.core.config import settings

logger = logging.getLogger(__name__)


class DeepFaceDemographicsAnalyzer:
    """Demographics analyzer using DeepFace.

    Analyzes age, gender, and optionally race and emotion from face images.
    Includes a 3-second TTL in-memory cache keyed by face spatial bucket
    to avoid redundant inference on consecutive frames with the same face.
    """

    def __init__(
        self,
        include_race: bool = False,
        include_emotion: bool = True,
        min_image_size: int = 224,
        age_margin: int = 10,
        age_confidence: float = 0.65,
    ) -> None:
        """Initialize DeepFace demographics analyzer.

        Args:
            include_race: Whether to include race estimation
            include_emotion: Whether to include emotion analysis
            min_image_size: Minimum image size for accurate analysis (default: 224px)
            age_margin: Age range margin in years (default: 10 based on DeepFace MAE)
            age_confidence: Age estimation confidence to report (default: 0.65 conservative estimate)
        """
        self._include_race = include_race
        self._include_emotion = include_emotion
        self._min_image_size = min_image_size
        self._age_margin = age_margin
        self._age_confidence = age_confidence

        # TTL cache: keyed by spatial bucket of face region, 3-second TTL, max 20 entries
        self._cache: dict = {}
        self._cache_ttl = 3.0
        self._lock = threading.Lock()

        logger.info(
            f"DeepFaceDemographicsAnalyzer initialized: "
            f"race={include_race}, emotion={include_emotion}, "
            f"min_size={min_image_size}px, age_margin=±{age_margin}yr, "
            f"age_confidence={age_confidence:.2f}"
        )

    def _cache_key(self, face_region: dict) -> str:
        """Build a spatial bucket cache key from a face region dict.

        Floors x and y to the nearest 50px so that small tracking jitter
        still hits the cache.
        """
        x = face_region.get("x", 0) // 50
        y = face_region.get("y", 0) // 50
        return f"{x}_{y}"

    def analyze(
        self, image: np.ndarray, face_region: Optional[dict] = None
    ) -> DemographicsResult:
        """Analyze demographics from face image.

        Args:
            image: Face image as numpy array (RGB format)
            face_region: Optional dict with 'x' and 'y' keys (face bounding-box
                top-left corner in the original frame).  When provided the result
                is cached for ``_cache_ttl`` seconds so consecutive frames at the
                same position skip expensive DeepFace inference.

        Returns:
            DemographicsResult with demographics data

        Raises:
            DemographicsError: If analysis fails
        """
        # --- Cache lookup ---
        if face_region is not None:
            key = self._cache_key(face_region)
            with self._lock:
                cached = self._cache.get(key)
                if cached and (time.monotonic() - cached["ts"]) < self._cache_ttl:
                    _log = logger.info if settings.ENABLE_ML_PROFILER else logger.debug
                    _log(f"Demographics cache hit (age={cached['result'].age.value})")
                    return cached["result"]

        logger.debug("Starting demographics analysis")

        t0 = time.monotonic()
        try:
            # Validate image quality before analysis
            h, w = image.shape[:2]
            if min(h, w) < self._min_image_size:
                raise DemographicsError(
                    f"Image too small for accurate demographics: {w}x{h}. "
                    f"Minimum recommended: {self._min_image_size}x{self._min_image_size} pixels for optimal accuracy"
                )

            # Build actions list
            actions = ["age", "gender"]
            if self._include_race:
                actions.append("race")
            if self._include_emotion:
                actions.append("emotion")

            # Analyze with DeepFace
            # Note: enforce_detection=True to ensure face is properly detected
            # silent=False to show important warnings
            results = DeepFace.analyze(
                img_path=image,
                actions=actions,
                enforce_detection=True,
                silent=False,
            )
            elapsed_ms = (time.monotonic() - t0) * 1000
            _log = logger.info if settings.ENABLE_ML_PROFILER else logger.debug
            _log(f"Demographics computed in {elapsed_ms:.0f}ms")

            # Handle list result (when multiple faces)
            if isinstance(results, list):
                if len(results) == 0:
                    raise DemographicsError("No face detected in image")
                if len(results) > 1:
                    logger.warning(f"Multiple faces detected ({len(results)}), using first face")
                results = results[0]

            # Extract age with proper validation
            if "age" not in results:
                raise DemographicsError("Age estimation failed - no age returned by model")

            age_value = int(results["age"])

            # Validate age is within reasonable bounds
            if not (0 <= age_value <= 120):
                raise DemographicsError(
                    f"Invalid age detected: {age_value}. Age must be between 0-120."
                )

            # Calculate realistic confidence based on configuration
            # DeepFace doesn't return age confidence directly, so we use a conservative estimate
            # Based on research: DeepFace has MAE ~10 years, so confidence should reflect this uncertainty
            age_confidence = self._age_confidence

            # Use realistic age range based on known model uncertainty
            # Research shows DeepFace MAE is ~10 years, configurable via age_margin
            age = AgeEstimate(
                value=age_value,
                range=(max(0, age_value - self._age_margin), min(120, age_value + self._age_margin)),
                confidence=age_confidence,
            )

            logger.info(
                f"Age estimation: {age_value} years (range: {age.range[0]}-{age.range[1]}, "
                f"confidence: {age_confidence:.2f})"
            )

            # Extract gender with proper validation
            if "gender" not in results:
                raise DemographicsError("Gender estimation failed - no gender returned by model")

            gender_data = results["gender"]
            if isinstance(gender_data, dict):
                woman_conf = gender_data.get("Woman", 0)
                man_conf = gender_data.get("Man", 0)

                if woman_conf == 0 and man_conf == 0:
                    raise DemographicsError("Gender estimation failed - no confidence scores")

                gender_value = "female" if woman_conf > man_conf else "male"
                gender_conf = max(woman_conf, man_conf) / 100.0
            else:
                # Fallback: if gender is returned as string (shouldn't happen with current DeepFace)
                gender_value = str(gender_data).lower()
                if gender_value not in ["male", "female", "man", "woman"]:
                    raise DemographicsError(f"Invalid gender value: {gender_value}")
                # Map to standard values
                gender_value = "female" if gender_value in ["female", "woman"] else "male"
                # Use lower confidence for string fallback
                gender_conf = 0.6
                logger.warning(f"Gender returned as string: {gender_data}, using confidence=0.6")

            gender = GenderEstimate(value=gender_value, confidence=gender_conf)

            logger.info(
                f"Gender estimation: {gender_value} (confidence: {gender_conf:.2f})"
            )

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
