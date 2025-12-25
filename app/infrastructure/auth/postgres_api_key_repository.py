"""PostgreSQL API key repository implementation.

Provides persistent, distributed API key storage for production deployments.
"""

import logging
from datetime import datetime
from typing import List, Optional

from app.domain.entities.api_key import APIKey
from app.domain.interfaces.api_key_repository import IAPIKeyRepository

logger = logging.getLogger(__name__)


class PostgresAPIKeyRepository:
    """PostgreSQL-backed API key repository.

    Provides persistent storage of API keys for production deployments.
    Supports multi-instance deployments with shared database.

    Features:
        - Secure storage of key hashes (never plaintext keys)
        - Efficient lookups by hash, prefix, and tenant
        - Connection pooling for performance
        - Automatic last_used_at tracking

    Schema:
        CREATE TABLE api_keys (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            key_hash VARCHAR(64) NOT NULL UNIQUE,
            key_prefix VARCHAR(8) NOT NULL,
            tenant_id VARCHAR(255) NOT NULL,
            scopes TEXT NOT NULL DEFAULT 'read,write',
            tier VARCHAR(50) NOT NULL DEFAULT 'standard',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            last_used_at TIMESTAMP WITH TIME ZONE,
            expires_at TIMESTAMP WITH TIME ZONE,
            metadata JSONB
        );
        CREATE INDEX ix_api_keys_key_hash ON api_keys(key_hash);
        CREATE INDEX ix_api_keys_key_prefix ON api_keys(key_prefix);
        CREATE INDEX ix_api_keys_tenant_id ON api_keys(tenant_id);
        CREATE INDEX ix_api_keys_is_active ON api_keys(is_active);
    """

    def __init__(
        self,
        database_url: str,
        pool_size: int = 5,
        table_name: str = "api_keys",
    ) -> None:
        """Initialize PostgreSQL API key repository.

        Args:
            database_url: PostgreSQL connection URL
            pool_size: Connection pool size
            table_name: Name of the API keys table
        """
        self._database_url = database_url
        self._pool_size = pool_size
        self._table_name = table_name
        self._pool = None
        logger.info(
            f"PostgresAPIKeyRepository initialized (pool_size={pool_size})"
        )

    async def connect(self) -> None:
        """Establish database connection pool.

        Raises:
            RuntimeError: If connection fails
        """
        try:
            import asyncpg

            self._pool = await asyncpg.create_pool(
                self._database_url,
                min_size=2,
                max_size=self._pool_size,
            )
            logger.info("PostgreSQL API key repository connection pool established")
        except ImportError:
            raise RuntimeError(
                "asyncpg not installed. Install with: pip install asyncpg"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to connect to PostgreSQL: {e}")

    async def disconnect(self) -> None:
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("PostgreSQL API key repository connection pool closed")

    async def _ensure_connected(self) -> None:
        """Ensure connection pool is established."""
        if self._pool is None:
            await self.connect()

    def _row_to_api_key(self, row) -> APIKey:
        """Convert database row to APIKey entity.

        Args:
            row: Database row

        Returns:
            APIKey entity
        """
        scopes = row["scopes"].split(",") if row["scopes"] else ["read", "write"]
        metadata = row["metadata"] if row["metadata"] else {}

        return APIKey(
            id=row["id"],
            name=row["name"],
            key_hash=row["key_hash"],
            key_prefix=row["key_prefix"],
            tenant_id=row["tenant_id"],
            scopes=scopes,
            tier=row["tier"],
            is_active=row["is_active"],
            created_at=row["created_at"],
            last_used_at=row["last_used_at"],
            expires_at=row["expires_at"],
            metadata=metadata,
        )

    async def save(self, api_key: APIKey) -> None:
        """Save an API key.

        Args:
            api_key: API key entity to save
        """
        await self._ensure_connected()

        scopes_str = ",".join(api_key.scopes)
        import json
        metadata_json = json.dumps(api_key.metadata) if api_key.metadata else None

        query = f"""
            INSERT INTO {self._table_name} (
                id, name, key_hash, key_prefix, tenant_id,
                scopes, tier, is_active, created_at, last_used_at, expires_at, metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (id) DO UPDATE SET
                name = $2,
                scopes = $6,
                tier = $7,
                is_active = $8,
                last_used_at = $10,
                expires_at = $11,
                metadata = $12
        """

        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    query,
                    api_key.id,
                    api_key.name,
                    api_key.key_hash,
                    api_key.key_prefix,
                    api_key.tenant_id,
                    scopes_str,
                    api_key.tier,
                    api_key.is_active,
                    api_key.created_at,
                    api_key.last_used_at,
                    api_key.expires_at,
                    metadata_json,
                )
            logger.debug(f"Saved API key: {api_key.name} (prefix: {api_key.key_prefix})")
        except Exception as e:
            logger.error(f"Failed to save API key: {e}")
            raise

    async def find_by_key_hash(self, key_hash: str) -> Optional[APIKey]:
        """Find an API key by its hash.

        Args:
            key_hash: SHA-256 hash of the API key

        Returns:
            APIKey if found, None otherwise
        """
        await self._ensure_connected()

        query = f"""
            SELECT id, name, key_hash, key_prefix, tenant_id,
                   scopes, tier, is_active, created_at, last_used_at, expires_at, metadata
            FROM {self._table_name}
            WHERE key_hash = $1
        """

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, key_hash)

            if row is None:
                return None

            return self._row_to_api_key(row)

        except Exception as e:
            logger.error(f"Failed to find API key by hash: {e}")
            return None

    async def find_by_prefix(self, prefix: str) -> Optional[APIKey]:
        """Find an API key by its prefix.

        Args:
            prefix: First 8 characters of the API key

        Returns:
            APIKey if found, None otherwise
        """
        await self._ensure_connected()

        query = f"""
            SELECT id, name, key_hash, key_prefix, tenant_id,
                   scopes, tier, is_active, created_at, last_used_at, expires_at, metadata
            FROM {self._table_name}
            WHERE key_prefix = $1
        """

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, prefix)

            if row is None:
                return None

            return self._row_to_api_key(row)

        except Exception as e:
            logger.error(f"Failed to find API key by prefix: {e}")
            return None

    async def find_by_tenant(self, tenant_id: str) -> List[APIKey]:
        """Find all API keys for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            List of API keys for the tenant
        """
        await self._ensure_connected()

        query = f"""
            SELECT id, name, key_hash, key_prefix, tenant_id,
                   scopes, tier, is_active, created_at, last_used_at, expires_at, metadata
            FROM {self._table_name}
            WHERE tenant_id = $1
            ORDER BY created_at DESC
        """

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, tenant_id)

            return [self._row_to_api_key(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to find API keys by tenant: {e}")
            return []

    async def find_by_id(self, key_id: str) -> Optional[APIKey]:
        """Find an API key by its ID.

        Args:
            key_id: API key ID

        Returns:
            APIKey if found, None otherwise
        """
        await self._ensure_connected()

        query = f"""
            SELECT id, name, key_hash, key_prefix, tenant_id,
                   scopes, tier, is_active, created_at, last_used_at, expires_at, metadata
            FROM {self._table_name}
            WHERE id = $1
        """

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, key_id)

            if row is None:
                return None

            return self._row_to_api_key(row)

        except Exception as e:
            logger.error(f"Failed to find API key by ID: {e}")
            return None

    async def update_last_used(self, key_id: str) -> None:
        """Update the last_used_at timestamp for a key.

        Args:
            key_id: API key ID
        """
        await self._ensure_connected()

        query = f"""
            UPDATE {self._table_name}
            SET last_used_at = NOW()
            WHERE id = $1
        """

        try:
            async with self._pool.acquire() as conn:
                await conn.execute(query, key_id)
        except Exception as e:
            logger.error(f"Failed to update last_used_at: {e}")

    async def deactivate(self, key_id: str) -> bool:
        """Deactivate an API key.

        Args:
            key_id: API key ID

        Returns:
            True if deactivated, False if not found
        """
        await self._ensure_connected()

        query = f"""
            UPDATE {self._table_name}
            SET is_active = FALSE
            WHERE id = $1
        """

        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(query, key_id)

            # Parse "UPDATE n" to get count
            updated = int(result.split()[-1])
            if updated > 0:
                logger.info(f"Deactivated API key: {key_id}")
            return updated > 0

        except Exception as e:
            logger.error(f"Failed to deactivate API key: {e}")
            return False

    async def delete(self, key_id: str) -> bool:
        """Delete an API key.

        Args:
            key_id: API key ID

        Returns:
            True if deleted, False if not found
        """
        await self._ensure_connected()

        query = f"""
            DELETE FROM {self._table_name}
            WHERE id = $1
        """

        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(query, key_id)

            # Parse "DELETE n" to get count
            deleted = int(result.split()[-1])
            if deleted > 0:
                logger.info(f"Deleted API key: {key_id}")
            return deleted > 0

        except Exception as e:
            logger.error(f"Failed to delete API key: {e}")
            return False

    async def list_all(self, include_inactive: bool = False) -> List[APIKey]:
        """List all API keys.

        Args:
            include_inactive: Whether to include inactive keys

        Returns:
            List of all API keys
        """
        await self._ensure_connected()

        if include_inactive:
            query = f"""
                SELECT id, name, key_hash, key_prefix, tenant_id,
                       scopes, tier, is_active, created_at, last_used_at, expires_at, metadata
                FROM {self._table_name}
                ORDER BY created_at DESC
            """
        else:
            query = f"""
                SELECT id, name, key_hash, key_prefix, tenant_id,
                       scopes, tier, is_active, created_at, last_used_at, expires_at, metadata
                FROM {self._table_name}
                WHERE is_active = TRUE
                ORDER BY created_at DESC
            """

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query)

            return [self._row_to_api_key(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to list API keys: {e}")
            return []

    async def count(self) -> int:
        """Get the number of stored keys.

        Returns:
            Number of API keys
        """
        await self._ensure_connected()

        query = f"SELECT COUNT(*) FROM {self._table_name}"

        try:
            async with self._pool.acquire() as conn:
                count = await conn.fetchval(query)
            return count or 0

        except Exception as e:
            logger.error(f"Failed to count API keys: {e}")
            return 0

    async def health_check(self) -> bool:
        """Check database connection health.

        Returns:
            True if healthy
        """
        try:
            await self._ensure_connected()
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"API key repository health check failed: {e}")
            return False
