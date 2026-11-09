"""Server-computed templates carry the server embedding pipeline id."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import cv2
import numpy as np
import pytest

from app.application.use_cases.enroll_face import EnrollFaceUseCase
from app.domain.embedding_pipeline import (
    FACENET_CHANNEL_ORDER,
    SERVER_EMBEDDING_PIPELINE,
)


def _use_case(repository: MagicMock) -> EnrollFaceUseCase:
    detection = MagicMock()
    detection.get_face_region.side_effect = lambda image: image[0:20, 0:20]
    detector = MagicMock()
    detector.detect = AsyncMock(return_value=detection)

    quality = MagicMock(is_acceptable=True, score=80.0)
    assessor = MagicMock()
    assessor.assess = AsyncMock(return_value=quality)

    extractor = MagicMock()
    extractor.extract = AsyncMock(return_value=np.ones(512, dtype=np.float32) / np.sqrt(512))

    return EnrollFaceUseCase(
        detector=detector,
        extractor=extractor,
        quality_assessor=assessor,
        repository=repository,
    )


@pytest.mark.asyncio
async def test_execute_WhenServerComputesTheEmbedding_ShouldRecordTheServerPipeline(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "face.png"
    cv2.imwrite(str(image_path), np.full((40, 40, 3), 128, dtype=np.uint8))
    repository = MagicMock()
    repository.save = AsyncMock()

    await _use_case(repository).execute(user_id="u1", image_path=str(image_path), tenant_id="t1")

    assert repository.save.await_args.kwargs["embedding_pipeline"] == SERVER_EMBEDDING_PIPELINE


def test_SERVER_EMBEDDING_PIPELINE_WhenDerived_ShouldNameModelAndChannelOrder() -> None:
    assert SERVER_EMBEDDING_PIPELINE == f"server-deepface-facenet512-{FACENET_CHANNEL_ORDER.lower()}"
    assert SERVER_EMBEDDING_PIPELINE == "server-deepface-facenet512-rgb"
