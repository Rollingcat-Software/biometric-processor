"""PostgreSQL pgvector repository for voice embeddings.

Follows the same centroid-based storage pattern as PgVectorEmbeddingRepository
(face embeddings). Each enrollment is stored as an INDIVIDUAL row, and a
CENTROID row is maintained as the running average of all individual embeddings.

Verification is performed against the CENTROID for robustness.
"""

import logging
from typing import Optional

import asyncpg
import numpy as np

from app.domain.exceptions.repository_errors import RepositoryError
from app.infrastructure.security.embedding_cipher import EmbeddingCipher

logger = logging.getLogger(__name__)

VOICE_EMBEDDING_DIM = 256

# GDPR P1.3 — see app/infrastructure/security/embedding_cipher.py for the
# dual-column rationale (plaintext pgvector for ANN + ciphertext canonical store).


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
        cipher: Optional[EmbeddingCipher] = None,
    ) -> None:
        self._database_url = database_url
        self._pool_min_size = pool_min_size
        self._pool_max_size = pool_max_size
        self._embedding_dimension = embedding_dimension
        self._pool: Optional[asyncpg.Pool] = None
        self._cipher: EmbeddingCipher = cipher if cipher is not None else EmbeddingCipher.from_env()
        self._key_version: int = 1

        logger.info(
            f"Initialized PgVectorVoiceRepository "
            f"(dim={embedding_dimension}, pool={pool_min_size}-{pool_max_size})"
        )

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
            ciphertext = self._cipher.encrypt_vector(np.asarray(embedding, dtype=np.float32))

            async with pool.acquire() as conn:
                # Insert individual enrollment (with GDPR P1.3 ciphertext)
                await conn.execute(
                    """
                    INSERT INTO voice_enrollments (
                        user_id, tenant_id, embedding, quality_score, enrollment_type,
                        embedding_ciphertext, key_version
                    ) VALUES ($1::varchar, $2::varchar, $3, $4, 'INDIVIDUAL'::varchar, $5, $6)
                    """,
                    user_id, tenant_id, embedding_list, quality_score,
                    ciphertext, self._key_version,
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

                # Compute centroid in SQL, then re-read in Python to encrypt.
                centroid_row = await conn.fetchrow(
                    f"""
                    SELECT {centroid_sql_avg} AS avg_emb,
                           AVG(quality_score) AS avg_q
                    FROM voice_enrollments
                    WHERE user_id = $1::varchar
                      AND enrollment_type = 'INDIVIDUAL'
                      AND deleted_at IS NULL
                    """,
                    user_id,
                )
                if centroid_row and centroid_row["avg_emb"] is not None:
                    centroid_vec = np.array(centroid_row["avg_emb"], dtype=np.float32)
                    centroid_quality = (
                        float(centroid_row["avg_q"])
                        if centroid_row["avg_q"] is not None
                        else 0.0
                    )
                    centroid_ciphertext = self._cipher.encrypt_vector(centroid_vec)
                    centroid_list = centroid_vec.tolist()

                    if has_centroid == 0:
                        # Create new centroid (plaintext + ciphertext in lockstep)
                        await conn.execute(
                            """
                            INSERT INTO voice_enrollments (
                                user_id, tenant_id, embedding, quality_score, enrollment_type,
                                embedding_ciphertext, key_version
                            )
                            VALUES ($1::varchar, $2::varchar, $3, $4, 'CENTROID'::varchar, $5, $6)
                            """,
                            user_id, tenant_id, centroid_list, centroid_quality,
                            centroid_ciphertext, self._key_version,
                        )
                    else:
                        # Update existing centroid (plaintext + ciphertext in lockstep)
                        await conn.execute(
                            """
                            UPDATE voice_enrollments SET
                                embedding = $2,
                                quality_score = $3,
                                embedding_ciphertext = $4,
                                key_version = $5,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE user_id = $1::varchar
                              AND enrollment_type = 'CENTROID'::varchar
                            """,
                            user_id, centroid_list, centroid_quality,
                            centroid_ciphertext, self._key_version,
                        )

                count = await conn.fetchval(
                    """
                    SELECT count(*) FROM voice_enrollments
                    WHERE user_id = $1::varchar AND enrollment_type = 'INDIVIDUAL' AND deleted_at IS NULL
                    """,
                    user_id,
                )

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

        GDPR P1.3 (P0-#2 fix, 2026-05-07): canonical store-of-record is
        ``embedding_ciphertext`` (Fernet). We select both columns and prefer
        the decrypted ciphertext; the plaintext column is only consulted for
        pre-P1.3 legacy rows. See sibling face repo for full rationale.
        """
        try:
            pool = await self._ensure_pool()

            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT embedding, embedding_ciphertext
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
                        """
                        SELECT embedding, embedding_ciphertext
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

                return self._decode_row_embedding(row, user_id=user_id)

        except Exception as e:
            logger.error(f"Failed to find voice embedding: {e}", exc_info=True)
            raise RepositoryError(operation="find_by_user_id", reason=str(e))

    def _decode_row_embedding(
        self, row: "asyncpg.Record", *, user_id: Optional[str] = None
    ) -> np.ndarray:
        """Decode an embedding row, preferring the encrypted column.

        Mirrors :meth:`PgVectorEmbeddingRepository._decode_row_embedding`.
        """
        ciphertext = row["embedding_ciphertext"]
        if ciphertext is not None:
            return self._cipher.decrypt_vector(bytes(ciphertext))

        logger.warning(
            "GDPR P1.3 voice fallback: row for user_id=%s has NULL "
            "embedding_ciphertext; reading plaintext column. Backfill required.",
            user_id,
        )
        return np.array(row["embedding"], dtype=np.float32)

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
