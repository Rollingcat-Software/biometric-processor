"""File storage interface for temporary file handling."""

from typing import Protocol
from fastapi import UploadFile


class IFileStorage(Protocol):
    """Protocol for file storage implementations.

    Abstracts file I/O operations, allowing different storage backends
    (local filesystem, S3, MinIO, etc.) without changing business logic.
    """

    async def save_temp(self, file: UploadFile) -> str:
        """Save uploaded file to temporary storage.

        Args:
            file: Uploaded file from FastAPI

        Returns:
            Absolute path to the saved file

        Raises:
            FileStorageError: When save operation fails

        Note:
            File is saved with a unique name to avoid collisions.
            Caller is responsible for cleanup using cleanup() method.
        """
        ...

    async def cleanup(self, file_path: str) -> None:
        """Delete temporary file.

        Args:
            file_path: Absolute path to file to delete

        Raises:
            FileStorageError: When delete operation fails

        Note:
            Should not raise error if file doesn't exist (idempotent).
        """
        ...

    async def read_as_bytes(self, file_path: str) -> bytes:
        """Read file contents as bytes.

        Args:
            file_path: Absolute path to file

        Returns:
            File contents as bytes

        Raises:
            FileStorageError: When file doesn't exist or read fails
        """
        ...

    def get_storage_path(self) -> str:
        """Get the root storage path.

        Returns:
            Absolute path to storage directory
        """
        ...
