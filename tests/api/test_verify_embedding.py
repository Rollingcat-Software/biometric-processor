"""Tests for the precomputed-embedding routes (client-side embedding, Phase 4).

These cover the two additive routes that let a caller submit a PRECOMPUTED
512-d Facenet512 embedding instead of a face image:

    * ``POST /verify-embedding`` (Task 4.1) — runs ONLY the pgvector match +
      threshold/decision logic; it SKIPS detection, quality, liveness and
      Facenet512 because the client already computed the embedding.
    * ``POST /enroll-embedding`` (Task 4.2) — stores the client vector as the
      user's template via the EXISTING dual-column Fernet path.

The route handler coroutines are exercised directly (rather than through a full
TestClient) — the same pattern ``tests/unit/api/test_voice_routes.py`` uses to
avoid the asyncio loop-poisoning the integration TestClient-in-test-body suffers
from. The shared match/store code is reused from the verify/enroll use cases, so
these tests also prove that extracted code behaves correctly end-to-end.
"""

import numpy as np
import pytest
from pydantic import ValidationError as PydanticValidationError

from app.api.routes import verification as verification_route
from app.api.routes import enrollment as enrollment_route
from app.api.schemas.verification import EmbeddingVerifyRequest
from app.api.schemas.enrollment import EmbeddingEnrollRequest
from app.application.use_cases.verify_face import VerifyFaceUseCase
from app.application.use_cases.enroll_face import EnrollFaceUseCase
from app.infrastructure.ml.similarity.cosine_similarity import CosineSimilarityCalculator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unit_vector(seed: int, dim: int = 512) -> list[float]:
    """A deterministic, L2-normalized 512-vector — the client contract sends an
    already-normalized embedding."""
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(dim).astype(np.float32)
    v = v / np.linalg.norm(v)
    return v.tolist()


class _FakeEmbeddingRepository:
    """In-memory stand-in for the pgvector repository.

    Stores the LAST embedding per (user_id) and serves it back from
    ``find_by_user_id`` — enough to prove the enroll→verify round-trip without a
    live PostgreSQL. The real ``save`` does the Fernet dual-column write; the
    route under test calls ``save`` exactly as the image path does, so this fake
    proves the WIRING (shared store/match code) rather than the crypto, which is
    unit-tested separately against the real repository.
    """

    def __init__(self) -> None:
        self._store: dict[str, np.ndarray] = {}
        self.save_calls: list[dict] = []

    async def save(
        self,
        user_id: str,
        embedding: np.ndarray,
        quality_score: float,
        tenant_id=None,
        fuse_with_existing: bool = False,
    ) -> None:
        self.save_calls.append(
            {
                "user_id": user_id,
                "quality_score": quality_score,
                "tenant_id": tenant_id,
                "fuse_with_existing": fuse_with_existing,
                "dim": len(embedding),
            }
        )
        self._store[user_id] = np.asarray(embedding, dtype=np.float32)

    async def find_by_user_id(self, user_id: str, tenant_id=None):
        return self._store.get(user_id)


def _make_verify_use_case(repository) -> VerifyFaceUseCase:
    """A VerifyFaceUseCase with a REAL cosine calculator + the supplied repo.

    Detector / extractor / quality_assessor are irrelevant to the embedding
    match path (which skips them), so they are passed as None.
    """
    return VerifyFaceUseCase(
        detector=None,
        extractor=None,
        similarity_calculator=CosineSimilarityCalculator(threshold=0.4),
        repository=repository,
        quality_assessor=None,
    )


def _make_enroll_use_case(repository) -> EnrollFaceUseCase:
    return EnrollFaceUseCase(
        detector=None,
        extractor=None,
        quality_assessor=None,
        repository=repository,
    )


# ---------------------------------------------------------------------------
# Task 4.1 — POST /verify-embedding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_embedding_matches_stored_template():
    """Stored matching template + matching vector -> verified:true, distance<0.4."""
    repo = _FakeEmbeddingRepository()
    vec = _unit_vector(seed=1)
    repo._store["user-1"] = np.asarray(vec, dtype=np.float32)

    request = EmbeddingVerifyRequest(tenant_id="t1", user_id="user-1", embedding=vec)
    response = await verification_route.verify_embedding(
        request=request,
        use_case=_make_verify_use_case(repo),
    )

    assert response.verified is True
    assert response.distance < 0.4


@pytest.mark.asyncio
async def test_verify_embedding_rejects_non_matching_vector():
    """A different vector -> verified:false."""
    repo = _FakeEmbeddingRepository()
    repo._store["user-1"] = np.asarray(_unit_vector(seed=1), dtype=np.float32)

    request = EmbeddingVerifyRequest(
        tenant_id="t1", user_id="user-1", embedding=_unit_vector(seed=999)
    )
    response = await verification_route.verify_embedding(
        request=request,
        use_case=_make_verify_use_case(repo),
    )

    assert response.verified is False


@pytest.mark.asyncio
async def test_verify_embedding_unknown_user_is_not_found():
    """No stored template -> EmbeddingNotFoundError (mapped to HTTP 404)."""
    from app.domain.exceptions.verification_errors import EmbeddingNotFoundError

    repo = _FakeEmbeddingRepository()
    request = EmbeddingVerifyRequest(
        tenant_id="t1", user_id="nobody", embedding=_unit_vector(seed=1)
    )

    with pytest.raises(EmbeddingNotFoundError):
        await verification_route.verify_embedding(
            request=request,
            use_case=_make_verify_use_case(repo),
        )


def test_verify_embedding_wrong_length_is_rejected():
    """Wrong length (256 floats) -> schema validation error (HTTP 422)."""
    with pytest.raises(PydanticValidationError):
        EmbeddingVerifyRequest(
            tenant_id="t1",
            user_id="user-1",
            embedding=_unit_vector(seed=1, dim=256),
        )


def test_verify_embedding_correct_length_is_accepted():
    """A 512-vector validates cleanly."""
    req = EmbeddingVerifyRequest(
        tenant_id="t1", user_id="user-1", embedding=_unit_vector(seed=1)
    )
    assert len(req.embedding) == 512


# ---------------------------------------------------------------------------
# Task 4.2 — POST /enroll-embedding + round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enroll_embedding_stores_template_via_repository_save():
    """The client vector is stored through the same repository.save path."""
    repo = _FakeEmbeddingRepository()
    vec = _unit_vector(seed=7)

    request = EmbeddingEnrollRequest(tenant_id="t1", user_id="user-7", embedding=vec)
    response = await enrollment_route.enroll_embedding(
        request=request,
        use_case=_make_enroll_use_case(repo),
    )

    assert response.success is True
    assert response.user_id == "user-7"
    assert response.embedding_dimension == 512
    assert len(repo.save_calls) == 1
    assert repo.save_calls[0]["user_id"] == "user-7"
    assert repo.save_calls[0]["tenant_id"] == "t1"
    assert repo.save_calls[0]["dim"] == 512


@pytest.mark.asyncio
async def test_enroll_then_verify_roundtrip_same_vector_matches():
    """enroll a vector, then /verify-embedding with the SAME vector -> verified, distance~0."""
    repo = _FakeEmbeddingRepository()
    vec = _unit_vector(seed=42)

    await enrollment_route.enroll_embedding(
        request=EmbeddingEnrollRequest(tenant_id="t1", user_id="rt", embedding=vec),
        use_case=_make_enroll_use_case(repo),
    )

    response = await verification_route.verify_embedding(
        request=EmbeddingVerifyRequest(tenant_id="t1", user_id="rt", embedding=vec),
        use_case=_make_verify_use_case(repo),
    )

    assert response.verified is True
    assert response.distance == pytest.approx(0.0, abs=1e-5)


@pytest.mark.asyncio
async def test_enroll_then_verify_roundtrip_different_vector_rejected():
    """enroll one vector, verify a DIFFERENT vector -> verified:false."""
    repo = _FakeEmbeddingRepository()

    await enrollment_route.enroll_embedding(
        request=EmbeddingEnrollRequest(
            tenant_id="t1", user_id="rt2", embedding=_unit_vector(seed=42)
        ),
        use_case=_make_enroll_use_case(repo),
    )

    response = await verification_route.verify_embedding(
        request=EmbeddingVerifyRequest(
            tenant_id="t1", user_id="rt2", embedding=_unit_vector(seed=12345)
        ),
        use_case=_make_verify_use_case(repo),
    )

    assert response.verified is False


def test_enroll_embedding_wrong_length_is_rejected():
    """Wrong length on enroll -> schema validation error (HTTP 422)."""
    with pytest.raises(PydanticValidationError):
        EmbeddingEnrollRequest(
            tenant_id="t1",
            user_id="user-1",
            embedding=_unit_vector(seed=1, dim=256),
        )
