"""Local filesystem storage implementation."""

import logging
import os
import uuid
from pathlib import Path
from typing import Optional
from fastapi import UploadFile

from app.domain.interfaces.file_storage import IFileStorage
from app.domain.exceptions.storage_errors import FileStorageError

logger = logging.getLogger(__name__)


class LocalFileStorage:
    """Local filesystem storage implementation.

    Implements IFileStorage interface for storing files on local filesystem.
    Following Repository Pattern for file operations.

    Note:
        This is suitable for development and small-scale deployments.
        For production at scale, consider S3Storage or similar.
    """

    def __init__(self, storage_path: str = "./temp_uploads") -> None:
        """Initialize local file storage.

        Args:
            storage_path: Directory path for storing files

        Raises:
            FileStorageError: If storage directory cannot be created
        """
        self._storage_path = Path(storage_path)

        # Create storage directory if it doesn't exist
        try:
            self._storage_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Initialized LocalFileStorage at: {self._storage_path.absolute()}")
        except Exception as e:
            logger.error(f"Failed to create storage directory: {e}")
            raise FileStorageError(
                operation="initialize",
                file_path=str(self._storage_path),
                reason=str(e),
            )

    async def save_temp(self, file: UploadFile) -> str:
        """Save uploaded file to temporary storage.

        Args:
            file: Uploaded file from FastAPI

        Returns:
            Absolute path to saved file

        Raises:
            FileStorageError: When save operation fails
        """
        try:
            # Generate unique filename
            file_extension = self._get_file_extension(file.filename or "")
            temp_filename = f"{uuid.uuid4()}{file_extension}"
            temp_file_path = self._storage_path / temp_filename

            logger.debug(f"Saving file: {file.filename} -> {temp_filename}")

            # Read file content
            content = await file.read()

            # Write to disk
            with open(temp_file_path, "wb") as buffer:
                buffer.write(content)

            absolute_path = str(temp_file_path.absolute())

            logger.info(
                f"File saved successfully: {absolute_path} "
                f"({len(content)} bytes)"
            )

            return absolute_path

        except Exception as e:
            logger.error(f"Failed to save file: {e}", exc_info=True)
            raise FileStorageError(
                operation="save",
                file_path=file.filename or "unknown",
                reason=str(e),
            )

    async def cleanup(self, file_path: str) -> None:
        """Delete temporary file.

        Args:
            file_path: Absolute path to file to delete

        Note:
            This method is idempotent - no error if file doesn't exist.
        """
        try:
            path = Path(file_path)

            if path.exists():
                path.unlink()
                logger.debug(f"File deleted: {file_path}")
            else:
                logger.debug(f"File already deleted or doesn't exist: {file_path}")

        except Exception as e:
            # Log warning but don't raise - cleanup is best-effort
            logger.warning(f"Failed to delete file {file_path}: {e}")

    async def read_as_bytes(self, file_path: str) -> bytes:
        """Read file contents as bytes.

        Args:
            file_path: Absolute path to file

        Returns:
            File contents as bytes

        Raises:
            FileStorageError: When file doesn't exist or read fails
        """
        try:
            path = Path(file_path)

            if not path.exists():
                raise FileStorageError(
                    operation="read",
                    file_path=file_path,
                    reason="File not found",
                )

            with open(path, "rb") as f:
                content = f.read()

            logger.debug(f"File read: {file_path} ({len(content)} bytes)")

            return content

        except FileStorageError:
            raise
        except Exception as e:
            logger.error(f"Failed to read file: {e}", exc_info=True)
            raise FileStorageError(
                operation="read",
                file_path=file_path,
                reason=str(e),
            )

    def get_storage_path(self) -> str:
        """Get the root storage path.

        Returns:
            Absolute path to storage directory
        """
        return str(self._storage_path.absolute())

    def exists(self, file_path: str) -> bool:
        """Check if file exists.

        Args:
            file_path: Absolute path to file

        Returns:
            True if file exists
        """
        return Path(file_path).exists()

    def get_file_size(self, file_path: str) -> Optional[int]:
        """Get file size in bytes.

        Args:
            file_path: Absolute path to file

        Returns:
            File size in bytes, None if file doesn't exist
        """
        path = Path(file_path)
        if path.exists():
            return path.stat().st_size
        return None

    @staticmethod
    def _get_file_extension(filename: str) -> str:
        """Extract file extension from filename.

        Args:
            filename: Original filename

        Returns:
            File extension including dot (e.g., ".jpg")
            Returns "" if no extension
        """
        if not filename:
            return ""

        _, ext = os.path.splitext(filename)
        return ext.lower()

    def cleanup_old_files(self, max_age_hours: int = 24) -> int:
        """Cleanup files older than specified age.

        Args:
            max_age_hours: Maximum file age in hours

        Returns:
            Number of files deleted
        """
        import time

        deleted_count = 0
        max_age_seconds = max_age_hours * 3600
        current_time = time.time()

        try:
            for file_path in self._storage_path.iterdir():
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime

                    if file_age > max_age_seconds:
                        try:
                            file_path.unlink()
                            deleted_count += 1
                            logger.debug(f"Deleted old file: {file_path}")
                        except Exception as e:
                            logger.warning(f"Failed to delete {file_path}: {e}")

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old files")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

        return deleted_count
