"""One face detection per probe image, shared by liveness and verification.

The image ``/verify`` route used to run the face detector twice on the same
upload: once inside ``CheckLivenessUseCase`` (passive PAD) and again inside
``VerifyFaceUseCase`` (embedding). Both use the same detector singleton, so the
second pass recomputed an identical result. These tests pin that

* the route invokes the detector exactly once per request, and
* the liveness decision and the verification result are the same as when each
  use case detects on its own (the previous behaviour).

The ML parts are deterministic fakes whose outputs depend on the face crop, so a
wrong bounding box or a different image would change the numbers.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import cv2
import numpy as np
import pytest

from app.api.routes import verification as verification_route
from app.application.services.face_image_detection import (
    DetectedFaceImage,
    detect_face_image,
)
from app.application.use_cases import check_liveness as check_liveness_module
from app.application.use_cases.check_liveness import CheckLivenessUseCase
from app.application.use_cases.verify_face import VerifyFaceUseCase
from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.entities.liveness_result import LivenessResult
from app.domain.exceptions.liveness_errors import LivenessModelLoadError
from app.infrastructure.ml.similarity.cosine_similarity import CosineSimilarityCalculator

USER_ID = "user-1"
EMBEDDING_DIM = 512


# ---------------------------------------------------------------------------
# Deterministic fakes
# ---------------------------------------------------------------------------


class _CountingDetector:
    """Detector fake: a fixed box derived from the image size, call counter."""

    def __init__(self) -> None:
        self.calls = 0

    async def detect(self, image: np.ndarray) -> FaceDetectionResult:
        self.calls += 1
        h, w = image.shape[:2]
        return FaceDetectionResult(
            found=True,
            bounding_box=(w // 8, h // 8, w // 2, h // 2),
            landmarks=None,
            confidence=0.99,
            antispoof_score=0.91,
            antispoof_label="real",
        )


class _CropLivenessDetector:
    """Liveness fake whose score is a function of the crop pixels."""

    async def check_liveness(self, face_region: np.ndarray) -> LivenessResult:
        score = float(np.mean(face_region)) / 255.0 * 100.0
        return LivenessResult(
            is_live=score >= 40.0,
            score=score,
            challenge="passive",
            challenge_completed=True,
            confidence=score / 100.0,
            details={"crop_shape": list(face_region.shape)},
        )


class _CropEmbeddingExtractor:
    """Extractor fake: a 512-d vector that depends on every crop pixel."""

    async def extract(self, face_region: np.ndarray) -> np.ndarray:
        small = cv2.resize(face_region, (16, 11)).astype(np.float32).ravel()
        vector = np.resize(small, EMBEDDING_DIM) + np.arange(EMBEDDING_DIM, dtype=np.float32)
        return vector / np.linalg.norm(vector)


class _FixedRepository:
    def __init__(self, embedding: np.ndarray) -> None:
        self._embedding = embedding

    async def find_by_user_id(self, user_id: str, tenant_id=None):
        return self._embedding if user_id == USER_ID else None


class _PathStorage:
    """IFileStorage fake that hands back a prepared file and never deletes it."""

    def __init__(self, path: str) -> None:
        self._path = path

    async def save_temp(self, file) -> str:
        return self._path

    async def cleanup(self, path: str) -> None:
        return None


def _write_probe(tmp_path: Path, seed: int) -> str:
    rng = np.random.default_rng(seed)
    image = rng.integers(60, 230, size=(240, 200, 3), dtype=np.uint8)
    path = tmp_path / f"probe_{seed}.png"
    cv2.imwrite(str(path), image)
    return str(path)


async def _template_from(path: str) -> np.ndarray:
    """A stored template close to (but not equal to) the probe's embedding."""
    image = cv2.imread(path)
    detection = await _CountingDetector().detect(image)
    embedding = await _CropEmbeddingExtractor().extract(detection.get_face_region(image))
    nudged = embedding + 0.01
    return nudged / np.linalg.norm(nudged)


def _build(detector: _CountingDetector, template: np.ndarray):
    liveness = CheckLivenessUseCase(
        detector=detector,
        liveness_detector=_CropLivenessDetector(),
        landmark_detector=None,
    )
    verify = VerifyFaceUseCase(
        detector=detector,
        extractor=_CropEmbeddingExtractor(),
        similarity_calculator=CosineSimilarityCalculator(threshold=0.4),
        repository=_FixedRepository(template),
        quality_assessor=None,
    )
    return liveness, verify


@pytest.fixture
def _antispoof_helpers_off(monkeypatch):
    """The route's optional anti-spoof attachments need models; switch them off."""
    monkeypatch.setattr(verification_route, "_evaluate_antispoof_pipeline_safe", lambda _p: None)
    monkeypatch.setattr(verification_route, "_evaluate_ear_liveness_safe", lambda _p: None)
    monkeypatch.setattr(verification_route.settings, "ANTISPOOF_DEVICE_RISK_ENABLED", False)
    monkeypatch.setattr(check_liveness_module.settings, "ANTI_SPOOFING_ENABLED", True)
    monkeypatch.setattr(check_liveness_module.settings, "ANTI_SPOOFING_THRESHOLD", 0.5)


async def _call_route(path: str, liveness, verify):
    upload = SimpleNamespace(content_type="image/png")
    request = SimpleNamespace(headers={"user-agent": "pytest"})
    background = SimpleNamespace(add_task=lambda *a, **k: None)
    return await verification_route.verify_face(
        request=request,
        background_tasks=background,
        user_id=USER_ID,
        file=upload,
        tenant_id=None,
        client_embedding=None,
        client_embeddings=None,
        client_model_version=None,
        session_id=None,
        device_platform=None,
        use_case=verify,
        liveness_use_case=liveness,
        storage=_PathStorage(path),
        observation_repo=Mock(),
    )


# ---------------------------------------------------------------------------
# Route: one detection per request, same response as before
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("seed", [1, 2, 3])
async def test_verifyFace_WhenImageProbe_ShouldDetectFaceOnce(
    tmp_path, _antispoof_helpers_off, seed
) -> None:
    path = _write_probe(tmp_path, seed)
    detector = _CountingDetector()
    liveness, verify = _build(detector, await _template_from(path))

    await _call_route(path, liveness, verify)

    assert detector.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("seed", [1, 2, 3])
async def test_verifyFace_WhenDetectionShared_ShouldReturnSameResultAsSeparateDetections(
    tmp_path, _antispoof_helpers_off, seed
) -> None:
    path = _write_probe(tmp_path, seed)
    template = await _template_from(path)

    # Previous behaviour: each use case decodes and detects on its own.
    ref_liveness, ref_verify = _build(_CountingDetector(), template)
    expected_liveness = await ref_liveness.execute(image_path=path)
    expected = await ref_verify.execute(user_id=USER_ID, image_path=path, tenant_id=None)

    liveness, verify = _build(_CountingDetector(), template)
    response = await _call_route(path, liveness, verify)

    assert expected_liveness.is_live is True
    assert response.verified == expected.verified
    assert response.distance == expected.distance
    assert response.confidence == expected.confidence
    assert response.threshold == expected.threshold


# ---------------------------------------------------------------------------
# Use cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_executeWithDetection_WhenFaceFound_ShouldReturnSameLivenessAndTheDetection(
    tmp_path, _antispoof_helpers_off
) -> None:
    path = _write_probe(tmp_path, 4)
    detector = _CountingDetector()
    liveness, _ = _build(detector, np.ones(EMBEDDING_DIM, dtype=np.float32))

    expected = await liveness.execute(image_path=path)
    result, detected = await liveness.execute_with_detection(image_path=path)

    assert result == expected
    assert detected is not None
    assert detected.detection == await _CountingDetector().detect(cv2.imread(path))
    assert np.array_equal(detected.fresh_image(), cv2.imread(path))


@pytest.mark.asyncio
async def test_executeWithDetection_WhenAntispoofModelMissing_ShouldApplyPolicyAndShareNothing(
    tmp_path, monkeypatch
) -> None:
    path = _write_probe(tmp_path, 5)
    monkeypatch.setattr(
        check_liveness_module.settings, "LIVENESS_ANTISPOOF_MODEL_MISSING_POLICY", "fail_closed"
    )
    detector = Mock()
    detector.detect = AsyncMock(side_effect=LivenessModelLoadError(model_name="MiniFASNet"))
    liveness = CheckLivenessUseCase(
        detector=detector, liveness_detector=_CropLivenessDetector(), landmark_detector=None
    )

    result, detected = await liveness.execute_with_detection(image_path=path)

    assert result.is_live is False
    assert result.details["reason"] == "antispoof_model_missing"
    assert detected is None


@pytest.mark.asyncio
async def test_verifyExecute_WhenDetectionGiven_ShouldNotDetectAgainAndMatchOwnDetection(
    tmp_path,
) -> None:
    path = _write_probe(tmp_path, 6)
    template = await _template_from(path)
    shared = await detect_face_image(_CountingDetector(), path)

    own_detector = _CountingDetector()
    _, own = _build(own_detector, template)
    expected = await own.execute(user_id=USER_ID, image_path=path)

    detector = _CountingDetector()
    _, verify = _build(detector, template)
    result = await verify.execute(user_id=USER_ID, image_path=path, detected=shared)

    assert own_detector.calls == 1
    assert detector.calls == 0
    assert result == expected


@pytest.mark.asyncio
async def test_freshImage_WhenConsumerWritesToIt_ShouldNotChangeSharedPixels(tmp_path) -> None:
    path = _write_probe(tmp_path, 7)
    detected = await detect_face_image(_CountingDetector(), path)

    first = detected.fresh_image()
    first[:] = 0

    assert np.array_equal(detected.fresh_image(), cv2.imread(path))
    assert not detected.image.flags.writeable


@pytest.mark.asyncio
async def test_detectFaceImage_WhenPathUnreadable_ShouldRaiseValueError(tmp_path) -> None:
    with pytest.raises(ValueError):
        await detect_face_image(_CountingDetector(), str(tmp_path / "missing.png"))


def test_detectedFaceImage_IsImmutableValueObject() -> None:
    image = np.zeros((4, 4, 3), dtype=np.uint8)
    detection = FaceDetectionResult(found=True, bounding_box=(0, 0, 2, 2), landmarks=None, confidence=0.9)
    detected = DetectedFaceImage(image=image, detection=detection, decode_ms=0.0, detect_ms=0.0)

    with pytest.raises(Exception):
        detected.detection = detection  # type: ignore[misc]
