"""API key entity for authentication."""

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class APIKey:
    """API key entity for client authentication.

    Attributes:
        id: Unique API key identifier
        name: Human-readable name for the API key
        key_hash: SHA-256 hash of the API key (never store plaintext!)
        key_prefix: First 8 characters of key for identification
        tenant_id: Tenant this key belongs to
        scopes: List of allowed scopes/permissions
        tier: Rate limit tier (free, standard, premium, unlimited)
        is_active: Whether the key is currently active
        created_at: When the key was created
        last_used_at: When the key was last used
        expires_at: Optional expiration datetime
        metadata: Additional key metadata
    """

    id: str
    name: str
    key_hash: str
    key_prefix: str
    tenant_id: str
    scopes: List[str] = field(default_factory=lambda: ["read", "write"])
    tier: str = "standard"
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def generate_key() -> str:
        """Generate a new API key.

        Returns:
            32-byte hex-encoded API key (64 characters)
        """
        return secrets.token_hex(32)

    @staticmethod
    def hash_key(key: str) -> str:
        """Hash an API key using SHA-256.

        Args:
            key: Plaintext API key

        Returns:
            SHA-256 hash of the key
        """
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def get_prefix(key: str) -> str:
        """Get the prefix of an API key for identification.

        Args:
            key: Plaintext API key

        Returns:
            First 8 characters of the key
        """
        return key[:8]

    @classmethod
    def create_new(
        cls,
        name: str,
        tenant_id: str,
        scopes: Optional[List[str]] = None,
        tier: str = "standard",
        expires_at: Optional[datetime] = None,
        metadata: Optional[dict] = None,
    ) -> tuple["APIKey", str]:
        """Create a new API key entity.

        Args:
            name: Human-readable name
            tenant_id: Tenant identifier
            scopes: List of allowed scopes
            tier: Rate limit tier
            expires_at: Optional expiration datetime
            metadata: Additional metadata

        Returns:
            Tuple of (APIKey entity, plaintext key)
            NOTE: The plaintext key should only be shown once to the user!
        """
        import uuid

        plaintext_key = cls.generate_key()
        key_hash = cls.hash_key(plaintext_key)
        key_prefix = cls.get_prefix(plaintext_key)

        entity = cls(
            id=str(uuid.uuid4()),
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            tenant_id=tenant_id,
            scopes=scopes or ["read", "write"],
            tier=tier,
            expires_at=expires_at,
            metadata=metadata or {},
        )

        return entity, plaintext_key

    def verify(self, key: str) -> bool:
        """Verify if a plaintext key matches this API key.

        Args:
            key: Plaintext API key to verify

        Returns:
            True if the key matches
        """
        return self.key_hash == self.hash_key(key)

    def is_expired(self) -> bool:
        """Check if the API key is expired.

        Returns:
            True if expired, False otherwise
        """
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def is_valid(self) -> bool:
        """Check if the API key is valid (active and not expired).

        Returns:
            True if valid, False otherwise
        """
        return self.is_active and not self.is_expired()

    def has_scope(self, scope: str) -> bool:
        """Check if the API key has a specific scope.

        Args:
            scope: Scope to check

        Returns:
            True if the key has the scope
        """
        return scope in self.scopes or "*" in self.scopes

    def update_last_used(self) -> None:
        """Update the last_used_at timestamp."""
        self.last_used_at = datetime.utcnow()


@dataclass
class APIKeyContext:
    """Authentication context from API key validation.

    Passed to handlers after successful authentication.
    """

    key_id: str
    tenant_id: str
    scopes: List[str]
    tier: str
    name: str
