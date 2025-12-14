"""Demographics analysis domain entities."""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from pydantic import BaseModel


@dataclass
class AgeEstimate:
    """Age estimation result.

    Attributes:
        value: Estimated age
        range: Age range tuple (min, max)
        confidence: Estimation confidence
    """

    value: int
    range: Tuple[int, int]
    confidence: float


@dataclass
class GenderEstimate:
    """Gender estimation result.

    Attributes:
        value: Predicted gender ("male" or "female")
        confidence: Estimation confidence
    """

    value: str
    confidence: float


@dataclass
class RaceEstimate:
    """Race estimation result.

    Attributes:
        dominant: Most likely race
        confidence: Estimation confidence
        all_probabilities: Probabilities for all races
    """

    dominant: str
    confidence: float
    all_probabilities: Dict[str, float]


@dataclass
class EmotionEstimate:
    """Emotion estimation result.

    Attributes:
        dominant: Most likely emotion
        confidence: Estimation confidence
        all_probabilities: Probabilities for all emotions
    """

    dominant: str
    confidence: float
    all_probabilities: Dict[str, float]


@dataclass
class DemographicsResult:
    """Complete demographics analysis result.

    Attributes:
        age: Age estimation
        gender: Gender estimation
        race: Race estimation (optional)
        emotion: Emotion estimation (optional)
    """

    age: AgeEstimate
    gender: GenderEstimate
    race: Optional[RaceEstimate] = None
    emotion: Optional[EmotionEstimate] = None


# Pydantic models for API responses


class AgeEstimateResponse(BaseModel):
    """API response model for age estimate."""

    value: int
    range: list
    confidence: float


class GenderEstimateResponse(BaseModel):
    """API response model for gender estimate."""

    value: str
    confidence: float


class RaceEstimateResponse(BaseModel):
    """API response model for race estimate."""

    dominant: str
    confidence: float
    all: Dict[str, float]


class EmotionEstimateResponse(BaseModel):
    """API response model for emotion estimate."""

    dominant: str
    confidence: float
    all: Dict[str, float]


class DemographicsResponse(BaseModel):
    """API response model for demographics analysis."""

    age: AgeEstimateResponse
    gender: GenderEstimateResponse
    race: Optional[RaceEstimateResponse] = None
    emotion: Optional[EmotionEstimateResponse] = None

    @classmethod
    def from_result(cls, result: DemographicsResult) -> "DemographicsResponse":
        """Create response from domain result."""
        race = None
        if result.race:
            race = RaceEstimateResponse(
                dominant=result.race.dominant,
                confidence=result.race.confidence,
                all=result.race.all_probabilities,
            )

        emotion = None
        if result.emotion:
            emotion = EmotionEstimateResponse(
                dominant=result.emotion.dominant,
                confidence=result.emotion.confidence,
                all=result.emotion.all_probabilities,
            )

        return cls(
            age=AgeEstimateResponse(
                value=result.age.value,
                range=list(result.age.range),
                confidence=result.age.confidence,
            ),
            gender=GenderEstimateResponse(
                value=result.gender.value,
                confidence=result.gender.confidence,
            ),
            race=race,
            emotion=emotion,
        )
