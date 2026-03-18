"""Unit tests for LocalFileStorage."""

import pytest
import tempfile
import shutil
from pathlib import Path
from fastapi import UploadFile
import io

from app.infrastructure.storage.local_file_storage import LocalFileStorage
from app.domain.exceptions.storage_errors import FileStorageError


class TestLocalFileStorage:
    """Test LocalFileStorage."""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create temporary storage directory for tests."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup after test
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_initialization(self, temp_storage_dir):
        """Test initialization creates storage directory."""
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        assert storage.get_storage_path() == str(Path(temp_storage_dir).absolute())
        assert Path(temp_storage_dir).exists()

    def test_initialization_creates_nested_directories(self, temp_storage_dir):
        """Test initialization creates nested directories."""
        nested_path = str(Path(temp_storage_dir) / "nested" / "dirs")
        storage = LocalFileStorage(storage_path=nested_path)

        assert Path(nested_path).exists()

    @pytest.mark.asyncio
    async def test_save_temp_success(self, temp_storage_dir):
        """Test saving uploaded file successfully."""
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        # Create mock uploaded file
        content = b"test image content"
        file = self._create_upload_file("test.jpg", content)

        # Save
        saved_path = await storage.save_temp(file)

        # Verify
        assert Path(saved_path).exists()
        assert Path(saved_path).parent == Path(temp_storage_dir)
        with open(saved_path, "rb") as f:
            assert f.read() == content

    @pytest.mark.asyncio
    async def test_save_temp_generates_unique_filename(self, temp_storage_dir):
        """Test that save_temp generates unique filenames."""
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        file1 = self._create_upload_file("test.jpg", b"content1")
        file2 = self._create_upload_file("test.jpg", b"content2")

        path1 = await storage.save_temp(file1)
        path2 = await storage.save_temp(file2)

        # Paths should be different
        assert path1 != path2

    @pytest.mark.asyncio
    async def test_save_temp_preserves_extension(self, temp_storage_dir):
        """Test that file extension is preserved."""
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        extensions = [".jpg", ".png", ".gif", ".txt"]

        for ext in extensions:
            file = self._create_upload_file(f"test{ext}", b"content")
            path = await storage.save_temp(file)

            assert Path(path).suffix == ext

    @pytest.mark.asyncio
    async def test_save_temp_no_extension(self, temp_storage_dir):
        """Test saving file without extension."""
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        file = self._create_upload_file("testfile", b"content")
        path = await storage.save_temp(file)

        # Should save successfully, no extension
        assert Path(path).exists()
        assert Path(path).suffix == ""

    @pytest.mark.asyncio
    async def test_cleanup_existing_file(self, temp_storage_dir):
        """Test cleanup deletes existing file."""
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        # Save a file
        file = self._create_upload_file("test.jpg", b"content")
        saved_path = await storage.save_temp(file)

        assert Path(saved_path).exists()

        # Cleanup
        await storage.cleanup(saved_path)

        assert not Path(saved_path).exists()

    @pytest.mark.asyncio
    async def test_cleanup_non_existing_file(self, temp_storage_dir):
        """Test cleanup is idempotent for non-existent files."""
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        # Cleanup non-existent file should not raise error
        await storage.cleanup("/nonexistent/path/file.jpg")

    @pytest.mark.asyncio
    async def test_read_as_bytes_success(self, temp_storage_dir):
        """Test reading file as bytes."""
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        # Save a file
        content = b"test file content"
        file = self._create_upload_file("test.txt", content)
        saved_path = await storage.save_temp(file)

        # Read
        read_content = await storage.read_as_bytes(saved_path)

        assert read_content == content

    @pytest.mark.asyncio
    async def test_read_as_bytes_file_not_found(self, temp_storage_dir):
        """Test reading non-existent file raises error."""
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        with pytest.raises(FileStorageError, match="File not found"):
            await storage.read_as_bytes("/nonexistent/file.txt")

    def test_exists_true(self, temp_storage_dir):
        """Test exists returns True for existing file."""
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        # Create a file
        test_file = Path(temp_storage_dir) / "test.txt"
        test_file.write_text("content")

        assert storage.exists(str(test_file)) is True

    def test_exists_false(self, temp_storage_dir):
        """Test exists returns False for non-existent file."""
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        assert storage.exists("/nonexistent/file.txt") is False

    def test_get_file_size_existing(self, temp_storage_dir):
        """Test getting file size for existing file."""
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        # Create a file
        content = b"test content"
        test_file = Path(temp_storage_dir) / "test.txt"
        test_file.write_bytes(content)

        size = storage.get_file_size(str(test_file))

        assert size == len(content)

    def test_get_file_size_non_existing(self, temp_storage_dir):
        """Test getting file size for non-existent file."""
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        size = storage.get_file_size("/nonexistent/file.txt")

        assert size is None

    def test_get_file_extension(self):
        """Test extracting file extension."""
        assert LocalFileStorage._get_file_extension("test.jpg") == ".jpg"
        assert LocalFileStorage._get_file_extension("test.PNG") == ".png"
        assert LocalFileStorage._get_file_extension("file.tar.gz") == ".gz"
        assert LocalFileStorage._get_file_extension("noextension") == ""
        assert LocalFileStorage._get_file_extension("") == ""

    def test_cleanup_old_files(self, temp_storage_dir):
        """Test cleaning up old files."""
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        # Create old file (modify mtime)
        old_file = Path(temp_storage_dir) / "old.txt"
        old_file.write_text("old content")

        # Manually set modification time to 48 hours ago
        import time
        old_time = time.time() - (48 * 3600)
        import os
        os.utime(old_file, (old_time, old_time))

        # Create recent file
        recent_file = Path(temp_storage_dir) / "recent.txt"
        recent_file.write_text("recent content")

        # Cleanup files older than 24 hours
        deleted_count = storage.cleanup_old_files(max_age_hours=24)

        # Old file should be deleted
        assert not old_file.exists()
        assert recent_file.exists()
        assert deleted_count == 1

    def test_cleanup_old_files_no_old_files(self, temp_storage_dir):
        """Test cleanup when there are no old files."""
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        # Create recent file
        recent_file = Path(temp_storage_dir) / "recent.txt"
        recent_file.write_text("recent content")

        # Cleanup
        deleted_count = storage.cleanup_old_files(max_age_hours=24)

        assert deleted_count == 0
        assert recent_file.exists()

    def test_get_storage_path(self, temp_storage_dir):
        """Test getting storage path."""
        storage = LocalFileStorage(storage_path=temp_storage_dir)

        path = storage.get_storage_path()

        assert path == str(Path(temp_storage_dir).absolute())

    @staticmethod
    def _create_upload_file(filename: str, content: bytes) -> UploadFile:
        """Create mock UploadFile for testing.

        Args:
            filename: Filename
            content: File content as bytes

        Returns:
            Mock UploadFile
        """
        file = UploadFile(
            filename=filename,
            file=io.BytesIO(content)
        )
        return file
