"""FastAPI application entry point.

This module creates and configures the FastAPI application with:
- Clean Architecture layers
- Dependency injection
- Error handling
- Security (CORS, rate limiting)
- Structured logging
- API documentation
"""

import logging
import time
from contextlib import asynccontextmanager
from mimetypes import guess_type
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.middleware.error_handler import setup_exception_handlers
from app.api.middleware.rate_limit import RateLimitMiddleware
from app.api.routes import batch, enrollment, health, liveness, search, verification, card_type_router
from app.api.routes import quality, multi_face, demographics, landmarks, comparison, similarity_matrix, embeddings_io, webhooks
from app.api.routes import proctor
from app.api.routes import proctor_ws
from app.api.routes import admin
from app.api.routes import live_analysis
from app.core.config import settings
from app.core.container import initialize_dependencies, shutdown_dependencies, shutdown_thread_pool
from app.infrastructure.rate_limit.storage_factory import RateLimitStorageFactory

# Configure logging
if settings.LOG_FORMAT == "json":
    # Use structured logging for JSON format
    from app.core.logging import configure_logging, get_logger
    configure_logging(
        log_level=settings.LOG_LEVEL,
        log_format="json",
        service_name=settings.APP_NAME,
        version=settings.VERSION,
    )
    logger = get_logger(__name__)
else:
    # Use standard logging for text format
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown events including:
    - ML model pre-loading at startup
    - Thread pool shutdown at exit
    - Rate limit storage cleanup
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Face Detection: {settings.FACE_DETECTION_BACKEND}")
    logger.info(f"Face Recognition Model: {settings.FACE_RECOGNITION_MODEL}")
    logger.info(f"Async ML: {settings.ASYNC_ML_ENABLED}")
    logger.info(f"Embedding Cache: {settings.EMBEDDING_CACHE_ENABLED}")

    # Initialize dependencies (pre-load ML models, create thread pool, etc.)
    logger.info("Initializing dependencies...")
    initialize_dependencies()
    logger.info("Dependencies initialized")

    yield

    # Shutdown
    logger.info("Shutting down application...")

    # CRITICAL: Shutdown all dependencies gracefully (thread pool, database, event bus, etc.)
    logger.info("Shutting down dependencies...")
    await shutdown_dependencies(wait=True)

    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="AI/ML microservice for face recognition and liveness detection",
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.is_development() else None,  # Disable docs in production
    redoc_url="/redoc" if settings.is_development() else None,
)

# ============================================================================
# Rate Limiting Middleware
# ============================================================================

if settings.RATE_LIMIT_ENABLED:
    rate_limit_storage = RateLimitStorageFactory.create(
        backend=settings.RATE_LIMIT_STORAGE,
        redis_url=settings.redis_url,
    )
    app.add_middleware(
        RateLimitMiddleware,
        storage=rate_limit_storage,
        default_limit=settings.RATE_LIMIT_PER_MINUTE,
        window_seconds=60,
    )
    logger.info(f"Rate limiting enabled: {settings.RATE_LIMIT_PER_MINUTE} requests/minute")

# ============================================================================
# CORS Configuration (SECURITY FIX - No Wildcard!)
# IMPORTANT: CORS must be added LAST so it runs FIRST (middleware stack is LIFO)
# ============================================================================

cors_config = settings.get_cors_config()
logger.info(f"CORS allowed origins: {cors_config['allow_origins']}")

app.add_middleware(
    CORSMiddleware,
    **cors_config,
)

# ============================================================================
# Exception Handlers
# ============================================================================

setup_exception_handlers(app)

# ============================================================================
# API Routes
# ============================================================================

# Include routers with /api/v1 prefix
API_PREFIX = "/api/v1"

app.include_router(health.router, prefix=API_PREFIX)
app.include_router(enrollment.router, prefix=API_PREFIX)
app.include_router(verification.router, prefix=API_PREFIX)
app.include_router(liveness.router, prefix=API_PREFIX)
app.include_router(search.router, prefix=API_PREFIX)
app.include_router(batch.router, prefix=API_PREFIX)
app.include_router(card_type_router.router, prefix=API_PREFIX)

# New feature routes
app.include_router(quality.router, prefix=API_PREFIX)
app.include_router(multi_face.router, prefix=API_PREFIX)
app.include_router(demographics.router, prefix=API_PREFIX)
app.include_router(landmarks.router, prefix=API_PREFIX)
app.include_router(comparison.router, prefix=API_PREFIX)
app.include_router(similarity_matrix.router, prefix=API_PREFIX)
app.include_router(embeddings_io.router, prefix=API_PREFIX)
app.include_router(webhooks.router, prefix=API_PREFIX)

# Proctoring routes
app.include_router(proctor.router, prefix=API_PREFIX)

# WebSocket routes (proctoring real-time streaming)
app.include_router(proctor_ws.router, prefix=API_PREFIX)

# WebSocket routes (live camera analysis)
app.include_router(live_analysis.router, prefix=API_PREFIX)

# Admin routes
app.include_router(admin.router, prefix=API_PREFIX)

# ============================================================================
# Frontend Configuration & Security
# ============================================================================

# Get the directory containing the main.py file (single source of truth)
BASE_DIR = Path(__file__).resolve().parent.parent  # biometric-processor/
STATIC_DIR = BASE_DIR / "demo-ui" / "out"

# Allowed content types for static files (security whitelist)
ALLOWED_STATIC_TYPES = {
    'text/html',
    'text/css',
    'text/javascript',
    'application/javascript',
    'application/json',
    'image/png',
    'image/jpeg',
    'image/svg+xml',
    'image/webp',
    'image/x-icon',
    'font/woff',
    'font/woff2',
    'font/ttf',
    'font/otf',
}


def is_safe_path(base_dir: Path, user_path: str) -> bool:
    """Validate that user-provided path is within base directory.

    Prevents path traversal attacks (e.g., ../../etc/passwd).

    Args:
        base_dir: The base directory (static files root)
        user_path: User-provided path to validate

    Returns:
        True if path is safe, False otherwise

    Security:
        Uses Path.resolve() to normalize paths and check containment.
        Catches exceptions from invalid paths.
    """
    try:
        # Resolve to absolute paths
        abs_base = base_dir.resolve()
        abs_user = (base_dir / user_path).resolve()

        # Check if user path is within base directory
        # Python 3.9+: is_relative_to()
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
        # Invalid path, symlink loop, or filesystem error
        return False


def create_safe_file_response(file_path: Path) -> FileResponse:
    """Create FileResponse with Content-Type validation.

    Args:
        file_path: Path to file to serve

    Returns:
        FileResponse with validated Content-Type

    Raises:
        HTTPException: If content type is not allowed

    Security:
        Only serves files with whitelisted MIME types.
        Prevents serving executable files or other dangerous content.
    """
    content_type, _ = guess_type(str(file_path))

    # Default to octet-stream if type cannot be determined
    if content_type is None:
        logger.warning(f"Could not determine content type for: {file_path}")
        content_type = 'application/octet-stream'

    # Validate against whitelist
    if content_type not in ALLOWED_STATIC_TYPES:
        logger.warning(
            f"Blocked unsafe content type: {content_type} for file: {file_path.name}"
        )
        raise HTTPException(
            status_code=403,
            detail="Forbidden file type"
        )

    return FileResponse(file_path, media_type=content_type)


# ============================================================================
# Root Endpoint
# ============================================================================


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint - serves frontend if available, otherwise API info."""
    index_html = STATIC_DIR / "index.html"

    # Serve frontend if available
    if index_html.is_file():
        try:
            return create_safe_file_response(index_html)
        except HTTPException:
            # If for some reason index.html is blocked, fall through to API info
            pass
        except Exception as e:
            logger.error(f"Error serving index.html: {e}")

    # Otherwise return API service information
    return JSONResponse(
        content={
            "service": settings.APP_NAME,
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "status": "running",
            "docs_url": "/docs" if settings.is_development() else None,
        }
    )


# ============================================================================
# Static Files (Next.js Frontend)
# ============================================================================

# Only serve static files if the directory exists
if STATIC_DIR.exists():
    # Mount static assets (CSS, JS, images) with caching
    app.mount(
        "/_next",
        StaticFiles(directory=str(STATIC_DIR / "_next")),
        name="next-static"
    )

    # Serve other static files (icons, images, etc.)
    @app.get("/icon.svg", include_in_schema=False)
    async def serve_icon():
        """Serve icon.svg with security validation."""
        try:
            # Validate path safety
            if not is_safe_path(STATIC_DIR, "icon.svg"):
                raise HTTPException(status_code=403, detail="Forbidden")

            icon_path = STATIC_DIR / "icon.svg"
            if icon_path.is_file():
                return create_safe_file_response(icon_path)

            return JSONResponse(status_code=404, content={"detail": "Icon not found"})

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error serving icon.svg: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    # Catch-all handler for SPA routing - MUST be last
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        """Serve Next.js static frontend with security validation.

        This handles SPA routing by:
        1. Validating path safety (prevent path traversal)
        2. Checking if a static file exists at the path
        3. Checking if path.html exists (Next.js static export pattern)
        4. Falling back to index.html for client-side routing

        Priority:
        - API routes (/api/v1/*) are handled first (already registered)
        - Static files (_next/*) are mounted above
        - Everything else goes through this handler

        Security:
        - Path traversal protection (../../etc/passwd blocked)
        - Content-Type validation (only whitelisted MIME types)
        - Error handling for file system operations
        - Logging for security audit trail
        """
        start_time = time.time()

        try:
            # Don't intercept API routes (they're registered with higher priority)
            if full_path.startswith("api/"):
                # This should never be reached due to route priority
                logger.warning(f"API path reached frontend handler: {full_path}")
                return JSONResponse(
                    status_code=404,
                    content={"detail": "API endpoint not found"}
                )

            # Security: Validate path is safe (prevent path traversal)
            if not is_safe_path(STATIC_DIR, full_path):
                logger.warning(f"Path traversal attempt blocked: {full_path}")
                raise HTTPException(status_code=403, detail="Forbidden")

            # Try exact file match
            file_path = STATIC_DIR / full_path
            if file_path.is_file():
                elapsed_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Served static file: {full_path} ({elapsed_ms:.2f}ms)",
                    extra={"path": full_path, "elapsed_ms": elapsed_ms}
                )
                return create_safe_file_response(file_path)

            # Try with .html extension (Next.js static export pattern)
            html_path = STATIC_DIR / f"{full_path}.html"
            if is_safe_path(STATIC_DIR, f"{full_path}.html") and html_path.is_file():
                elapsed_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Served HTML file: {full_path}.html ({elapsed_ms:.2f}ms)",
                    extra={"path": f"{full_path}.html", "elapsed_ms": elapsed_ms}
                )
                return create_safe_file_response(html_path)

            # Try directory index
            if file_path.is_dir():
                index_path = file_path / "index.html"
                index_relative = f"{full_path}/index.html"
                if is_safe_path(STATIC_DIR, index_relative) and index_path.is_file():
                    elapsed_ms = (time.time() - start_time) * 1000
                    logger.info(
                        f"Served directory index: {index_relative} ({elapsed_ms:.2f}ms)",
                        extra={"path": index_relative, "elapsed_ms": elapsed_ms}
                    )
                    return create_safe_file_response(index_path)

            # Fallback to index.html for SPA client-side routing
            index_html = STATIC_DIR / "index.html"
            if index_html.is_file():
                elapsed_ms = (time.time() - start_time) * 1000
                logger.debug(
                    f"SPA fallback to index.html for: {full_path} ({elapsed_ms:.2f}ms)",
                    extra={"path": full_path, "fallback": True, "elapsed_ms": elapsed_ms}
                )
                return create_safe_file_response(index_html)

            # If nothing found, return 404
            logger.warning(f"Static file not found: {full_path}")
            return JSONResponse(
                status_code=404,
                content={"detail": "Page not found"}
            )

        except HTTPException:
            # Re-raise HTTP exceptions (403, 404, etc.)
            raise

        except PermissionError as e:
            logger.error(f"Permission denied accessing {full_path}: {e}")
            raise HTTPException(status_code=403, detail="Access forbidden")

        except OSError as e:
            logger.error(f"File system error for {full_path}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

        except Exception as e:
            logger.exception(f"Unexpected error serving {full_path}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    logger.info(f"Frontend static files mounted from: {STATIC_DIR}")
else:
    logger.warning(f"Frontend static directory not found: {STATIC_DIR}")
    logger.warning("Build the frontend with 'npm run build' in demo-ui/ directory")


# ============================================================================
# Application Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.port,  # Uses PORT env var if available (PaaS compatibility)
        reload=settings.is_development(),
        log_level=settings.LOG_LEVEL.lower(),
    )
