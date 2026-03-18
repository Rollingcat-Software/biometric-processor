"""In-memory API key repository implementation."""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from app.domain.entities.api_key import APIKey

logger = logging.getLogger(__name__)


class InMemoryAPIKeyRepository:
    """In-memory API key repository.

    Suitable for development and single-instance deployments.
    For production, use a database-backed implementation.
    """

    def __init__(self) -> None:
        """Initialize the repository."""
        self._keys_by_id: Dict[str, APIKey] = {}
        self._keys_by_hash: Dict[str, str] = {}  # hash -> id
        self._keys_by_prefix: Dict[str, str] = {}  # prefix -> id
        logger.info("InMemoryAPIKeyRepository initialized")

    async def save(self, api_key: APIKey) -> None:
        """Save an API key.

        Args:
            api_key: API key entity to save
        """
        self._keys_by_id[api_key.id] = api_key
        self._keys_by_hash[api_key.key_hash] = api_key.id
        self._keys_by_prefix[api_key.key_prefix] = api_key.id
        logger.debug(f"Saved API key: {api_key.name} (prefix: {api_key.key_prefix})")

    async def find_by_key_hash(self, key_hash: str) -> Optional[APIKey]:
        """Find an API key by its hash.

        Args:
            key_hash: SHA-256 hash of the API key

        Returns:
            APIKey if found, None otherwise
        """
        key_id = self._keys_by_hash.get(key_hash)
        if key_id:
            return self._keys_by_id.get(key_id)
        return None

    async def find_by_prefix(self, prefix: str) -> Optional[APIKey]:
        """Find an API key by its prefix.

        Args:
            prefix: First 8 characters of the API key

        Returns:
            APIKey if found, None otherwise
        """
        key_id = self._keys_by_prefix.get(prefix)
        if key_id:
            return self._keys_by_id.get(key_id)
        return None

    async def find_by_tenant(self, tenant_id: str) -> List[APIKey]:
        """Find all API keys for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            List of API keys for the tenant
        """
        return [
            key for key in self._keys_by_id.values()
            if key.tenant_id == tenant_id
        ]

    async def find_by_id(self, key_id: str) -> Optional[APIKey]:
        """Find an API key by its ID.

        Args:
            key_id: API key ID

        Returns:
            APIKey if found, None otherwise
        """
        return self._keys_by_id.get(key_id)

    async def update_last_used(self, key_id: str) -> None:
        """Update the last_used_at timestamp for a key.

        Args:
            key_id: API key ID
        """
        key = self._keys_by_id.get(key_id)
        if key:
            key.last_used_at = datetime.utcnow()

    async def deactivate(self, key_id: str) -> bool:
        """Deactivate an API key.

        Args:
            key_id: API key ID

        Returns:
            True if deactivated, False if not found
        """
        key = self._keys_by_id.get(key_id)
        if key:
            key.is_active = False
            logger.info(f"Deactivated API key: {key.name}")
            return True
        return False

    async def delete(self, key_id: str) -> bool:
        """Delete an API key.

        Args:
            key_id: API key ID

        Returns:
            True if deleted, False if not found
        """
        key = self._keys_by_id.get(key_id)
        if key:
            del self._keys_by_id[key_id]
            self._keys_by_hash.pop(key.key_hash, None)
            self._keys_by_prefix.pop(key.key_prefix, None)
            logger.info(f"Deleted API key: {key.name}")
            return True
        return False

    async def list_all(self, include_inactive: bool = False) -> List[APIKey]:
        """List all API keys.

        Args:
            include_inactive: Whether to include inactive keys

        Returns:
            List of all API keys
        """
        if include_inactive:
            return list(self._keys_by_id.values())
        return [key for key in self._keys_by_id.values() if key.is_active]

    def count(self) -> int:
        """Get the number of stored keys.

        Returns:
            Number of API keys
        """
        return len(self._keys_by_id)
