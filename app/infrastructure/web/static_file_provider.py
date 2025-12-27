"""Static file provider abstractions.

Implements Dependency Inversion Principle:
- High-level modules (routes) depend on abstractions (IStaticFileProvider)
- Low-level modules (LocalFileProvider) implement the abstraction
- Easy to swap implementations (e.g., S3Provider, CDNProvider)
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from fastapi.responses import FileResponse


class IStaticFileProvider(ABC):
    """Abstract interface for static file providers.

    Dependency Inversion Principle: Routes depend on this interface,
    not on concrete implementations.

    This allows:
    - Easy testing (mock implementations)
    - Future extensibility (S3, CDN, etc.)
    - Configuration-based provider selection
    """

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if file exists.

        Args:
            path: Relative path to file

        Returns:
            True if file exists
        """
        pass

    @abstractmethod
    async def get_response(self, path: str) -> FileResponse:
        """Get file response.

        Args:
            path: Relative path to file

        Returns:
            FileResponse for the file

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        pass

    @abstractmethod
    def get_base_dir(self) -> Path:
        """Get base directory.

        Returns:
            Base directory path
        """
        pass


class LocalFileProvider(IStaticFileProvider):
    """Local file system provider.

    Concrete implementation for serving files from local disk.
    """

    def __init__(self, base_dir: Path):
        """Initialize provider.

        Args:
            base_dir: Base directory for static files
        """
        self.base_dir = base_dir.resolve()

    async def exists(self, path: str) -> bool:
        """Check if file exists on local disk."""
        file_path = self.base_dir / path
        return file_path.is_file()

    async def get_response(self, path: str) -> FileResponse:
        """Get FileResponse for local file."""
        file_path = self.base_dir / path
        if not file_path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        return FileResponse(file_path)

    def get_base_dir(self) -> Path:
        """Get base directory."""
        return self.base_dir


# Future extension examples (not implemented):
#
# class S3FileProvider(IStaticFileProvider):
#     """S3 file provider for cloud storage."""
#
#     def __init__(self, bucket: str, prefix: str):
#         self.bucket = bucket
#         self.prefix = prefix
#
#     async def exists(self, path: str) -> bool:
#         # Check S3 object existence
#         pass
#
#     async def get_response(self, path: str) -> FileResponse:
#         # Stream from S3 or redirect to CloudFront
#         pass
#
# class CDNFileProvider(IStaticFileProvider):
#     """CDN provider that redirects to CDN URLs."""
#
#     def __init__(self, cdn_base_url: str):
#         self.cdn_base_url = cdn_base_url
#
#     async def get_response(self, path: str) -> FileResponse:
#         # Redirect to CDN
#         pass
