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
from contextlib import asynccontextmanager

from fastapi import FastAPI
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
# Root Endpoint
# ============================================================================


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint - serves frontend if available, otherwise API info."""
    # Check if frontend static files exist
    static_dir = Path(__file__).resolve().parent.parent / "demo-ui" / "out"
    index_html = static_dir / "index.html"

    # Serve frontend if available
    if index_html.is_file():
        return FileResponse(index_html)

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

# Get the directory containing the main.py file
BASE_DIR = Path(__file__).resolve().parent.parent  # biometric-processor/
STATIC_DIR = BASE_DIR / "demo-ui" / "out"

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
        """Serve icon.svg."""
        icon_path = STATIC_DIR / "icon.svg"
        if icon_path.is_file():
            return FileResponse(icon_path)
        return JSONResponse(status_code=404, content={"detail": "Icon not found"})

    # Catch-all handler for SPA routing - MUST be last
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        """Serve Next.js static frontend.

        This handles SPA routing by:
        1. Checking if a static file exists at the path
        2. Checking if path.html exists (Next.js static export pattern)
        3. Falling back to index.html for client-side routing

        Priority:
        - API routes (/api/v1/*) are handled first (already registered)
        - Static files (_next/*) are mounted above
        - Everything else goes through this handler
        """
        # Don't intercept API routes (they're registered with higher priority)
        if full_path.startswith("api/"):
            # This should never be reached due to route priority
            return JSONResponse(
                status_code=404,
                content={"detail": "API endpoint not found"}
            )

        # Try exact file match
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)

        # Try with .html extension (Next.js static export pattern)
        html_path = STATIC_DIR / f"{full_path}.html"
        if html_path.is_file():
            return FileResponse(html_path)

        # Try directory index
        if file_path.is_dir():
            index_path = file_path / "index.html"
            if index_path.is_file():
                return FileResponse(index_path)

        # Fallback to index.html for SPA client-side routing
        index_html = STATIC_DIR / "index.html"
        if index_html.is_file():
            return FileResponse(index_html)

        # If nothing found, return 404
        return JSONResponse(
            status_code=404,
            content={"detail": "Page not found"}
        )

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
