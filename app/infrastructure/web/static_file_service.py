"""Static file serving service.

Implements Single Responsibility Principle:
- Main responsibility: Serve static files securely
- Separated from main.py (application setup)
- Testable in isolation
"""

import logging
import time
from mimetypes import guess_type
from pathlib import Path
from typing import Optional, Set
from fastapi import HTTPException
from fastapi.responses import FileResponse, JSONResponse

from .file_resolution_strategies import FileResolver, create_default_resolver
from .static_file_provider import IStaticFileProvider, LocalFileProvider


logger = logging.getLogger(__name__)


class StaticFileService:
    """Service for serving static files with security and caching.

    Single Responsibility: Handles all static file serving logic.

    Features:
    - Path traversal protection
    - Content-Type validation
    - File resolution strategies
    - Caching headers
    - Security logging
    - Performance monitoring

    Design Patterns:
    - Strategy Pattern: File resolution
    - Dependency Injection: File provider
    - Service Pattern: Encapsulated business logic
    """

    def __init__(
        self,
        file_provider: IStaticFileProvider,
        file_resolver: Optional[FileResolver] = None,
        allowed_content_types: Optional[Set[str]] = None,
        cache_max_age: int = 31536000,  # 1 year for static assets
        html_cache_max_age: int = 0,  # No cache for HTML (revalidate)
    ):
        """Initialize static file service.

        Args:
            file_provider: Provider for file access
            file_resolver: File resolution strategy chain (None = default)
            allowed_content_types: Whitelisted MIME types (None = default)
            cache_max_age: Cache duration for static assets (seconds)
            html_cache_max_age: Cache duration for HTML files (seconds)
        """
        self.file_provider = file_provider
        self.file_resolver = file_resolver or create_default_resolver()
        self.allowed_content_types = allowed_content_types or self._default_allowed_types()
        self.cache_max_age = cache_max_age
        self.html_cache_max_age = html_cache_max_age

    @staticmethod
    def _default_allowed_types() -> Set[str]:
        """Get default allowed content types."""
        return {
            'text/html',
            'text/css',
            'text/javascript',
            'text/plain',  # Required for Next.js RSC data files
            'application/javascript',
            'application/json',
            'application/octet-stream',  # Required for Next.js RSC payloads
            'image/png',
            'image/jpeg',
            'image/svg+xml',
            'image/webp',
            'image/x-icon',
            'image/gif',
            'font/woff',
            'font/woff2',
            'font/ttf',
            'font/otf',
        }

    def is_safe_path(self, user_path: str) -> bool:
        """Validate path is within base directory.

        Security: Prevents path traversal attacks (e.g., ../../etc/passwd).

        Args:
            user_path: User-provided path to validate

        Returns:
            True if path is safe
        """
        try:
            base_dir = self.file_provider.get_base_dir()
            abs_base = base_dir.resolve()
            abs_user = (base_dir / user_path).resolve()

            # Python 3.9+ compatibility
            try:
                return abs_user.is_relative_to(abs_base)
            except AttributeError:
                # Fallback for Python < 3.9
                try:
                    abs_user.relative_to(abs_base)
                    return True
                except ValueError:
                    return False

        except (ValueError, RuntimeError, OSError):
            return False

    def validate_content_type(self, file_path: Path) -> str:
        """Validate and get content type for file.

        Security: Only allows whitelisted MIME types.

        Args:
            file_path: Path to file

        Returns:
            Validated content type

        Raises:
            HTTPException: If content type not allowed
        """
        content_type, _ = guess_type(str(file_path))

        if content_type is None:
            logger.warning(f"Could not determine content type for: {file_path.name}")
            content_type = 'application/octet-stream'

        if content_type not in self.allowed_content_types:
            logger.warning(
                f"Blocked unsafe content type: {content_type} for file: {file_path.name}"
            )
            raise HTTPException(
                status_code=403,
                detail="Forbidden file type"
            )

        return content_type

    def create_file_response(
        self,
        file_path: Path,
        content_type: Optional[str] = None
    ) -> FileResponse:
        """Create FileResponse with caching headers.

        Performance: Adds appropriate cache headers based on file type.

        Args:
            file_path: Path to file
            content_type: Content type (None = auto-detect)

        Returns:
            FileResponse with cache headers
        """
        # Validate and get content type
        if content_type is None:
            content_type = self.validate_content_type(file_path)

        # Create response
        response = FileResponse(file_path, media_type=content_type)

        # Add cache headers based on content type
        if content_type == 'text/html':
            # HTML: Revalidate every time (for SPA routing)
            response.headers["Cache-Control"] = (
                f"public, max-age={self.html_cache_max_age}, must-revalidate"
            )
        else:
            # Static assets: Long-term caching (Next.js uses hashed filenames)
            response.headers["Cache-Control"] = (
                f"public, max-age={self.cache_max_age}, immutable"
            )

        return response

    async def serve_file(self, path: str) -> FileResponse | JSONResponse:
        """Serve static file with security validation.

        Main entry point for serving files.

        Args:
            path: User-provided path

        Returns:
            FileResponse or JSONResponse (404)

        Raises:
            HTTPException: For security violations or errors
        """
        start_time = time.time()

        try:
            # Don't serve API routes
            if path.startswith("api/"):
                logger.warning(f"API path reached static file service: {path}")
                return JSONResponse(
                    status_code=404,
                    content={"detail": "API endpoint not found"}
                )

            # Security: Validate path safety
            if not self.is_safe_path(path):
                logger.warning(f"Path traversal attempt blocked: {path}")
                raise HTTPException(status_code=403, detail="Forbidden")

            # Resolve file using strategy chain
            base_dir = self.file_provider.get_base_dir()
            resolved_file, strategy_name = self.file_resolver.resolve(base_dir, path)

            if resolved_file:
                # Validate content type and create response
                content_type = self.validate_content_type(resolved_file)
                response = self.create_file_response(resolved_file, content_type)

                # Log success
                elapsed_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Served {path} via {strategy_name} ({elapsed_ms:.2f}ms)",
                    extra={
                        "path": path,
                        "resolved": str(resolved_file),
                        "strategy": strategy_name,
                        "elapsed_ms": elapsed_ms,
                        "content_type": content_type,
                    }
                )
                return response

            # Not found
            logger.warning(f"Static file not found: {path}")
            return JSONResponse(
                status_code=404,
                content={"detail": "Page not found"}
            )

        except HTTPException:
            # Re-raise HTTP exceptions
            raise

        except PermissionError as e:
            logger.error(f"Permission denied accessing {path}: {e}")
            raise HTTPException(status_code=403, detail="Access forbidden")

        except OSError as e:
            logger.error(f"File system error for {path}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

        except Exception as e:
            logger.exception(f"Unexpected error serving {path}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    async def serve_specific_file(self, file_name: str) -> FileResponse | JSONResponse:
        """Serve a specific file (e.g., icon.svg).

        Args:
            file_name: Name of file to serve

        Returns:
            FileResponse or JSONResponse (404)
        """
        try:
            # Validate path safety
            if not self.is_safe_path(file_name):
                raise HTTPException(status_code=403, detail="Forbidden")

            base_dir = self.file_provider.get_base_dir()
            file_path = base_dir / file_name

            if file_path.is_file():
                content_type = self.validate_content_type(file_path)
                return self.create_file_response(file_path, content_type)

            return JSONResponse(
                status_code=404,
                content={"detail": f"{file_name} not found"}
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error serving {file_name}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")


def create_static_file_service(base_dir: Path) -> StaticFileService:
    """Factory function for creating static file service.

    Args:
        base_dir: Base directory for static files

    Returns:
        Configured StaticFileService
    """
    file_provider = LocalFileProvider(base_dir)
    file_resolver = create_default_resolver()

    return StaticFileService(
        file_provider=file_provider,
        file_resolver=file_resolver,
    )
