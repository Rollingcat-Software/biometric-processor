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
from fastapi.responses import JSONResponse

from app.api.middleware.error_handler import setup_exception_handlers
from app.api.routes import batch, enrollment, health, liveness, search, verification, card_type_router
from app.api.routes import quality, multi_face, demographics, landmarks, comparison, similarity_matrix, embeddings_io, webhooks
from app.core.config import settings
from app.core.container import initialize_dependencies

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Face Detection: {settings.FACE_DETECTION_BACKEND}")
    logger.info(f"Face Recognition Model: {settings.FACE_RECOGNITION_MODEL}")

    # Initialize dependencies (pre-load ML models)
    logger.info("Initializing dependencies...")
    initialize_dependencies()
    logger.info("Dependencies initialized")

    yield

    # Shutdown
    logger.info("Shutting down application...")


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
# CORS Configuration (SECURITY FIX - No Wildcard!)
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
# ============================================================================
# Root Endpoint
# ============================================================================


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint with service information."""
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
# Application Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.is_development(),
        log_level=settings.LOG_LEVEL.lower(),
    )
