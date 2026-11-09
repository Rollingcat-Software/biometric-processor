"""face_embeddings rows record the embedding pipeline, and a user's template
(the CENTROID) averages only samples of the pipeline being enrolled.

Embeddings from different pipelines (BGR and RGB input, different aligners)
are not comparable, and their average is meaningless. The id lives in the
existing ``metadata`` JSONB column, so no migration is needed; rows written
before it existed have no id and form their own group.

Same asyncpg double approach as ``test_face_repository_encryption.py``: the
SQL text and its arguments are captured and asserted on.
"""

from __future__ import annotations

import json
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from cryptography.fernet import Fernet

from app.domain.embedding_pipeline import EMBEDDING_PIPELINE_METADATA_KEY
from app.infrastructure.persistence.repositories.pgvector_embedding_repository import (
    PgVectorEmbeddingRepository,
)
from app.infrastructure.security.embedding_cipher import EmbeddingCipher

PIPELINE = "server-deepface-facenet512-rgb"


class _Recorder:
    def __init__(self, prior_centroid: dict[str, Any] | None = None) -> None:
        self.executes: List[tuple] = []
        self.fetchrows: List[tuple] = []
        self.fetchvals: List[tuple] = []
        self._prior_centroid = prior_centroid

    def connection(self) -> MagicMock:
        conn = MagicMock()

        async def _execute(*args: Any, **kwargs: Any) -> str:
            self.executes.append(args)
            return "OK"

        async def _fetchrow(*args: Any, **kwargs: Any) -> Any:
            self.fetchrows.append(args)
            if "enrollment_type = 'CENTROID'" in args[0]:
                return self._prior_centroid
            return {"avg_emb": np.full(512, 0.1, dtype=np.float32).tolist(), "avg_q": 0.5, "n": 2}

        async def _fetchval(*args: Any, **kwargs: Any) -> int:
            self.fetchvals.append(args)
            if "CENTROID" in args[0]:
                return 1 if self._prior_centroid is not None else 0
            return 1

        conn.execute = AsyncMock(side_effect=_execute)
        conn.fetchrow = AsyncMock(side_effect=_fetchrow)
        conn.fetchval = AsyncMock(side_effect=_fetchval)
        return conn


def _pool(conn: MagicMock) -> MagicMock:
    pool = MagicMock()

    class _Ctx:
        async def __aenter__(self) -> Any:
            return conn

        async def __aexit__(self, *exc: Any) -> None:
            return None

    pool.acquire = lambda: _Ctx()
    return pool


def _repo(cipher: EmbeddingCipher) -> PgVectorEmbeddingRepository:
    return PgVectorEmbeddingRepository(
        database_url="postgresql://stub", embedding_dimension=512, cipher=cipher
    )


@pytest.fixture
def cipher() -> EmbeddingCipher:
    return EmbeddingCipher(key=Fernet.generate_key())


def _vec() -> np.ndarray:
    v = np.random.default_rng(1).standard_normal(512).astype(np.float32)
    return v / np.linalg.norm(v)


def _metadata_args(call: tuple) -> list[dict]:
    out = []
    for arg in call[1:]:
        if isinstance(arg, str) and arg.startswith("{"):
            out.append(json.loads(arg))
    return out


async def _save(recorder: _Recorder, cipher: EmbeddingCipher, **kwargs: Any) -> None:
    repo = _repo(cipher)
    with patch.object(repo, "_ensure_pool", AsyncMock(return_value=_pool(recorder.connection()))):
        await repo.save(user_id="u1", embedding=_vec(), quality_score=90.0, tenant_id="t1", **kwargs)


@pytest.mark.asyncio
async def test_save_WhenPipelineIsGiven_ShouldWriteItIntoTheIndividualRowMetadata(cipher) -> None:
    recorder = _Recorder()

    await _save(recorder, cipher, embedding_pipeline=PIPELINE)

    individual = recorder.executes[0]
    assert "metadata" in individual[0]
    assert _metadata_args(individual) == [{EMBEDDING_PIPELINE_METADATA_KEY: PIPELINE}]


@pytest.mark.asyncio
async def test_save_WhenPipelineIsAbsent_ShouldWriteEmptyMetadataAsBefore(cipher) -> None:
    recorder = _Recorder()

    await _save(recorder, cipher)

    assert _metadata_args(recorder.executes[0]) == [{}]


@pytest.mark.asyncio
async def test_save_WhenAveragingTheCentroid_ShouldUseOnlySamplesOfTheSamePipeline(cipher) -> None:
    recorder = _Recorder()

    await _save(recorder, cipher, embedding_pipeline=PIPELINE)

    avg = next(c for c in recorder.fetchrows if "AVG(embedding)" in c[0])
    assert f"metadata->>'{EMBEDDING_PIPELINE_METADATA_KEY}' IS NOT DISTINCT FROM $2" in avg[0]
    assert avg[1:] == ("u1", PIPELINE)


@pytest.mark.asyncio
async def test_save_WhenCreatingTheCentroid_ShouldRecordItsPipeline(cipher) -> None:
    recorder = _Recorder()

    await _save(recorder, cipher, embedding_pipeline=PIPELINE)

    centroid_insert = next(c for c in recorder.executes if "'CENTROID'" in c[0] and "INSERT" in c[0])
    assert _metadata_args(centroid_insert) == [{EMBEDDING_PIPELINE_METADATA_KEY: PIPELINE}]


@pytest.mark.asyncio
async def test_save_WhenUpdatingTheCentroid_ShouldRecordItsPipeline(cipher) -> None:
    recorder = _Recorder(prior_centroid={"embedding": None, "embedding_ciphertext": None,
                                         "quality_score": 0.5, "embedding_pipeline": None})

    await _save(recorder, cipher, embedding_pipeline=PIPELINE)

    update = next(c for c in recorder.executes if c[0].lstrip().startswith("UPDATE face_embeddings"))
    assert _metadata_args(update) == [{EMBEDDING_PIPELINE_METADATA_KEY: PIPELINE}]


@pytest.mark.asyncio
async def test_save_WhenPruningAboveTheCap_ShouldDropOtherPipelinesFirst(cipher) -> None:
    recorder = _Recorder()
    recorder_conn = recorder.connection()

    async def _many(*args: Any, **kwargs: Any) -> int:
        recorder.fetchvals.append(args)
        return 7 if "INDIVIDUAL" in args[0] else 0

    recorder_conn.fetchval = AsyncMock(side_effect=_many)
    repo = _repo(cipher)
    with patch.object(repo, "_ensure_pool", AsyncMock(return_value=_pool(recorder_conn))):
        await repo.save(user_id="u1", embedding=_vec(), quality_score=90.0, embedding_pipeline=PIPELINE)

    prune = next(c for c in recorder.executes if c[0].lstrip().startswith("DELETE"))
    assert "IS DISTINCT FROM" in prune[0]
    assert PIPELINE in prune[1:]


@pytest.mark.asyncio
async def test_save_WhenPriorCentroidIsFromAnotherPipeline_ShouldNotFuseIntoIt(cipher) -> None:
    prior = cipher.encrypt_vector(np.full(512, 0.3, dtype=np.float32))
    recorder = _Recorder(prior_centroid={"embedding": None, "embedding_ciphertext": prior,
                                         "quality_score": 0.9, "embedding_pipeline": None})
    repo = _repo(cipher)
    repo._fusion_service = MagicMock()

    with patch.object(repo, "_ensure_pool", AsyncMock(return_value=_pool(recorder.connection()))):
        await repo.save(user_id="u1", embedding=_vec(), quality_score=90.0,
                        fuse_with_existing=True, embedding_pipeline=PIPELINE)

    repo._fusion_service.fuse_incremental.assert_not_called()
