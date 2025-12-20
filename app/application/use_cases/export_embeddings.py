"""Export embeddings use case."""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.domain.exceptions.feature_errors import ExportError
from app.domain.interfaces.embedding_repository import IEmbeddingRepository

logger = logging.getLogger(__name__)


class ExportEmbeddingsUseCase:
    """Use case for exporting face embeddings.

    Exports embeddings to JSON format for backup or migration.
    """

    def __init__(self, repository: IEmbeddingRepository) -> None:
        """Initialize export embeddings use case.

        Args:
            repository: Embedding repository implementation
        """
        self._repository = repository
        logger.info("ExportEmbeddingsUseCase initialized")

    async def execute(
        self,
        tenant_id: str = "default",
        model: str = "Facenet",
        include_metadata: bool = True,
    ) -> Dict[str, Any]:
        """Execute embedding export.

        Args:
            tenant_id: Tenant to export embeddings for
            model: Model name used for embeddings
            include_metadata: Whether to include metadata

        Returns:
            Dictionary with export data

        Raises:
            ExportError: If export fails
        """
        logger.info(f"Starting embedding export for tenant: {tenant_id}")

        try:
            # Get all embeddings from repository
            embeddings_data = await self._get_all_embeddings(tenant_id)

            # Build export structure
            export_data = {
                "version": "1.0",
                "export_date": datetime.utcnow().isoformat() + "Z",
                "tenant_id": tenant_id,
                "model": model,
                "embedding_dimension": self._get_embedding_dimension(embeddings_data),
                "count": len(embeddings_data),
                "embeddings": embeddings_data if include_metadata else self._strip_metadata(embeddings_data),
            }

            # Calculate checksum
            content = json.dumps(export_data["embeddings"], sort_keys=True)
            checksum = hashlib.sha256(content.encode()).hexdigest()
            export_data["checksum"] = f"sha256:{checksum}"

            logger.info(
                f"Export complete: {len(embeddings_data)} embeddings, "
                f"checksum={checksum[:16]}..."
            )

            return export_data

        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise ExportError(f"Export failed: {str(e)}")

    async def _get_all_embeddings(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get all embeddings from repository."""
        embeddings = []

        # Get all user IDs
        try:
            all_users = await self._repository.list_all(tenant_id)
        except AttributeError:
            # Fallback if repository doesn't have list_all
            all_users = []

        for user_data in all_users:
            user_id = user_data.get("user_id") or user_data.get("id")
            embedding = user_data.get("embedding", [])

            embeddings.append(
                {
                    "user_id": user_id,
                    "embedding": embedding if isinstance(embedding, list) else embedding.tolist(),
                    "created_at": user_data.get("created_at", datetime.utcnow().isoformat()),
                    "metadata": user_data.get("metadata", {}),
                }
            )

        return embeddings

    def _get_embedding_dimension(self, embeddings: List[Dict]) -> int:
        """Get embedding dimension from first embedding."""
        if embeddings and embeddings[0].get("embedding"):
            return len(embeddings[0]["embedding"])
        return 128  # Default for Facenet

    def _strip_metadata(self, embeddings: List[Dict]) -> List[Dict]:
        """Remove metadata from embeddings."""
        return [
            {
                "user_id": e["user_id"],
                "embedding": e["embedding"],
                "created_at": e["created_at"],
            }
            for e in embeddings
        ]
