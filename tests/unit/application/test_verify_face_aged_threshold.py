"""Pins the threshold match_embedding actually applies, by enrollment age.

Until fix/remove-pytz, find_created_at raised ImportError (pytz) and returned
None, so the aged branch never ran in production. With the fix, a template
older than VERIFICATION_THRESHOLD_AGED_YEARS is matched against
VERIFICATION_THRESHOLD_AGED instead of the calculator threshold. These tests
pin that policy so any change to it is deliberate and visible.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.application.use_cases import verify_face as verify_face_module
from app.application.use_cases.verify_face import VerifyFaceUseCase
from app.core.config import Settings

STANDARD_THRESHOLD = 0.40  # production VERIFICATION_THRESHOLD on 2026-11-09
PROBE_DISTANCE = 0.50  # rejected at 0.40, accepted at the 0.55 aged default


def _use_case(created_at: datetime | None) -> VerifyFaceUseCase:
    repository = MagicMock()
    repository.find_by_user_id = AsyncMock(return_value=np.ones(512, dtype=np.float32))
    repository.find_created_at = AsyncMock(return_value=created_at)
    calculator = MagicMock()
    calculator.calculate.return_value = PROBE_DISTANCE
    calculator.get_threshold.return_value = STANDARD_THRESHOLD
    calculator.get_confidence.return_value = 0.5
    return VerifyFaceUseCase(
        detector=MagicMock(),
        extractor=MagicMock(),
        similarity_calculator=calculator,
        repository=repository,
    )


@pytest.fixture
def default_aged_settings(monkeypatch):
    defaults = Settings(_env_file=None)
    monkeypatch.setattr(
        verify_face_module.settings,
        "VERIFICATION_THRESHOLD_AGED_YEARS",
        defaults.VERIFICATION_THRESHOLD_AGED_YEARS,
    )
    monkeypatch.setattr(
        verify_face_module.settings,
        "VERIFICATION_THRESHOLD_AGED",
        defaults.VERIFICATION_THRESHOLD_AGED,
    )
    return defaults


@pytest.mark.asyncio
async def test_matchEmbedding_WhenTemplateIsOlderThanAgedYears_ShouldApplyAgedThreshold(
    default_aged_settings,
):
    created_at = datetime.utcnow() - timedelta(days=int(2.0 * 365) + 30)

    result = await _use_case(created_at).match_embedding(user_id="u1", embedding=np.ones(512))

    assert default_aged_settings.VERIFICATION_THRESHOLD_AGED_YEARS == 2.0
    assert default_aged_settings.VERIFICATION_THRESHOLD_AGED == 0.55
    assert result.threshold == 0.55
    assert result.verified is True


@pytest.mark.asyncio
async def test_matchEmbedding_WhenTemplateIsYoungerThanAgedYears_ShouldApplyStandardThreshold(
    default_aged_settings,
):
    created_at = datetime.utcnow() - timedelta(days=200)

    result = await _use_case(created_at).match_embedding(user_id="u1", embedding=np.ones(512))

    assert result.threshold == STANDARD_THRESHOLD
    assert result.verified is False


@pytest.mark.asyncio
async def test_matchEmbedding_WhenCreatedAtIsUnknown_ShouldApplyStandardThreshold(
    default_aged_settings,
):
    result = await _use_case(None).match_embedding(user_id="u1", embedding=np.ones(512))

    assert result.threshold == STANDARD_THRESHOLD
    assert result.verified is False
