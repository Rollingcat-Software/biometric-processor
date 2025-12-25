"""Import embeddings use case."""

import hashlib
import json
import logging
from typing import Any, Dict, List, Literal

from app.domain.exceptions.feature_errors import (
    EmbeddingImportError,
    ImportValidationError,
)
from app.domain.interfaces.embedding_repository import IEmbeddingRepository

logger = logging.getLogger(__name__)

ImportMode = Literal["merge", "replace", "skip_existing"]


class ImportEmbeddingsUseCase:
    """Use case for importing face embeddings.

    Imports embeddings from JSON format for restore or migration.
    """

    def __init__(self, repository: IEmbeddingRepository) -> None:
        """Initialize import embeddings use case.

        Args:
            repository: Embedding repository implementation
        """
        self._repository = repository
        logger.info("ImportEmbeddingsUseCase initialized")

    async def execute(
        self,
        import_data: Dict[str, Any],
        mode: ImportMode = "merge",
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Execute embedding import.

        Args:
            import_data: Export data dictionary
            mode: Import mode (merge, replace, skip_existing)
            tenant_id: Target tenant ID

        Returns:
            Import result with statistics

        Raises:
            ImportValidationError: If validation fails
            EmbeddingImportError: If import fails
        """
        logger.info(f"Starting embedding import (mode={mode})")

        # Validate import data
        self._validate_import_data(import_data)

        embeddings = import_data.get("embeddings", [])
        results = {
            "success": True,
            "imported": 0,
            "skipped": 0,
            "errors": 0,
            "details": [],
        }

        # Handle replace mode
        if mode == "replace":
            await self._clear_existing(tenant_id)

        # Import each embedding
        for entry in embeddings:
            try:
                status = await self._import_single(entry, mode, tenant_id)
                results["details"].append(
                    {"user_id": entry["user_id"], "status": status}
                )

                if status == "imported":
                    results["imported"] += 1
                elif status == "skipped":
                    results["skipped"] += 1
                    results["details"][-1]["reason"] = "already_exists"

            except Exception as e:
                logger.warning(f"Failed to import {entry['user_id']}: {e}")
                results["errors"] += 1
                results["details"].append(
                    {
                        "user_id": entry["user_id"],
                        "status": "error",
                        "reason": str(e),
                    }
                )

        results["success"] = results["errors"] == 0

        logger.info(
            f"Import complete: imported={results['imported']}, "
            f"skipped={results['skipped']}, errors={results['errors']}"
        )

        return results

    def _validate_import_data(self, data: Dict[str, Any]) -> None:
        """Validate import data structure and embedding quality.

        SECURITY FIX: Comprehensive validation prevents corrupt/malicious data import.
        Validates dimensions, value ranges, normalization, and checksums.
        """
        required_fields = ["version", "embeddings"]
        for field in required_fields:
            if field not in data:
                raise ImportValidationError(f"Missing required field: {field}")

        if not isinstance(data["embeddings"], list):
            raise ImportValidationError("embeddings must be a list")

        # Validate checksum if present
        if "checksum" in data:
            content = json.dumps(data["embeddings"], sort_keys=True)
            expected = hashlib.sha256(content.encode()).hexdigest()
            actual = data["checksum"].replace("sha256:", "")

            if expected != actual:
                raise ImportValidationError("Checksum validation failed")

        # Get expected dimension from first entry (all must match)
        expected_dim = None
        if data["embeddings"]:
            expected_dim = len(data["embeddings"][0].get("embedding", []))

        # Validate each embedding entry
        for i, entry in enumerate(data["embeddings"]):
            if "user_id" not in entry:
                raise ImportValidationError(f"Entry {i} missing user_id")
            if "embedding" not in entry:
                raise ImportValidationError(f"Entry {i} missing embedding")
            if not isinstance(entry["embedding"], list):
                raise ImportValidationError(f"Entry {i} embedding must be a list")

            # CRITICAL FIX: Validate embedding dimensions
            embedding = entry["embedding"]
            if len(embedding) < 128:  # Minimum realistic dimension
                raise ImportValidationError(
                    f"Entry {i} ({entry['user_id']}): "
                    f"embedding dimension too small ({len(embedding)}), expected >= 128"
                )

            if expected_dim and len(embedding) != expected_dim:
                raise ImportValidationError(
                    f"Entry {i} ({entry['user_id']}): "
                    f"dimension mismatch ({len(embedding)} vs {expected_dim})"
                )

            # CRITICAL FIX: Validate all values are numeric
            try:
                import numpy as np
                emb_array = np.array(embedding, dtype=np.float32)

                # Check for NaN or Inf
                if np.any(np.isnan(emb_array)) or np.any(np.isinf(emb_array)):
                    raise ImportValidationError(
                        f"Entry {i} ({entry['user_id']}): "
                        f"embedding contains NaN or Inf values"
                    )

                # Check value range (embeddings should be normalized)
                if np.max(np.abs(emb_array)) > 10.0:
                    raise ImportValidationError(
                        f"Entry {i} ({entry['user_id']}): "
                        f"embedding values out of range (max={np.max(np.abs(emb_array))}), "
                        f"expected normalized values"
                    )

            except (ValueError, TypeError) as e:
                raise ImportValidationError(
                    f"Entry {i} ({entry['user_id']}): "
                    f"invalid embedding values - {str(e)}"
                )

    async def _import_single(
        self, entry: Dict[str, Any], mode: ImportMode, tenant_id: str
    ) -> str:
        """Import single embedding entry."""
        user_id = entry["user_id"]
        embedding = entry["embedding"]
        metadata = entry.get("metadata", {})

        # Check if exists
        existing = await self._repository.get(user_id, tenant_id)

        if existing:
            if mode == "skip_existing":
                return "skipped"
            elif mode == "merge":
                # Update existing
                await self._repository.update(
                    user_id=user_id,
                    embedding=embedding,
                    tenant_id=tenant_id,
                    metadata=metadata,
                )
                return "imported"

        # Create new
        await self._repository.save(
            user_id=user_id,
            embedding=embedding,
            tenant_id=tenant_id,
            metadata=metadata,
        )
        return "imported"

    async def _clear_existing(self, tenant_id: str) -> None:
        """Clear all existing embeddings for tenant."""
        try:
            await self._repository.delete_all(tenant_id)
        except AttributeError:
            logger.warning("Repository does not support delete_all")
