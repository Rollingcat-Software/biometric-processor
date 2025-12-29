# Phase 2: Production Readiness Features

## Overview

This document describes the design for production-ready features including Redis-backed rate limiting, API key authentication, metrics/monitoring, and structured logging.

## Features

### 1. Redis Rate Limiting

**Purpose**: Replace in-memory rate limiting with Redis for distributed deployments.

#### Domain Layer

**Interface** (`app/domain/interfaces/rate_limit_storage.py`):
```python
# Already exists - IRateLimitStorage Protocol
# No changes needed - Redis implementation will implement this interface
```

#### Infrastructure Layer

**Implementation** (`app/infrastructure/rate_limit/redis_storage.py`):
```python
class RedisRateLimitStorage(IRateLimitStorage):
    """Redis-backed rate limit storage with sliding window."""

    def __init__(
        self,
        redis_url: str,
        window_seconds: int = 60,
        default_limit: int = 60,
    ):
        self._redis = redis.from_url(redis_url)
        self._window = window_seconds
        self._default_limit = default_limit

    def increment(self, key: str) -> int:
        """Increment counter using Redis INCR with expiry."""
        pipe = self._redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, self._window)
        result = pipe.execute()
        return result[0]

    def get_info(self, key: str) -> RateLimitInfo:
        """Get rate limit info from Redis."""
        count = self._redis.get(key) or 0
        ttl = self._redis.ttl(key)
        return RateLimitInfo(
            count=int(count),
            limit=self._default_limit,
            remaining=max(0, self._default_limit - int(count)),
            reset_at=datetime.utcnow() + timedelta(seconds=max(0, ttl)),
        )

    def is_rate_limited(self, key: str) -> bool:
        """Check if key exceeds rate limit."""
        count = self._redis.get(key) or 0
        return int(count) >= self._default_limit

    def reset(self, key: str) -> None:
        """Delete key from Redis."""
        self._redis.delete(key)
```

**Factory Update** (`app/infrastructure/rate_limit/storage_factory.py`):
```python
@staticmethod
def create(storage_type: str, **kwargs) -> IRateLimitStorage:
    if storage_type == "memory":
        return InMemoryRateLimitStorage(**kwargs)
    elif storage_type == "redis":
        return RedisRateLimitStorage(
            redis_url=kwargs.get("redis_url", "redis://localhost:6379/0"),
            window_seconds=kwargs.get("window_seconds", 60),
            default_limit=kwargs.get("default_limit", 60),
        )
    else:
        raise ValueError(f"Unknown storage type: {storage_type}")
```

#### Configuration

**Config Updates** (`app/core/config.py`):
```python
# Redis Configuration
REDIS_URL: Optional[str] = Field(default="redis://localhost:6379/0")
REDIS_ENABLED: bool = Field(default=False)

# Rate Limiting
RATE_LIMIT_STORAGE: Literal["memory", "redis"] = Field(default="memory")
RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, ge=1, le=3600)
```

---

### 2. Rate Limit Middleware

**Purpose**: Apply rate limiting to all API endpoints automatically.

#### API Layer

**Middleware** (`app/api/middleware/rate_limit.py`):
```python
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using sliding window."""

    def __init__(self, app, storage: IRateLimitStorage, limit: int = 60):
        super().__init__(app)
        self._storage = storage
        self._limit = limit

    async def dispatch(self, request: Request, call_next):
        # Extract client identifier
        client_id = self._get_client_id(request)

        # Check rate limit
        if self._storage.is_rate_limited(client_id):
            info = self._storage.get_info(client_id)
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(info.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": info.reset_at.isoformat(),
                    "Retry-After": str(int((info.reset_at - datetime.utcnow()).total_seconds())),
                },
            )

        # Increment counter
        self._storage.increment(client_id)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        info = self._storage.get_info(client_id)
        response.headers["X-RateLimit-Limit"] = str(info.limit)
        response.headers["X-RateLimit-Remaining"] = str(info.remaining)
        response.headers["X-RateLimit-Reset"] = info.reset_at.isoformat()

        return response

    def _get_client_id(self, request: Request) -> str:
        """Extract client identifier from request."""
        # Priority: API key > X-Forwarded-For > client IP
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"api:{api_key}"

        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"

        return f"ip:{request.client.host}"
```

---

### 3. API Key Authentication

**Purpose**: Secure API access with API key authentication.

#### Domain Layer

**Entity** (`app/domain/entities/api_key.py`):
```python
@dataclass
class APIKey:
    """API key entity."""
    key_id: str
    key_hash: str  # SHA-256 hash of the actual key
    name: str
    tenant_id: str
    scopes: List[str]  # ["read", "write", "admin"]
    rate_limit: int  # Custom rate limit for this key
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
```

**Interface** (`app/domain/interfaces/api_key_repository.py`):
```python
from typing import Protocol, Optional

class IAPIKeyRepository(Protocol):
    """Repository interface for API keys."""

    async def find_by_key_hash(self, key_hash: str) -> Optional[APIKey]:
        """Find API key by hash."""
        ...

    async def save(self, api_key: APIKey) -> None:
        """Save API key."""
        ...

    async def update_last_used(self, key_id: str) -> None:
        """Update last used timestamp."""
        ...
```

#### Infrastructure Layer

**In-Memory Implementation** (`app/infrastructure/persistence/repositories/memory_api_key_repository.py`):
```python
class InMemoryAPIKeyRepository(IAPIKeyRepository):
    """In-memory API key repository for development."""

    def __init__(self):
        self._keys: Dict[str, APIKey] = {}

    async def find_by_key_hash(self, key_hash: str) -> Optional[APIKey]:
        return self._keys.get(key_hash)

    async def save(self, api_key: APIKey) -> None:
        self._keys[api_key.key_hash] = api_key

    async def update_last_used(self, key_id: str) -> None:
        for key in self._keys.values():
            if key.key_id == key_id:
                key.last_used_at = datetime.utcnow()
                break
```

#### API Layer

**Dependency** (`app/api/dependencies/auth.py`):
```python
import hashlib
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(
    api_key: Optional[str] = Security(api_key_header),
    repository: IAPIKeyRepository = Depends(get_api_key_repository),
) -> Optional[APIKey]:
    """Verify API key and return key info."""
    if not api_key:
        if settings.API_KEY_REQUIRED:
            raise HTTPException(status_code=401, detail="API key required")
        return None

    # Hash the key for lookup
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    # Find in repository
    key_info = await repository.find_by_key_hash(key_hash)

    if not key_info:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not key_info.is_active:
        raise HTTPException(status_code=401, detail="API key disabled")

    if key_info.expires_at and key_info.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="API key expired")

    # Update last used
    await repository.update_last_used(key_info.key_id)

    return key_info

def require_scope(scope: str):
    """Dependency to require specific scope."""
    async def check_scope(
        api_key: Optional[APIKey] = Depends(verify_api_key),
    ):
        if api_key and scope not in api_key.scopes:
            raise HTTPException(status_code=403, detail=f"Scope '{scope}' required")
        return api_key
    return check_scope
```

#### Configuration

```python
# API Key Authentication
API_KEY_REQUIRED: bool = Field(default=False)
API_KEY_HEADER: str = Field(default="X-API-Key")
```

---

### 4. Prometheus Metrics

**Purpose**: Expose application metrics for monitoring.

#### Infrastructure Layer

**Metrics Module** (`app/infrastructure/monitoring/metrics.py`):
```python
from prometheus_client import Counter, Histogram, Gauge, Info
import time

# Application info
APP_INFO = Info("biometric_processor", "Application information")

# Request metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Business metrics
ENROLLMENT_COUNT = Counter(
    "face_enrollments_total",
    "Total face enrollments",
    ["tenant_id", "status"],
)

VERIFICATION_COUNT = Counter(
    "face_verifications_total",
    "Total face verifications",
    ["tenant_id", "result"],
)

LIVENESS_CHECK_COUNT = Counter(
    "liveness_checks_total",
    "Total liveness checks",
    ["mode", "result"],
)

# ML metrics
FACE_DETECTION_LATENCY = Histogram(
    "face_detection_seconds",
    "Face detection latency",
    ["backend"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0],
)

EMBEDDING_EXTRACTION_LATENCY = Histogram(
    "embedding_extraction_seconds",
    "Embedding extraction latency",
    ["model"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
)

# System metrics
ACTIVE_REQUESTS = Gauge(
    "active_requests",
    "Number of active requests",
)

EMBEDDINGS_COUNT = Gauge(
    "embeddings_stored_total",
    "Total embeddings stored",
    ["tenant_id"],
)
```

**Metrics Middleware** (`app/api/middleware/metrics.py`):
```python
from starlette.middleware.base import BaseHTTPMiddleware
import time

class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect request metrics."""

    async def dispatch(self, request: Request, call_next):
        ACTIVE_REQUESTS.inc()

        start_time = time.time()

        try:
            response = await call_next(request)

            # Record metrics
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code,
            ).inc()

            REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=request.url.path,
            ).observe(time.time() - start_time)

            return response
        finally:
            ACTIVE_REQUESTS.dec()
```

#### API Layer

**Metrics Endpoint** (`app/api/routes/metrics.py`):
```python
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

router = APIRouter(prefix="/metrics", tags=["Monitoring"])

@router.get("", response_class=PlainTextResponse)
async def get_metrics():
    """Expose Prometheus metrics."""
    return PlainTextResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
```

---

### 5. Structured Logging

**Purpose**: JSON-formatted logs for log aggregation systems.

#### Infrastructure Layer

**Logging Setup** (`app/infrastructure/logging/structured.py`):
```python
import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict

class StructuredFormatter(logging.Formatter):
    """JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "tenant_id"):
            log_data["tenant_id"] = record.tenant_id
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms

        return json.dumps(log_data)

def setup_structured_logging(level: str = "INFO"):
    """Configure structured logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Add structured handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(handler)
```

**Request Context** (`app/api/middleware/request_context.py`):
```python
import uuid
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

class RequestContextMiddleware(BaseHTTPMiddleware):
    """Add request context for logging."""

    async def dispatch(self, request: Request, call_next):
        # Generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_var.set(request_id)

        # Process request
        response = await call_next(request)

        # Add request ID to response
        response.headers["X-Request-ID"] = request_id

        return response
```

---

## Configuration Summary

**New Environment Variables**:

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | redis://localhost:6379/0 | Redis connection URL |
| `REDIS_ENABLED` | false | Enable Redis integration |
| `RATE_LIMIT_STORAGE` | memory | Rate limit backend (memory/redis) |
| `RATE_LIMIT_WINDOW_SECONDS` | 60 | Sliding window duration |
| `API_KEY_REQUIRED` | false | Require API key for all requests |
| `LOG_FORMAT` | json | Log format (json/text) |
| `METRICS_ENABLED` | true | Enable Prometheus metrics |

---

## File Structure

```
app/
├── api/
│   ├── dependencies/
│   │   └── auth.py                 # NEW: API key auth dependency
│   ├── middleware/
│   │   ├── rate_limit.py           # NEW: Rate limit middleware
│   │   ├── metrics.py              # NEW: Metrics middleware
│   │   └── request_context.py      # NEW: Request context middleware
│   └── routes/
│       └── metrics.py              # NEW: Prometheus endpoint
├── domain/
│   ├── entities/
│   │   └── api_key.py              # NEW: API key entity
│   └── interfaces/
│       └── api_key_repository.py   # NEW: API key repository interface
├── infrastructure/
│   ├── logging/
│   │   └── structured.py           # NEW: Structured logging
│   ├── monitoring/
│   │   └── metrics.py              # NEW: Prometheus metrics
│   ├── persistence/
│   │   └── repositories/
│   │       └── memory_api_key_repository.py  # NEW
│   └── rate_limit/
│       └── redis_storage.py        # NEW: Redis rate limiter
└── core/
    └── config.py                   # UPDATE: New settings
```

---

## Dependencies

**New Requirements** (`requirements.txt` additions):
```
redis>=5.0.0
prometheus-client>=0.19.0
```

---

## SE Checklist Compliance

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| Clean Architecture | ✅ | Domain interfaces, infrastructure implementations |
| Dependency Inversion | ✅ | IRateLimitStorage, IAPIKeyRepository |
| Open/Closed Principle | ✅ | Factory patterns for storage backends |
| Single Responsibility | ✅ | Separate middleware for each concern |
| Interface Segregation | ✅ | Focused interfaces (storage, repository) |
| Factory Pattern | ✅ | RateLimitStorageFactory extended |
| Configuration | ✅ | Environment-based settings |
| Error Handling | ✅ | HTTP exceptions with proper codes |
| Logging | ✅ | Structured JSON logging |
| Monitoring | ✅ | Prometheus metrics |
| Security | ✅ | API key auth, rate limiting |
| Testability | ✅ | In-memory implementations for testing |

---

## Implementation Order

1. **Redis Rate Limiting** - Infrastructure + factory update
2. **Rate Limit Middleware** - Apply to all routes
3. **API Key Authentication** - Entity + repository + dependency
4. **Prometheus Metrics** - Metrics module + middleware + endpoint
5. **Structured Logging** - Formatter + context middleware
6. **Configuration** - Update config.py
7. **Main.py Integration** - Wire up middlewares
8. **Tests** - Unit + integration tests
9. **Documentation** - Update README
