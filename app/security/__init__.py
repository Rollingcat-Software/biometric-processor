"""Security primitives for the biometric processor.

Phase 1.3b (Audit 2026-04-19 remediation) — KVKK 2018/10 compliant biometric
embedding encryption. Provides AES-GCM-256 envelope encryption helpers and
per-tenant DEK management for face and voice embeddings.

Public surface:
    * :class:`EmbeddingCipher` — AES-GCM-256 encrypt/decrypt with
      ``enc:v1:`` prefix, mirroring the Java ``TotpSecretCipher`` contract.
    * :class:`TenantDekStore` — per-tenant 256-bit DEK store wrapped by the
      env-sourced KEK.
    * :class:`EmbeddingMatchService` — decrypt-to-memory cosine matcher with
      per-tenant LRU cache, replacing pgvector operators once the plaintext
      columns are dropped (migration 0007).

The module MUST NOT log key material, decrypted bytes, or ciphertext payloads
at INFO or higher.
"""

from app.security.embedding_cipher import EmbeddingCipher
from app.security.embedding_match import EmbeddingMatchService
from app.security.tenant_dek_store import TenantDekStore

__all__ = [
    "EmbeddingCipher",
    "EmbeddingMatchService",
    "TenantDekStore",
]
