"""FastAPI application entry point.

This module creates and configures the FastAPI application with:
- Clean Architecture layers
- Dependency injection
- Error handling
- Security (CORS, rate limiting)
- Structured logging
- API documentation
"""

import hmac
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from PIL import Image

# Defense-in-depth: cap decompressed pixels to ~50 MP to block decompression bombs.
# request_size_guard caps wire bytes; this caps post-decode RAM.
Image.MAX_IMAGE_PIXELS = 50_000_000
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.middleware.api_key_auth import APIKeyAuthMiddleware
from app.api.middleware.error_handler import setup_exception_handlers
from app.api.middleware.rate_limit import RateLimitMiddleware
from app.api.middleware.security import InputSanitizationMiddleware
from app.api.middleware.security_headers import SecurityHeadersMiddleware
from app.api.routes import batch, enrollment, health, liveness, search, verification, card_type_router
from app.api.routes import quality, multi_face, demographics, landmarks, comparison, similarity_matrix, embeddings_io, webhooks
from app.api.routes import verification_pipeline
from app.api.routes import proctor
from app.api.routes import proctor_ws
from app.api.routes import admin
from app.api.routes import live_analysis
from app.api.routes import fingerprint, voice
from app.api.routes import puzzle
from app.core.config import settings
from app.core.container import initialize_dependencies, shutdown_dependencies
from app.core.gpu import configure_gpu
from app.infrastructure.rate_limit.storage_factory import RateLimitStorageFactory
from app.infrastructure.web.static_file_service import create_static_file_service

# Configure GPU before any ML model loading
configure_gpu()

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

    # P6.9 #4: validate liveness model SHA256 pins at startup so corrupt or
    # tampered assets are rejected BEFORE the service starts serving traffic.
    # Previously the check was lazy (first liveness request) — that meant
    # bad assets on a freshly-deployed container would only surface when a
    # user hit the endpoint.
    try:
        from app.application.services.active_liveness_manager import (
            verify_liveness_model_assets,
        )

        verify_liveness_model_assets()
    except RuntimeError:
        # SHA mismatch — refuse to start the service.
        logger.exception("Liveness model asset verification FAILED at startup")
        raise
    except Exception:
        # Defensive: any other error (e.g. unexpected IO) is logged but
        # doesn't crash boot — the lazy check still gates the first request.
        logger.exception(
            "Liveness model asset verification raised non-fatal error; "
            "lazy startup will still validate on first request."
        )

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
# Middleware Configuration
# ============================================================================
# NOTE: Middleware runs in reverse order (LIFO stack)
# Add middleware in reverse order of execution

# Exception Handlers (processed last)
setup_exception_handlers(app)

# CORS (must be last middleware so it runs first)
cors_config = settings.get_cors_config()
logger.info(f"CORS allowed origins: {cors_config['allow_origins']}")
app.add_middleware(CORSMiddleware, **cors_config)

# Security Headers
app.add_middleware(
    SecurityHeadersMiddleware,
    enable_hsts=settings.ENVIRONMENT == "production",
    frame_options="SAMEORIGIN",  # Allow embedding from same origin
)
logger.info("Security headers middleware enabled")

# Compression (gzip)
app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,  # Only compress responses > 1KB
    compresslevel=6,  # Balance between speed and compression ratio
)
logger.info("GZip compression middleware enabled (min size: 1KB)")

# Rate Limiting
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

# API Key Authentication is applied via @app.middleware("http") below
# (add_middleware ordering issues with FastAPI — using decorator instead)
#
# NOTE: The Request Size Guard is registered AFTER the API-key middleware via
# @app.middleware("http") (see bottom of this section) so it executes FIRST in
# the request path. We must reject 100 MB uploads BEFORE buffering the body and
# BEFORE the auth check — an unauthenticated client should still be 413'd
# without burning CX43 RAM (16 GB shared across all services).
# Audit ref: AUDIT_2026-04-28_EDGE.md row 10 (Edge-P2 #10).

# Input Sanitization (SQL injection, XSS, path traversal detection)
app.add_middleware(
    InputSanitizationMiddleware,
    check_sql=True,
    check_xss=True,
    check_path_traversal=True,
)
logger.info("Input sanitization middleware enabled")

# ============================================================================
# API Key Authentication (http middleware decorator — reliable execution order)
# ============================================================================

if settings.API_KEY_ENABLED and settings.API_KEY_REQUIRE_AUTH:
    _API_KEY_SECRET = settings.API_KEY_SECRET
    _API_KEY_HEADER = settings.API_KEY_HEADER
    _EXCLUDED_PATHS = {"/health", "/api/v1/health", "/metrics"}

    @app.middleware("http")
    async def api_key_auth(request, call_next):
        # Always pass OPTIONS through so CORS preflight can be handled by CORSMiddleware
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.url.path
        if path.startswith("/api/") and path not in _EXCLUDED_PATHS:
            key = request.headers.get(_API_KEY_HEADER)
            if not key or not hmac.compare_digest(key, _API_KEY_SECRET):
                from fastapi.responses import JSONResponse as JR
                return JR(
                    status_code=401,
                    content={"error_code": "UNAUTHORIZED", "message": "Valid API key required."},
                    headers={"WWW-Authenticate": "ApiKey"},
                )
        return await call_next(request)

    logger.info("API key authentication enabled via @app.middleware")

# ============================================================================
# Request Size Guard (registered LAST so it runs FIRST — before API key auth)
# ============================================================================
# Reject oversized uploads via Content-Length BEFORE the body is buffered in
# RAM and BEFORE the API-key check (denying a 100 MB unauthenticated upload
# should not require holding 100 MB in memory first).
#
# In FastAPI/Starlette the middleware stack is built in REVERSE order of
# registration: the LAST-registered middleware becomes the OUTERMOST wrapper
# and therefore runs FIRST. Registering this decorator after the API-key block
# above guarantees that ordering. Verified by integration test
# tests/integration/test_request_size_limit.py.
#
# Edge case: chunked transfer encoding has no Content-Length header. Such
# requests bypass this guard; Starlette buffers the stream into memory.
# Acceptable because the upstream Traefik/NGINX hop terminates chunked uploads
# and we control all clients (identity-core-api uses requests.post with files=
# which always sets Content-Length). For depth, the per-route validate_image_file
# magic-byte check still runs after.
#
# Audit ref: AUDIT_2026-04-28_EDGE.md row 10 (Edge-P2 #10) — 100 MB upload
# reaching validate_image_file before rejection ate CX43 RAM (16 GB shared).

_MAX_UPLOAD_SIZE = settings.MAX_UPLOAD_SIZE


@app.middleware("http")
async def request_size_guard(request, call_next):
    """Reject requests whose Content-Length exceeds MAX_UPLOAD_SIZE with 413."""
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            length = int(content_length)
        except ValueError:
            length = None
        if length is not None and length > _MAX_UPLOAD_SIZE:
            from fastapi.responses import JSONResponse as _JR
            logger.warning(
                f"Request rejected: Content-Length {length} > MAX_UPLOAD_SIZE "
                f"{_MAX_UPLOAD_SIZE} (path={request.url.path})"
            )
            return _JR(
                status_code=413,
                content={
                    "error_code": "PAYLOAD_TOO_LARGE",
                    "message": (
                        f"Request body exceeds maximum size of "
                        f"{_MAX_UPLOAD_SIZE} bytes"
                    ),
                },
            )
    return await call_next(request)


logger.info(
    f"Request size guard enabled (max={_MAX_UPLOAD_SIZE} bytes, "
    f"runs before API key auth)"
)

# ============================================================================
# API Routes
# ============================================================================

# Include routers with /api/v1 prefix
API_PREFIX = "/api/v1"

app.include_router(health.router, prefix=API_PREFIX)
app.include_router(enrollment.router, prefix=API_PREFIX)
app.include_router(verification.router, prefix=API_PREFIX)
app.include_router(liveness.router, prefix=API_PREFIX)
app.include_router(puzzle.router, prefix=API_PREFIX)
app.include_router(search.router, prefix=API_PREFIX)
app.include_router(batch.router, prefix=API_PREFIX)
app.include_router(card_type_router.router, prefix=API_PREFIX)

# Verification Pipeline routes (Phase 8B/8C: Document Processing + Face-to-Document Matching)
app.include_router(verification_pipeline.router, prefix=API_PREFIX)

# New feature routes
app.include_router(quality.router, prefix=API_PREFIX)
app.include_router(multi_face.router, prefix=API_PREFIX)
# Demographics router is gated behind DEMOGRAPHICS_ROUTER_ENABLED (default off).
# See FINDINGS_2026-04-25 B2: web-app has zero callers and DeepFace.analyze
# would lazy-load 4 extra age/gender/race/emotion models (~400 MB) on first hit.
if settings.DEMOGRAPHICS_ROUTER_ENABLED:
    app.include_router(demographics.router, prefix=API_PREFIX)
    logger.info("Demographics router enabled (DEMOGRAPHICS_ROUTER_ENABLED=true)")
else:
    logger.info(
        "Demographics router DISABLED (DEMOGRAPHICS_ROUTER_ENABLED=false). "
        "Set DEMOGRAPHICS_ROUTER_ENABLED=true to enable /api/v1/demographics/*."
    )
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

# Fingerprint routes (501 Not Implemented -- use WebAuthn) and Voice routes (Resemblyzer)
app.include_router(fingerprint.router, prefix=API_PREFIX)
app.include_router(voice.router, prefix=API_PREFIX)

# ============================================================================
# Frontend Static File Service
# ============================================================================

# Get the directory containing the main.py file (single source of truth)
BASE_DIR = Path(__file__).resolve().parent.parent  # biometric-processor/
STATIC_DIR = BASE_DIR / "demo-ui" / "out"

# Create static file service (uses Strategy, DIP, SRP patterns)
static_file_service = create_static_file_service(STATIC_DIR)


# ============================================================================
# Lightweight Health Probe (no dependency checks -- sub-5ms response)
# ============================================================================


@app.get("/ping", include_in_schema=False)
async def ping():
    """Instant health probe for load balancers and uptime monitors.

    Unlike /api/v1/health (which checks DB, Redis, ML models), this returns
    immediately with no dependency checks.  Use this for Docker HEALTHCHECK,
    Traefik health probes, and external uptime monitoring.
    """
    return {"status": "ok"}


# ============================================================================
# Root Endpoint
# ============================================================================


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint - serves frontend if available and enabled, otherwise API info."""
    if settings.DEMO_UI_ENABLED:
        try:
            return await static_file_service.serve_file("index.html")
        except Exception as e:
            logger.debug(f"Frontend not available: {e}")

    return JSONResponse(
        content={
            "service": settings.APP_NAME,
            "version": settings.VERSION,
            "status": "running",
        }
    )


# ============================================================================
# Static Files (Next.js Frontend)
# ============================================================================

# Only serve static files if the directory exists AND demo UI is enabled
if STATIC_DIR.exists() and settings.DEMO_UI_ENABLED:
    # Mount static assets (CSS, JS, images) with caching
    app.mount(
        "/_next",
        StaticFiles(directory=str(STATIC_DIR / "_next")),
        name="next-static"
    )

    # Serve other static files (icons, images, etc.)
    @app.get("/icon.svg", include_in_schema=False)
    async def serve_icon():
        """Serve icon.svg using StaticFileService."""
        return await static_file_service.serve_specific_file("icon.svg")

    @app.get("/robots.txt", include_in_schema=False)
    async def serve_robots():
        """Serve robots.txt for search engine crawlers."""
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            "User-agent: *\nAllow: /\n\n"
            "Sitemap: https://bio.fivucsas.com/sitemap.xml\n"
        )

    # Catch-all handler for SPA routing - MUST be last
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        """Serve Next.js static frontend using StaticFileService.

        Delegates to StaticFileService which handles:
        - Path traversal protection (security)
        - Content-Type validation (security)
        - File resolution strategies (Strategy pattern)
        - Caching headers (performance)
        - Security audit logging
        - Performance monitoring

        Design Patterns Used:
        - Strategy Pattern: File resolution (exact, .html, directory, fallback)
        - Service Pattern: Encapsulated business logic
        - Dependency Inversion: Abstract file provider interface
        - Single Responsibility: Separation of concerns

        Priority:
        - API routes (/api/v1/*) are handled first (already registered)
        - Static assets (_next/*) are mounted above
        - Everything else goes through this handler
        """
        return await static_file_service.serve_file(full_path)

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
