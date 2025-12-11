"""API key repository interface."""

from typing import List, Optional, Protocol

from app.domain.entities.api_key import APIKey


class IAPIKeyRepository(Protocol):
    """Interface for API key storage and retrieval.

    Implementations handle secure storage of API key metadata.
    Note: Only key hashes are stored, never plaintext keys.
    """

    async def save(self, api_key: APIKey) -> None:
        """Save an API key.

        Args:
            api_key: API key entity to save
        """
        ...

    async def find_by_key_hash(self, key_hash: str) -> Optional[APIKey]:
        """Find an API key by its hash.

        Args:
            key_hash: SHA-256 hash of the API key

        Returns:
            APIKey if found, None otherwise
        """
        ...

    async def find_by_prefix(self, prefix: str) -> Optional[APIKey]:
        """Find an API key by its prefix.

        Useful for quick lookups before full hash verification.

        Args:
            prefix: First 8 characters of the API key

        Returns:
            APIKey if found, None otherwise
        """
        ...

    async def find_by_tenant(self, tenant_id: str) -> List[APIKey]:
        """Find all API keys for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            List of API keys for the tenant
        """
        ...

    async def find_by_id(self, key_id: str) -> Optional[APIKey]:
        """Find an API key by its ID.

        Args:
            key_id: API key ID

        Returns:
            APIKey if found, None otherwise
        """
        ...

    async def update_last_used(self, key_id: str) -> None:
        """Update the last_used_at timestamp for a key.

        Args:
            key_id: API key ID
        """
        ...

    async def deactivate(self, key_id: str) -> bool:
        """Deactivate an API key.

        Args:
            key_id: API key ID

        Returns:
            True if deactivated, False if not found
        """
        ...

    async def delete(self, key_id: str) -> bool:
        """Delete an API key.

        Args:
            key_id: API key ID

        Returns:
            True if deleted, False if not found
        """
        ...

    async def list_all(self, include_inactive: bool = False) -> List[APIKey]:
        """List all API keys.

        Args:
            include_inactive: Whether to include inactive keys

        Returns:
            List of all API keys
        """
        ...
