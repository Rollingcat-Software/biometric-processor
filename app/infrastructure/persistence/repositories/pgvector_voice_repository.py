"""PostgreSQL pgvector repository for voice embeddings.

Follows the same centroid-based storage pattern as PgVectorEmbeddingRepository
(face embeddings). Each enrollment is stored as an INDIVIDUAL row, and a
CENTROID row is maintained as the running average of all individual embeddings.

Verification is performed against the CENTROID for robustness.
"""

import logging
from typing import List, Optional, Tuple
from uuid import UUID

import asyncpg
import numpy as np

from app.domain.exceptions.repository_errors import RepositoryError

logger = logging.getLogger(__name__)

VOICE_EMBEDDING_DIM = 256


def _tenant_uuid(tenant_id: Optional[str]) -> Optional[UUID]:
    if tenant_id is None:
        return None
    try:
        return UUID(str(tenant_id))
    except (ValueError, AttributeError):
        import hashlib
        digest = hashlib.sha256(str(tenant_id).encode("utf-8")).digest()[:16]
        return UUID(bytes=digest)


def _voice_aad(tenant_id: Optional[str], user_id: str) -> bytes:
    tu = _tenant_uuid(tenant_id)
    tb = tu.bytes if tu is not None else b"\x00" * 16
    return b"voice:" + tb + b":" + user_id.encode("utf-8")


def _embedding_to_bytes(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def _bytes_to_embedding(raw: bytes, dim: int) -> np.ndarray:
    vec = np.frombuffer(raw, dtype=np.float32)
    if vec.size != dim:
        raise ValueError(
            f"Decrypted voice embedding has wrong dimension: expected {dim}, got {vec.size}"
        )
    return vec


class PgVectorVoiceRepository:
    """Repository for voice enrollment embeddings using pgvector.

    Table: voice_enrollments
    Pattern: individual enrollments + centroid average (same as face_embeddings)
    """

    def __init__(
        self,
        database_url: str,
        pool_min_size: int = 2,
        pool_max_size: int = 5,
        embedding_dimension: int = VOICE_EMBEDDING_DIM,
        cipher: Optional[object] = None,
        match_service: Optional[object] = None,
        enc_enabled: bool = False,
        enc_strict: bool = False,
    ) -> None:
        self._database_url = database_url
        self._pool_min_size = pool_min_size
        self._pool_max_size = pool_max_size
        self._embedding_dimension = embedding_dimension
        self._pool: Optional[asyncpg.Pool] = None
        # Phase 1.3b — envelope encryption.
        self._cipher = cipher
        self._match_service = match_service
        self._enc_enabled = bool(enc_enabled)
        self._enc_strict = bool(enc_strict)

        logger.info(
            f"Initialized PgVectorVoiceRepository "
            f"(dim={embedding_dimension}, pool={pool_min_size}-{pool_max_size}, "
            f"enc_enabled={self._enc_enabled}, enc_strict={self._enc_strict})"
        )

    def _encrypt_embedding(
        self, embedding: np.ndarray, tenant_id: Optional[str], user_id: str
    ) -> Optional[bytes]:
        if not self._enc_enabled or self._cipher is None:
            return None
        aad = _voice_aad(tenant_id, user_id)
        return self._cipher.encrypt(_embedding_to_bytes(embedding), aad).encode("ascii")

    def _decrypt_ciphertext(
        self, ciphertext: object, tenant_id: Optional[str], user_id: str
    ) -> Optional[np.ndarray]:
        if ciphertext is None or self._cipher is None:
            return None
        if isinstance(ciphertext, (bytes, bytearray, memoryview)):
            stored = bytes(ciphertext).decode("ascii")
        else:
            stored = str(ciphertext)
        aad = _voice_aad(tenant_id, user_id)
        raw = self._cipher.decrypt(stored, aad)
        return _bytes_to_embedding(raw, self._embedding_dimension)

    async def _ensure_pool(self) -> asyncpg.Pool:
        """Create connection pool on first use."""
        if self._pool is None:
            try:
                self._pool = await asyncpg.create_pool(
                    self._database_url,
                    min_size=self._pool_min_size,
                    max_size=self._pool_max_size,
                    command_timeout=30.0,
                    setup=self._setup_connection,
                )
                logger.info("Voice repository connection pool created")
            except Exception as e:
                logger.error(f"Failed to create voice repo pool: {e}", exc_info=True)
                raise RepositoryError(operation="pool_creation", reason=str(e))
        return self._pool

    async def _setup_connection(self, conn: asyncpg.Connection) -> None:
        """Register pgvector type on each connection."""
        from pgvector.asyncpg import register_vector
        await register_vector(conn)

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("Voice repository connection pool closed")

    async def save(
        self,
        user_id: str,
        embedding: np.ndarray,
        quality_score: float = 1.0,
        tenant_id: Optional[str] = None,
    ) -> None:
        """Save a voice embedding (INDIVIDUAL) and update CENTROID.

        Args:
            user_id: User identifier.
            embedding: 256-dim speaker embedding vector.
            quality_score: Quality score (0-1).
            tenant_id: Optional tenant identifier.
        """
        if len(embedding) != self._embedding_dimension:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self._embedding_dimension}, "
                f"got {len(embedding)}"
            )

        dim = self._embedding_dimension

        try:
            pool = await self._ensure_pool()
            embedding_list = embedding.tolist()

            # Phase 1.3b — dual-write ciphertext when encryption is enabled.
            individual_ct = self._encrypt_embedding(embedding, tenant_id, user_id)

            async with pool.acquire() as conn:
                # Insert individual enrollment
                await conn.execute(
                    """
                    INSERT INTO voice_enrollments (
                        user_id, tenant_id, embedding, quality_score, enrollment_type,
                        embedding_ciphertext, enc_version
                    ) VALUES ($1::varchar, $2::varchar, $3, $4, 'INDIVIDUAL'::varchar, $5, $6)
                    """,
                    user_id, tenant_id, embedding_list, quality_score,
                    individual_ct,
                    1 if individual_ct is not None else None,
                )

                # Check if centroid exists
                has_centroid = await conn.fetchval(
                    """
                    SELECT count(*) FROM voice_enrollments
                    WHERE user_id = $1::varchar AND enrollment_type = 'CENTROID' AND deleted_at IS NULL
                    """,
                    user_id,
                )

                centroid_sql_avg = f"AVG(embedding)::vector({dim})"

                if has_centroid == 0:
                    # Create new centroid
                    await conn.execute(
                        f"""
                        INSERT INTO voice_enrollments (user_id, tenant_id, embedding, quality_score, enrollment_type)
                        SELECT $1::varchar, $2::varchar,
                               {centroid_sql_avg},
                               AVG(quality_score),
                               'CENTROID'::varchar
                        FROM voice_enrollments
                        WHERE user_id = $1::varchar AND enrollment_type = 'INDIVIDUAL' AND deleted_at IS NULL
                        """,
                        user_id, tenant_id,
                    )
                else:
                    # Update existing centroid
                    await conn.execute(
                        f"""
                        UPDATE voice_enrollments SET
                            embedding = sub.avg_emb,
                            quality_score = sub.avg_q,
                            updated_at = CURRENT_TIMESTAMP
                        FROM (
                            SELECT {centroid_sql_avg} as avg_emb,
                                   AVG(quality_score) as avg_q
                            FROM voice_enrollments
                            WHERE user_id = $1::varchar AND enrollment_type = 'INDIVIDUAL' AND deleted_at IS NULL
                        ) sub
                        WHERE voice_enrollments.user_id = $1::varchar
                          AND voice_enrollments.enrollment_type = 'CENTROID'
                        """,
                        user_id,
                    )

                # Phase 1.3b — encrypt the (just-computed) centroid plaintext.
                if self._enc_enabled and self._cipher is not None:
                    centroid_row = await conn.fetchrow(
                        """
                        SELECT embedding
                        FROM voice_enrollments
                        WHERE user_id = $1::varchar
                          AND enrollment_type = 'CENTROID'
                          AND deleted_at IS NULL
                        LIMIT 1
                        """,
                        user_id,
                    )
                    if centroid_row and centroid_row["embedding"] is not None:
                        centroid_vec = np.array(
                            centroid_row["embedding"], dtype=np.float32
                        )
                        centroid_ct = self._encrypt_embedding(
                            centroid_vec, tenant_id, user_id
                        )
                        await conn.execute(
                            """
                            UPDATE voice_enrollments
                            SET embedding_ciphertext = $1,
                                enc_version = 1
                            WHERE user_id = $2::varchar
                              AND enrollment_type = 'CENTROID'
                              AND deleted_at IS NULL
                            """,
                            centroid_ct, user_id,
                        )

                count = await conn.fetchval(
                    """
                    SELECT count(*) FROM voice_enrollments
                    WHERE user_id = $1::varchar AND enrollment_type = 'INDIVIDUAL' AND deleted_at IS NULL
                    """,
                    user_id,
                )

            # Phase 1.3b — invalidate per-tenant match cache.
            if self._match_service is not None:
                try:
                    tu = _tenant_uuid(tenant_id)
                    if tu is not None:
                        await self._match_service.invalidate(tu)
                except Exception:
                    logger.debug("voice match cache invalidate failed", exc_info=True)

            logger.info(
                f"Voice embedding saved: user_id={user_id}, "
                f"dim={len(embedding)}, total_enrollments={count}"
            )

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to save voice embedding: {e}", exc_info=True)
            raise RepositoryError(operation="save", reason=str(e))

    async def find_by_user_id(
        self, user_id: str, tenant_id: Optional[str] = None
    ) -> Optional[np.ndarray]:
        """Find the voice centroid embedding for a user.

        Returns the CENTROID if available, otherwise falls back to the
        latest INDIVIDUAL enrollment.
        """
        try:
            pool = await self._ensure_pool()
            select_cols = (
                "embedding, embedding_ciphertext"
                if self._enc_enabled
                else "embedding"
            )

            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"""
                    SELECT {select_cols}
                    FROM voice_enrollments
                    WHERE user_id = $1::varchar
                      AND enrollment_type = 'CENTROID'
                      AND deleted_at IS NULL
                    LIMIT 1
                    """,
                    user_id,
                )

                if not row:
                    row = await conn.fetchrow(
                        f"""
                        SELECT {select_cols}
                        FROM voice_enrollments
                        WHERE user_id = $1::varchar
                          AND enrollment_type = 'INDIVIDUAL'
                          AND deleted_at IS NULL
                        ORDER BY created_at DESC
                        LIMIT 1
                        """,
                        user_id,
                    )

                if not row:
                    return None

            # Phase 1.3b — ciphertext first.
            if self._enc_enabled and self._cipher is not None:
                ct = row["embedding_ciphertext"] if "embedding_ciphertext" in row else None
                if ct is not None:
                    try:
                        return self._decrypt_ciphertext(ct, tenant_id, user_id)
                    except ValueError:
                        logger.error(
                            "voice find_by_user_id: ciphertext decrypt failed "
                            "user_id=%s tenant_id=%s", user_id, tenant_id,
                        )
                        if self._enc_strict:
                            raise

            # Plaintext fallback.
            pt = row["embedding"] if "embedding" in row else None
            if pt is None:
                return None
            if self._enc_strict:
                raise RepositoryError(
                    operation="find",
                    reason=(
                        "Legacy plaintext voice embedding encountered with "
                        "FIVUCSAS_EMBEDDING_ENC_STRICT=true."
                    ),
                )
            if self._enc_enabled:
                logger.warning(
                    "legacy.plaintext.read.voice",
                    extra={"user_id": user_id, "tenant_id": tenant_id},
                )
            return np.array(pt, dtype=np.float32)

        except Exception as e:
            logger.error(f"Failed to find voice embedding: {e}", exc_info=True)
            raise RepositoryError(operation="find_by_user_id", reason=str(e))

    async def delete_by_user_id(self, user_id: str) -> bool:
        """Soft-delete all voice enrollments for a user.

        Returns True if any rows were affected, False if none found.
        """
        try:
            pool = await self._ensure_pool()

            async with pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE voice_enrollments
                    SET deleted_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1::varchar AND deleted_at IS NULL
                    """,
                    user_id,
                )

            # asyncpg returns e.g. "UPDATE 3"
            affected = int(result.split()[-1])
            logger.info(f"Voice enrollments soft-deleted: user_id={user_id}, affected={affected}")
            return affected > 0

        except Exception as e:
            logger.error(f"Failed to delete voice enrollment: {e}", exc_info=True)
            raise RepositoryError(operation="delete", reason=str(e))

    async def find_similar(self, embedding, threshold=0.4, limit=5, tenant_id: Optional[str] = None):
        """Search for similar voice embeddings (1:N identification).

        ML-M5 (Audit 2026-04-19): caller-supplied ``threshold`` and ``limit``
        are clamped against configurable caps to prevent enumeration-via-
        inflated-parameters. ``tenant_id`` is accepted for symmetry with the
        face repository; when supplied it scopes the query at the SQL layer.
        """
        # ML-M5: server-side caps
        from app.core.config import settings as _settings
        max_threshold = _settings.FIND_SIMILAR_VOICE_MAX_THRESHOLD
        max_limit = _settings.FIND_SIMILAR_MAX_LIMIT
        if threshold > max_threshold:
            logger.warning(
                "voice find_similar threshold %.3f exceeds cap %.3f; clamping",
                threshold, max_threshold,
            )
            threshold = max_threshold
        if limit > max_limit:
            logger.warning(
                "voice find_similar limit %d exceeds cap %d; clamping",
                limit, max_limit,
            )
            limit = max_limit

        # Phase 1.3b — delegate to the in-memory match service when
        # encryption is enabled.
        if self._enc_enabled and self._match_service is not None:
            try:
                tu = _tenant_uuid(tenant_id)
                if tu is None:
                    raise ValueError(
                        "tenant_id must be a valid UUID when encryption is enabled"
                    )
                return await self._match_service.search_top_k(
                    tu, np.asarray(embedding, dtype=np.float32), limit, threshold
                )
            except Exception:
                if self._enc_strict:
                    raise
                logger.warning(
                    "encrypted voice find_similar failed; falling back to pgvector",
                    exc_info=True,
                )

        try:
            pool = await self._ensure_pool()
            embedding_list = embedding.tolist()

            async with pool.acquire() as conn:
                if tenant_id:
                    rows = await conn.fetch(
                        """
                        SELECT user_id, embedding <=> $1::vector AS distance
                        FROM voice_enrollments
                        WHERE deleted_at IS NULL
                          AND (enrollment_type = 'CENTROID' OR enrollment_type IS NULL)
                          AND embedding <=> $1::vector < $2
                          AND tenant_id = $4::VARCHAR
                        ORDER BY distance ASC
                        LIMIT $3
                        """,
                        embedding_list, threshold, limit, tenant_id,
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT user_id, embedding <=> $1::vector AS distance
                        FROM voice_enrollments
                        WHERE deleted_at IS NULL
                          AND (enrollment_type = 'CENTROID' OR enrollment_type IS NULL)
                          AND embedding <=> $1::vector < $2
                        ORDER BY distance ASC
                        LIMIT $3
                        """,
                        embedding_list, threshold, limit,
                    )

            return [(row["user_id"], float(row["distance"])) for row in rows]

        except Exception as e:
            logger.error(f"Voice search failed: {e}", exc_info=True)
            raise RepositoryError(operation="search", reason=str(e))

    # ------------------------------------------------------------------
    # Phase 1.3b contract — used by EmbeddingMatchService (modality=voice).
    # ------------------------------------------------------------------
    async def load_active_ciphertexts(self, tenant_id: UUID) -> List[Tuple[str, str]]:
        """Return ``[(user_id, ciphertext), ...]`` for the tenant's active
        voice centroid rows.
        """
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, embedding_ciphertext
                FROM voice_enrollments
                WHERE tenant_id = $1::VARCHAR
                  AND deleted_at IS NULL
                  AND (enrollment_type = 'CENTROID' OR enrollment_type IS NULL)
                  AND embedding_ciphertext IS NOT NULL
                """,
                str(tenant_id),
            )
        out: List[Tuple[str, str]] = []
        for row in rows:
            ct = row["embedding_ciphertext"]
            if ct is None:
                continue
            if isinstance(ct, (bytes, bytearray, memoryview)):
                out.append((row["user_id"], bytes(ct).decode("ascii")))
            else:
                out.append((row["user_id"], str(ct)))
        return out
