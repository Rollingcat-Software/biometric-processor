"""Delete enrollment use case."""

import logging
from typing import Optional

from app.domain.interfaces.embedding_repository import IEmbeddingRepository

logger = logging.getLogger(__name__)


class DeleteEnrollmentUseCase:
    """Use case for deleting a user's face enrollment.

    Removes the user's face embedding from the repository.

    Following Single Responsibility Principle: Only handles enrollment deletion.
    Dependencies are injected for testability (Dependency Inversion Principle).
    """

    def __init__(self, repository: IEmbeddingRepository) -> None:
        self._repository = repository

    async def execute(
        self, user_id: str, tenant_id: Optional[str] = None
    ) -> bool:
        """Delete face enrollment for a user.

        Args:
            user_id: User identifier whose enrollment should be deleted
            tenant_id: Optional tenant identifier for multi-tenancy

        Returns:
            True if enrollment was deleted, False if not found
        """
        logger.info(f"Deleting enrollment for user: {user_id}, tenant: {tenant_id}")

        deleted = await self._repository.delete(
            user_id=user_id, tenant_id=tenant_id
        )

        if deleted:
            logger.info(f"Successfully deleted enrollment for user: {user_id}")
        else:
            logger.warning(f"No enrollment found for user: {user_id}")

        return deleted
