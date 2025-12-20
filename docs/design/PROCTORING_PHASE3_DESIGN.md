# Proctoring Service Phase 3 Design Document

## Overview

This document outlines the design for Phase 3 enhancements to the proctoring service, covering WebSocket streaming, PostgreSQL integration, observability, API documentation, E2E testing, and security hardening.

## Table of Contents

1. [WebSocket Streaming](#1-websocket-streaming)
2. [PostgreSQL Integration](#2-postgresql-integration)
3. [Observability](#3-observability)
4. [API Documentation](#4-api-documentation)
5. [E2E Tests](#5-e2e-tests)
6. [Security Hardening](#6-security-hardening)
7. [SE Checklist Compliance](#7-se-checklist-compliance)

---

## 1. WebSocket Streaming

### 1.1 Purpose

Enable real-time bidirectional communication for frame submission and instant feedback, reducing latency compared to HTTP polling.

### 1.2 Architecture

```
┌─────────────┐     WebSocket      ┌─────────────────────┐
│   Client    │◄──────────────────►│   WebSocket Router  │
│  (Browser)  │   Binary frames    │                     │
└─────────────┘                    └──────────┬──────────┘
                                              │
                                   ┌──────────▼──────────┐
                                   │  Connection Manager │
                                   │  - Session tracking │
                                   │  - Rate limiting    │
                                   │  - Authentication   │
                                   └──────────┬──────────┘
                                              │
                                   ┌──────────▼──────────┐
                                   │  Frame Processor    │
                                   │  - Decode frames    │
                                   │  - ML analysis      │
                                   │  - Incident creation│
                                   └─────────────────────┘
```

### 1.3 Message Protocol

```python
# Client -> Server Messages
class ClientMessage:
    type: Literal["frame", "audio", "ping", "config"]
    session_id: UUID
    payload: bytes | dict
    timestamp: int  # Unix ms

# Server -> Client Messages
class ServerMessage:
    type: Literal["result", "incident", "warning", "pong", "error"]
    session_id: UUID
    payload: dict
    timestamp: int
```

### 1.4 Frame Message Format (Binary)

```
┌────────────┬────────────┬────────────┬─────────────────┐
│  Header    │ Session ID │  Frame #   │   Image Data    │
│  (4 bytes) │ (16 bytes) │  (4 bytes) │   (variable)    │
└────────────┴────────────┴────────────┴─────────────────┘
```

### 1.5 Components

```python
# app/api/websocket/connection_manager.py
class ConnectionManager:
    """Manage WebSocket connections per session."""

    async def connect(self, websocket: WebSocket, session_id: UUID, tenant_id: str) -> bool
    async def disconnect(self, session_id: UUID) -> None
    async def send_result(self, session_id: UUID, result: FrameResult) -> None
    async def send_incident(self, session_id: UUID, incident: dict) -> None
    async def broadcast_to_monitors(self, session_id: UUID, message: dict) -> None
    def get_connection_count(self) -> int
    def get_session_connections(self, session_id: UUID) -> List[WebSocket]

# app/api/websocket/frame_handler.py
class WebSocketFrameHandler:
    """Handle incoming WebSocket frames."""

    async def handle_binary_frame(self, data: bytes, session_id: UUID) -> FrameResult
    async def handle_json_message(self, message: dict, session_id: UUID) -> dict

# app/api/websocket/auth.py
class WebSocketAuthenticator:
    """Authenticate WebSocket connections."""

    async def authenticate(self, websocket: WebSocket) -> Tuple[str, str]  # tenant_id, user_id
    async def validate_session_access(self, session_id: UUID, tenant_id: str) -> bool
```

### 1.6 WebSocket Endpoint

```python
# app/api/routes/proctor_ws.py
@router.websocket("/proctoring/sessions/{session_id}/stream")
async def websocket_stream(
    websocket: WebSocket,
    session_id: UUID,
    token: str = Query(...),  # JWT or API key
):
    """
    WebSocket endpoint for real-time frame streaming.

    Connection flow:
    1. Client connects with session_id and auth token
    2. Server validates token and session access
    3. Client sends binary frames
    4. Server responds with analysis results
    5. Server pushes incidents in real-time
    """
```

### 1.7 Configuration

```python
# New settings in config.py
PROCTOR_WS_ENABLED: bool = True
PROCTOR_WS_MAX_CONNECTIONS_PER_SESSION: int = 2
PROCTOR_WS_HEARTBEAT_INTERVAL_SEC: int = 30
PROCTOR_WS_MESSAGE_QUEUE_SIZE: int = 100
PROCTOR_WS_MAX_FRAME_SIZE_BYTES: int = 5_000_000  # 5MB
PROCTOR_WS_AUTH_TIMEOUT_SEC: int = 10
```

---

## 2. PostgreSQL Integration

### 2.1 Purpose

Production-ready persistent storage with connection pooling, migrations, and health checks.

### 2.2 Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────────┐
│  Repository     │────►│  Connection     │────►│  PostgreSQL  │
│  Interface      │     │  Pool (asyncpg) │     │  Database    │
└─────────────────┘     └─────────────────┘     └──────────────┘
                               │
                        ┌──────▼──────┐
                        │  Health     │
                        │  Checker    │
                        └─────────────┘
```

### 2.3 Database Schema

```sql
-- migrations/versions/001_create_proctor_tables.sql

-- Proctor Sessions Table
CREATE TABLE IF NOT EXISTS proctor_sessions (
    id UUID PRIMARY KEY,
    exam_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'created',
    risk_score FLOAT DEFAULT 0.0,
    config JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    baseline_embedding JSONB,
    verification_count INTEGER DEFAULT 0,
    verification_failures INTEGER DEFAULT 0,
    incident_count INTEGER DEFAULT 0,
    total_gaze_away_sec FLOAT DEFAULT 0.0,
    termination_reason VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,
    paused_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT unique_exam_user_tenant UNIQUE (exam_id, user_id, tenant_id)
);

-- Indexes for common queries
CREATE INDEX idx_sessions_tenant_status ON proctor_sessions(tenant_id, status);
CREATE INDEX idx_sessions_exam ON proctor_sessions(exam_id);
CREATE INDEX idx_sessions_user ON proctor_sessions(user_id);
CREATE INDEX idx_sessions_created ON proctor_sessions(created_at);

-- Proctor Incidents Table
CREATE TABLE IF NOT EXISTS proctor_incidents (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES proctor_sessions(id) ON DELETE CASCADE,
    incident_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    confidence FLOAT NOT NULL,
    details JSONB DEFAULT '{}',
    reviewed BOOLEAN DEFAULT FALSE,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewed_by VARCHAR(255),
    review_action VARCHAR(50),
    review_notes TEXT,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_incidents_session ON proctor_incidents(session_id);
CREATE INDEX idx_incidents_severity ON proctor_incidents(severity);
CREATE INDEX idx_incidents_reviewed ON proctor_incidents(reviewed);

-- Incident Evidence Table
CREATE TABLE IF NOT EXISTS incident_evidence (
    id UUID PRIMARY KEY,
    incident_id UUID NOT NULL REFERENCES proctor_incidents(id) ON DELETE CASCADE,
    evidence_type VARCHAR(50) NOT NULL,
    storage_url TEXT NOT NULL,
    thumbnail_url TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_evidence_incident ON incident_evidence(incident_id);
```

### 2.4 Connection Pool Manager

```python
# app/infrastructure/persistence/pool_manager.py
class DatabasePoolManager:
    """Manage PostgreSQL connection pool lifecycle."""

    def __init__(self, settings: Settings):
        self._pool: Optional[asyncpg.Pool] = None
        self._settings = settings

    async def initialize(self) -> None:
        """Create connection pool on startup."""
        self._pool = await asyncpg.create_pool(
            dsn=self._settings.DATABASE_URL,
            min_size=self._settings.DB_POOL_MIN_SIZE,
            max_size=self._settings.DB_POOL_MAX_SIZE,
            max_inactive_connection_lifetime=300,
            command_timeout=60,
        )

    async def close(self) -> None:
        """Close pool on shutdown."""
        if self._pool:
            await self._pool.close()

    async def health_check(self) -> bool:
        """Check pool health."""
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False

    @property
    def pool(self) -> asyncpg.Pool:
        return self._pool
```

### 2.5 Repository Factory Enhancement

```python
# app/infrastructure/persistence/repository_factory.py
class ProctorRepositoryFactory:
    """Create proctoring repositories based on configuration."""

    @staticmethod
    def create_session_repository(
        storage_type: str,
        pool: Optional[asyncpg.Pool] = None,
    ) -> IProctorSessionRepository:
        if storage_type == "postgres" and pool:
            return PostgresSessionRepository(pool)
        return MemoryProctorSessionRepository()

    @staticmethod
    def create_incident_repository(
        storage_type: str,
        pool: Optional[asyncpg.Pool] = None,
    ) -> IProctorIncidentRepository:
        if storage_type == "postgres" and pool:
            return PostgresIncidentRepository(pool)
        return MemoryProctorIncidentRepository()
```

### 2.6 Configuration

```python
# Existing + new settings
DATABASE_URL: str = "postgresql://user:pass@localhost:5432/biometric"
DB_POOL_MIN_SIZE: int = 5
DB_POOL_MAX_SIZE: int = 20
DB_POOL_MAX_QUERIES: int = 50000
DB_POOL_MAX_INACTIVE_LIFETIME: int = 300
DB_COMMAND_TIMEOUT: int = 60
```

---

## 3. Observability

### 3.1 Purpose

Production-grade monitoring with Prometheus metrics, structured logging, and distributed tracing.

### 3.2 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Application                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  Metrics    │  │  Logging    │  │       Tracing           │  │
│  │  Collector  │  │  Handler    │  │       (OpenTelemetry)   │  │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘  │
└─────────┼────────────────┼─────────────────────┼────────────────┘
          │                │                     │
          ▼                ▼                     ▼
    ┌──────────┐    ┌──────────┐          ┌──────────┐
    │Prometheus│    │  stdout  │          │  Jaeger  │
    │          │    │  (JSON)  │          │  /Zipkin │
    └──────────┘    └──────────┘          └──────────┘
```

### 3.3 Proctoring-Specific Metrics

```python
# app/core/metrics/proctoring.py
class ProctorMetrics:
    """Proctoring-specific Prometheus metrics."""

    # Session metrics
    sessions_total: Counter          # Total sessions created
    sessions_active: Gauge           # Currently active sessions
    session_duration_seconds: Histogram

    # Frame processing metrics
    frames_processed_total: Counter
    frame_processing_duration_ms: Histogram
    frame_processing_errors: Counter

    # ML analysis metrics
    gaze_analysis_duration_ms: Histogram
    object_detection_duration_ms: Histogram
    deepfake_detection_duration_ms: Histogram
    face_verification_duration_ms: Histogram

    # Incident metrics
    incidents_total: Counter         # By type and severity
    incidents_reviewed_total: Counter

    # Risk score distribution
    risk_score_histogram: Histogram

    # WebSocket metrics
    ws_connections_active: Gauge
    ws_messages_received: Counter
    ws_messages_sent: Counter
    ws_errors: Counter

    # Rate limiting metrics
    rate_limit_violations: Counter
    rate_limit_throttled_frames: Counter
```

### 3.4 Structured Logging

```python
# app/core/logging/structured.py
import structlog
from typing import Any

def configure_structured_logging(
    service_name: str,
    version: str,
    environment: str,
    log_level: str = "INFO",
) -> None:
    """Configure structured JSON logging."""

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger with context."""
    return structlog.get_logger(name)

# Context managers for request tracking
@contextmanager
def log_context(**kwargs):
    """Add context to all log messages in scope."""
    token = structlog.contextvars.bind_contextvars(**kwargs)
    try:
        yield
    finally:
        structlog.contextvars.unbind_contextvars(*kwargs.keys())
```

### 3.5 Distributed Tracing

```python
# app/core/tracing/opentelemetry.py
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

def configure_tracing(
    service_name: str,
    otlp_endpoint: str,
    environment: str,
) -> None:
    """Configure OpenTelemetry distributed tracing."""

    provider = TracerProvider(
        resource=Resource.create({
            "service.name": service_name,
            "deployment.environment": environment,
        })
    )

    exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Auto-instrument FastAPI
    FastAPIInstrumentor.instrument()

    # Auto-instrument asyncpg
    AsyncPGInstrumentor().instrument()

def get_tracer(name: str) -> trace.Tracer:
    """Get a tracer for manual instrumentation."""
    return trace.get_tracer(name)

# Decorator for custom spans
def traced(name: str = None):
    """Decorator to trace function execution."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer(func.__module__)
            span_name = name or func.__name__
            with tracer.start_as_current_span(span_name) as span:
                span.set_attribute("function", func.__name__)
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    raise
        return wrapper
    return decorator
```

### 3.6 Configuration

```python
# Observability settings
TRACING_ENABLED: bool = False
TRACING_OTLP_ENDPOINT: str = "http://localhost:4317"
TRACING_SAMPLE_RATE: float = 0.1  # 10% sampling in prod

LOG_FORMAT: Literal["json", "text"] = "json"
LOG_LEVEL: str = "INFO"
LOG_INCLUDE_TRACE_ID: bool = True

METRICS_ENABLED: bool = True
METRICS_PATH: str = "/metrics"
METRICS_INCLUDE_PROCESS: bool = True
```

---

## 4. API Documentation

### 4.1 Purpose

Enhanced OpenAPI documentation with examples, detailed descriptions, and SDK generation support.

### 4.2 OpenAPI Enhancements

```python
# app/api/docs/proctoring.py
"""OpenAPI documentation enhancements for proctoring endpoints."""

PROCTORING_TAG = {
    "name": "proctoring",
    "description": """
## Proctoring Service

AI-powered exam monitoring with:
- **Real-time face verification** - Continuous identity checks
- **Gaze tracking** - Detect looking away from screen
- **Object detection** - Identify phones, notes, extra persons
- **Deepfake detection** - Prevent synthetic media attacks
- **Audio analysis** - Detect unauthorized voices

### Session Lifecycle

```
Created → Started → Active ←→ Paused → Ended
                 ↓
              Flagged → Terminated
```

### Risk Scoring

Risk scores range from 0.0 (no risk) to 1.0 (maximum risk):
- **0.0 - 0.3**: Low risk (green)
- **0.3 - 0.6**: Medium risk (yellow)
- **0.6 - 0.8**: High risk (orange)
- **0.8 - 1.0**: Critical risk (red)

### Rate Limiting

Frame submission is rate-limited per session:
- Maximum 5 frames/second burst
- Maximum 60 frames/minute sustained
- Violations may trigger session throttling
""",
    "externalDocs": {
        "description": "Proctoring API Guide",
        "url": "https://docs.example.com/proctoring",
    },
}

# Response examples
SESSION_CREATED_EXAMPLE = {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "exam_id": "midterm-2024-math",
    "user_id": "student-12345",
    "status": "created",
    "config": {
        "verification_interval_sec": 60,
        "gaze_tracking_enabled": True,
        "object_detection_enabled": True,
        "deepfake_detection_enabled": True,
        "audio_analysis_enabled": False,
    },
}

FRAME_RESULT_EXAMPLE = {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "frame_number": 42,
    "risk_score": 0.15,
    "face_detected": True,
    "face_matched": True,
    "incidents_created": 0,
    "processing_time_ms": 87,
    "analysis": {
        "gaze": {"on_screen": True, "confidence": 0.95},
        "objects": [],
        "deepfake": {"is_fake": False, "confidence": 0.02},
    },
    "rate_limit": {
        "frames_remaining": 58,
        "reset_in_seconds": 45,
    },
}

INCIDENT_EXAMPLE = {
    "incident_id": "661e8400-e29b-41d4-a716-446655440001",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "incident_type": "gaze_away",
    "severity": "low",
    "confidence": 0.85,
    "timestamp": "2024-01-15T10:30:00Z",
    "details": {
        "duration_seconds": 5.2,
        "direction": "left",
    },
    "reviewed": False,
}
```

### 4.3 Schema Enhancements

```python
# app/api/schemas/proctor.py - Enhanced with examples and descriptions

class CreateSessionRequest(BaseModel):
    """Request to create a new proctoring session."""

    exam_id: str = Field(
        ...,
        description="Unique identifier for the exam",
        example="midterm-2024-math",
        min_length=1,
        max_length=255,
    )
    user_id: str = Field(
        ...,
        description="Unique identifier for the exam-taker",
        example="student-12345",
        min_length=1,
        max_length=255,
    )
    config: Optional[SessionConfigSchema] = Field(
        None,
        description="Optional session configuration overrides",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Custom metadata to attach to the session",
        example={"course": "MATH101", "instructor": "Dr. Smith"},
    )

    class Config:
        json_schema_extra = {
            "example": {
                "exam_id": "midterm-2024-math",
                "user_id": "student-12345",
                "config": {"verification_interval_sec": 30},
                "metadata": {"course": "MATH101"},
            }
        }

class SubmitFrameRequest(BaseModel):
    """Request to submit a video frame for analysis."""

    frame_base64: str = Field(
        ...,
        description="Base64-encoded JPEG or PNG image",
        min_length=100,
    )
    frame_number: int = Field(
        ...,
        description="Sequential frame number (client-assigned)",
        ge=0,
        example=42,
    )
    audio_base64: Optional[str] = Field(
        None,
        description="Base64-encoded audio data (float32 PCM)",
    )
    audio_sample_rate: Optional[int] = Field(
        None,
        description="Audio sample rate in Hz",
        example=16000,
        ge=8000,
        le=48000,
    )
```

### 4.4 Error Response Documentation

```python
# app/api/docs/errors.py
ERROR_RESPONSES = {
    400: {
        "description": "Bad Request - Invalid input data",
        "content": {
            "application/json": {
                "examples": {
                    "invalid_image": {
                        "summary": "Invalid image data",
                        "value": {
                            "detail": "Invalid image data: could not decode base64",
                            "error_code": "INVALID_IMAGE",
                        },
                    },
                    "session_not_active": {
                        "summary": "Session not in correct state",
                        "value": {
                            "detail": "Session must be active to submit frames",
                            "error_code": "INVALID_SESSION_STATE",
                        },
                    },
                },
            },
        },
    },
    404: {
        "description": "Not Found - Resource does not exist",
        "content": {
            "application/json": {
                "example": {
                    "detail": "Session 550e8400-e29b-41d4-a716-446655440000 not found",
                    "error_code": "SESSION_NOT_FOUND",
                },
            },
        },
    },
    429: {
        "description": "Too Many Requests - Rate limit exceeded",
        "content": {
            "application/json": {
                "example": {
                    "detail": "Rate limit exceeded: 60 frames/minute",
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "retry_after": 30,
                },
            },
        },
    },
}
```

---

## 5. E2E Tests

### 5.1 Purpose

Comprehensive end-to-end tests validating complete workflows with real ML models.

### 5.2 Test Architecture

```
tests/e2e/
├── conftest.py              # Fixtures and test app setup
├── test_session_workflow.py # Complete session lifecycle
├── test_frame_analysis.py   # Frame processing with ML
├── test_incident_flow.py    # Incident creation and review
├── test_websocket.py        # WebSocket streaming
├── test_concurrent.py       # Concurrent session handling
└── fixtures/
    ├── test_images/         # Sample face images
    ├── test_audio/          # Sample audio clips
    └── expected_results/    # Expected ML outputs
```

### 5.3 Test Fixtures

```python
# tests/e2e/conftest.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.fixture
async def e2e_client():
    """Create async test client with real dependencies."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
def valid_face_image() -> bytes:
    """Load a valid face image for testing."""
    with open("tests/e2e/fixtures/test_images/valid_face.jpg", "rb") as f:
        return base64.b64encode(f.read()).decode()

@pytest.fixture
def no_face_image() -> bytes:
    """Load an image without faces."""
    with open("tests/e2e/fixtures/test_images/no_face.jpg", "rb") as f:
        return base64.b64encode(f.read()).decode()

@pytest.fixture
def multiple_faces_image() -> bytes:
    """Load an image with multiple faces."""
    with open("tests/e2e/fixtures/test_images/multiple_faces.jpg", "rb") as f:
        return base64.b64encode(f.read()).decode()

@pytest.fixture
def phone_in_frame_image() -> bytes:
    """Load an image with a phone visible."""
    with open("tests/e2e/fixtures/test_images/phone_visible.jpg", "rb") as f:
        return base64.b64encode(f.read()).decode()
```

### 5.4 Session Workflow Tests

```python
# tests/e2e/test_session_workflow.py
class TestCompleteSessionWorkflow:
    """Test complete proctoring session from creation to report."""

    async def test_full_exam_session(
        self,
        e2e_client: AsyncClient,
        valid_face_image: str,
    ):
        """
        Test complete exam workflow:
        1. Create session
        2. Start with baseline
        3. Submit frames (simulating exam)
        4. Handle incidents
        5. End session
        6. Generate report
        """
        headers = {"X-Tenant-ID": "test-tenant"}

        # 1. Create session
        create_response = await e2e_client.post(
            "/api/v1/proctoring/sessions",
            headers=headers,
            json={
                "exam_id": "e2e-test-exam",
                "user_id": "e2e-test-user",
            },
        )
        assert create_response.status_code == 201
        session_id = create_response.json()["session_id"]

        # 2. Start session with baseline
        start_response = await e2e_client.post(
            f"/api/v1/proctoring/sessions/{session_id}/start",
            headers=headers,
            json={"baseline_image_base64": valid_face_image},
        )
        assert start_response.status_code == 200
        assert start_response.json()["status"] == "active"

        # 3. Submit multiple frames
        for frame_num in range(5):
            frame_response = await e2e_client.post(
                f"/api/v1/proctoring/sessions/{session_id}/frames",
                headers=headers,
                json={
                    "frame_base64": valid_face_image,
                    "frame_number": frame_num,
                },
            )
            assert frame_response.status_code == 200
            result = frame_response.json()
            assert result["face_detected"] is True
            assert result["face_matched"] is True

        # 4. End session
        end_response = await e2e_client.post(
            f"/api/v1/proctoring/sessions/{session_id}/end",
            headers=headers,
            json={"reason": "completed"},
        )
        assert end_response.status_code == 200
        assert end_response.json()["status"] == "ended"

        # 5. Get report
        report_response = await e2e_client.get(
            f"/api/v1/proctoring/sessions/{session_id}/report",
            headers=headers,
        )
        assert report_response.status_code == 200
        report = report_response.json()
        assert report["verification_count"] >= 1
        assert report["risk_score"] < 0.5  # Should be low risk

    async def test_incident_detection_workflow(
        self,
        e2e_client: AsyncClient,
        valid_face_image: str,
        phone_in_frame_image: str,
    ):
        """Test that incidents are properly detected and can be reviewed."""
        headers = {"X-Tenant-ID": "test-tenant"}

        # Create and start session
        create_resp = await e2e_client.post(
            "/api/v1/proctoring/sessions",
            headers=headers,
            json={"exam_id": "incident-test", "user_id": "test-user"},
        )
        session_id = create_resp.json()["session_id"]

        await e2e_client.post(
            f"/api/v1/proctoring/sessions/{session_id}/start",
            headers=headers,
            json={"baseline_image_base64": valid_face_image},
        )

        # Submit frame with phone (should create incident)
        frame_resp = await e2e_client.post(
            f"/api/v1/proctoring/sessions/{session_id}/frames",
            headers=headers,
            json={
                "frame_base64": phone_in_frame_image,
                "frame_number": 0,
            },
        )

        # Check for incident
        incidents_resp = await e2e_client.get(
            f"/api/v1/proctoring/sessions/{session_id}/incidents",
            headers=headers,
        )
        incidents = incidents_resp.json()["incidents"]

        # Should have detected phone
        phone_incidents = [i for i in incidents if i["incident_type"] == "phone_detected"]
        assert len(phone_incidents) > 0

        # Review incident
        incident_id = phone_incidents[0]["incident_id"]
        review_resp = await e2e_client.post(
            f"/api/v1/proctoring/incidents/{incident_id}/review",
            headers={**headers, "X-Reviewer-ID": "proctor-001"},
            json={
                "action": "dismiss",
                "notes": "False positive - was a calculator",
            },
        )
        assert review_resp.status_code == 200
```

### 5.5 WebSocket Tests

```python
# tests/e2e/test_websocket.py
class TestWebSocketStreaming:
    """Test WebSocket frame streaming."""

    async def test_websocket_frame_submission(
        self,
        e2e_client: AsyncClient,
        valid_face_image: str,
    ):
        """Test real-time frame submission via WebSocket."""
        # First create and start session via REST
        headers = {"X-Tenant-ID": "test-tenant"}

        create_resp = await e2e_client.post(
            "/api/v1/proctoring/sessions",
            headers=headers,
            json={"exam_id": "ws-test", "user_id": "ws-user"},
        )
        session_id = create_resp.json()["session_id"]

        # Start session
        await e2e_client.post(
            f"/api/v1/proctoring/sessions/{session_id}/start",
            headers=headers,
            json={"baseline_image_base64": valid_face_image},
        )

        # Connect WebSocket
        async with e2e_client.websocket_connect(
            f"/api/v1/proctoring/sessions/{session_id}/stream?token=test-token"
        ) as ws:
            # Send frame
            await ws.send_bytes(base64.b64decode(valid_face_image))

            # Receive result
            result = await ws.receive_json()
            assert result["type"] == "result"
            assert result["payload"]["face_detected"] is True

    async def test_websocket_incident_push(
        self,
        e2e_client: AsyncClient,
        valid_face_image: str,
        phone_in_frame_image: str,
    ):
        """Test that incidents are pushed via WebSocket."""
        # Setup session...
        # Connect WebSocket...
        # Send frame with phone...
        # Assert incident message received
        pass
```

### 5.6 Concurrent Session Tests

```python
# tests/e2e/test_concurrent.py
class TestConcurrentSessions:
    """Test concurrent session handling."""

    async def test_multiple_concurrent_sessions(self, e2e_client: AsyncClient):
        """Test handling multiple concurrent proctoring sessions."""
        num_sessions = 10
        headers = {"X-Tenant-ID": "concurrent-test"}

        # Create sessions concurrently
        async def create_session(i: int) -> str:
            resp = await e2e_client.post(
                "/api/v1/proctoring/sessions",
                headers=headers,
                json={"exam_id": f"concurrent-exam-{i}", "user_id": f"user-{i}"},
            )
            return resp.json()["session_id"]

        session_ids = await asyncio.gather(*[
            create_session(i) for i in range(num_sessions)
        ])

        assert len(session_ids) == num_sessions
        assert len(set(session_ids)) == num_sessions  # All unique

    async def test_session_isolation(self, e2e_client: AsyncClient):
        """Test that sessions are properly isolated between tenants."""
        # Create session for tenant A
        resp_a = await e2e_client.post(
            "/api/v1/proctoring/sessions",
            headers={"X-Tenant-ID": "tenant-a"},
            json={"exam_id": "isolation-test", "user_id": "user-1"},
        )
        session_id = resp_a.json()["session_id"]

        # Try to access from tenant B (should fail)
        resp_b = await e2e_client.get(
            f"/api/v1/proctoring/sessions/{session_id}",
            headers={"X-Tenant-ID": "tenant-b"},
        )
        assert resp_b.status_code == 404
```

---

## 6. Security Hardening

### 6.1 Purpose

Enhance security with input validation, sanitization, and protection against common attacks.

### 6.2 Input Validation

```python
# app/api/validators/proctor.py
import re
from typing import Optional
from pydantic import validator, Field

# Constants
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_AUDIO_SIZE_BYTES = 5 * 1024 * 1024   # 5MB
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}

class ImageValidator:
    """Validate image data for security and correctness."""

    @staticmethod
    def validate_base64_image(data: str) -> bytes:
        """Validate and decode base64 image data."""
        try:
            # Check length before decoding
            if len(data) > MAX_IMAGE_SIZE_BYTES * 1.4:  # Base64 overhead
                raise ValueError("Image data too large")

            decoded = base64.b64decode(data)

            # Check decoded size
            if len(decoded) > MAX_IMAGE_SIZE_BYTES:
                raise ValueError(f"Image exceeds maximum size of {MAX_IMAGE_SIZE_BYTES} bytes")

            # Validate image magic bytes
            if not ImageValidator._is_valid_image(decoded):
                raise ValueError("Invalid image format")

            return decoded

        except Exception as e:
            raise ValueError(f"Invalid image data: {e}")

    @staticmethod
    def _is_valid_image(data: bytes) -> bool:
        """Check image magic bytes."""
        # JPEG
        if data[:2] == b'\xff\xd8':
            return True
        # PNG
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            return True
        # WebP
        if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            return True
        return False

class InputSanitizer:
    """Sanitize user inputs to prevent injection attacks."""

    # Patterns for dangerous inputs
    SCRIPT_PATTERN = re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL)
    SQL_INJECTION_PATTERN = re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|OR|AND)\b)", re.IGNORECASE)

    @staticmethod
    def sanitize_string(value: str, max_length: int = 255) -> str:
        """Sanitize a string input."""
        if not value:
            return value

        # Truncate
        value = value[:max_length]

        # Remove null bytes
        value = value.replace('\x00', '')

        # Strip HTML tags for non-rich-text fields
        value = re.sub(r'<[^>]+>', '', value)

        return value.strip()

    @staticmethod
    def sanitize_metadata(metadata: dict, max_depth: int = 3) -> dict:
        """Sanitize metadata dictionary."""
        if not metadata:
            return {}

        def sanitize_value(val, depth=0):
            if depth > max_depth:
                return None
            if isinstance(val, str):
                return InputSanitizer.sanitize_string(val)
            if isinstance(val, dict):
                return {k: sanitize_value(v, depth + 1) for k, v in val.items()}
            if isinstance(val, list):
                return [sanitize_value(v, depth + 1) for v in val[:100]]  # Limit list size
            if isinstance(val, (int, float, bool, type(None))):
                return val
            return str(val)[:255]

        return sanitize_value(metadata)
```

### 6.3 Rate Limiting Enhancements

```python
# app/infrastructure/resilience/advanced_rate_limiter.py
from dataclasses import dataclass
from typing import Dict, Optional
import time

@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_second: int = 5
    requests_per_minute: int = 60
    burst_size: int = 10
    penalty_multiplier: float = 2.0
    max_violations_before_block: int = 5
    block_duration_seconds: int = 300

class AdvancedRateLimiter:
    """Advanced rate limiter with adaptive throttling."""

    def __init__(self, config: RateLimitConfig):
        self._config = config
        self._sessions: Dict[str, SessionRateState] = {}

    async def check_rate_limit(self, session_id: str) -> RateLimitResult:
        """Check if request is allowed under rate limits."""
        state = self._get_or_create_state(session_id)

        # Check if blocked
        if state.is_blocked():
            return RateLimitResult(
                allowed=False,
                reason="blocked",
                retry_after=state.block_expires_in(),
            )

        # Check burst limit
        if not state.check_burst():
            state.record_violation()
            return RateLimitResult(
                allowed=False,
                reason="burst_exceeded",
                retry_after=1,
            )

        # Check sustained limit
        if not state.check_sustained():
            state.record_violation()
            return RateLimitResult(
                allowed=False,
                reason="rate_exceeded",
                retry_after=state.seconds_until_reset(),
            )

        # Record request
        state.record_request()

        return RateLimitResult(
            allowed=True,
            remaining=state.remaining_requests(),
            reset_in=state.seconds_until_reset(),
        )

    async def get_session_stats(self, session_id: str) -> dict:
        """Get rate limit statistics for a session."""
        state = self._sessions.get(session_id)
        if not state:
            return {
                "frames_last_minute": 0,
                "remaining_this_minute": self._config.requests_per_minute,
                "violation_count": 0,
                "is_throttled": False,
            }

        return {
            "frames_last_minute": state.requests_last_minute(),
            "remaining_this_minute": state.remaining_requests(),
            "violation_count": state.violation_count,
            "is_throttled": state.is_blocked(),
            "throttle_expires_in": state.block_expires_in() if state.is_blocked() else None,
        }
```

### 6.4 Authentication & Authorization

```python
# app/api/middleware/auth.py
from fastapi import Request, HTTPException, status
from fastapi.security import APIKeyHeader
import hashlib
import hmac

class ProctorAuthMiddleware:
    """Authentication middleware for proctoring endpoints."""

    def __init__(self, api_key_repository, settings):
        self._repository = api_key_repository
        self._settings = settings

    async def authenticate(self, request: Request) -> AuthContext:
        """Authenticate request and return context."""
        # Extract API key
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API key",
            )

        # Validate key (constant-time comparison)
        key_record = await self._repository.get_by_key_hash(
            self._hash_key(api_key)
        )

        if not key_record or not key_record.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )

        # Check permissions
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id and tenant_id not in key_record.allowed_tenants:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized for this tenant",
            )

        return AuthContext(
            api_key_id=key_record.id,
            tenant_id=tenant_id or key_record.default_tenant,
            permissions=key_record.permissions,
        )

    def _hash_key(self, key: str) -> str:
        """Hash API key for storage comparison."""
        return hashlib.sha256(key.encode()).hexdigest()
```

### 6.5 Security Headers

```python
# app/api/middleware/security_headers.py
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data:; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'"
        )

        # HSTS (in production)
        if not request.url.hostname == "localhost":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response
```

### 6.6 Configuration

```python
# Security settings
SECURITY_API_KEY_MIN_LENGTH: int = 32
SECURITY_ENABLE_RATE_LIMITING: bool = True
SECURITY_MAX_REQUEST_SIZE_MB: int = 50
SECURITY_ALLOWED_HOSTS: List[str] = ["*"]
SECURITY_CSRF_ENABLED: bool = False  # Not needed for API-only
SECURITY_AUDIT_LOG_ENABLED: bool = True
```

---

## 7. SE Checklist Compliance

### 7.1 SOLID Principles

| Principle | Implementation |
|-----------|----------------|
| **S**ingle Responsibility | Each class has one purpose (ConnectionManager, FrameHandler, Authenticator) |
| **O**pen/Closed | Extensible via interfaces (IProctorSessionRepository, metrics collectors) |
| **L**iskov Substitution | All repository implementations are interchangeable |
| **I**nterface Segregation | Small, focused interfaces (IProctorSessionRepository vs IProctorIncidentRepository) |
| **D**ependency Inversion | All dependencies injected via FastAPI DI |

### 7.2 Design Patterns Used

| Pattern | Usage |
|---------|-------|
| Repository | PostgresSessionRepository, MemoryProctorSessionRepository |
| Factory | ProctorRepositoryFactory, MLComponentFactory |
| Strategy | Different rate limiting strategies, authentication methods |
| Observer | WebSocket ConnectionManager (broadcast to monitors) |
| Decorator | @traced for adding tracing to functions |
| Singleton | Connection pool, metrics collector |

### 7.3 Best Practices

| Practice | Implementation |
|----------|----------------|
| **DRY** | Shared validators, common error handling, reusable components |
| **KISS** | Simple message protocol, clear API contracts |
| **YAGNI** | Only implemented features that are needed |
| **Separation of Concerns** | Clear layers (API, Application, Domain, Infrastructure) |
| **Defensive Programming** | Input validation, error handling, null checks |
| **Fail Fast** | Early validation, clear error messages |

### 7.4 Security Checklist

- [x] Input validation on all endpoints
- [x] Rate limiting with adaptive throttling
- [x] Authentication via API keys
- [x] Authorization per tenant
- [x] Security headers middleware
- [x] SQL injection prevention (parameterized queries)
- [x] XSS prevention (no user HTML rendering)
- [x] CSRF protection (API uses tokens, not cookies)
- [x] Audit logging for security events

### 7.5 Testing Strategy

| Test Type | Coverage Target |
|-----------|-----------------|
| Unit Tests | >80% code coverage |
| Integration Tests | All API endpoints |
| E2E Tests | Critical user workflows |
| Performance Tests | Response time < 100ms p95 |
| Security Tests | OWASP Top 10 |

---

## Implementation Plan

### Phase 3.1: WebSocket Streaming (Priority: High)
1. Create connection manager
2. Implement WebSocket endpoint
3. Add binary frame protocol
4. Add authentication
5. Write tests

### Phase 3.2: PostgreSQL Integration (Priority: High)
1. Create database migrations
2. Implement pool manager
3. Update repository factory
4. Add health checks
5. Write tests

### Phase 3.3: Observability (Priority: Medium)
1. Add proctoring metrics
2. Implement structured logging
3. Configure tracing
4. Update middleware
5. Write tests

### Phase 3.4: API Documentation (Priority: Medium)
1. Enhance schemas with examples
2. Add OpenAPI tags
3. Document error responses
4. Generate SDK stubs

### Phase 3.5: E2E Tests (Priority: Medium)
1. Set up test fixtures
2. Implement workflow tests
3. Add WebSocket tests
4. Add concurrent tests

### Phase 3.6: Security Hardening (Priority: High)
1. Implement input validators
2. Enhance rate limiter
3. Add security headers
4. Add audit logging
5. Security testing

---

## Acceptance Criteria

1. **WebSocket**: Real-time frame streaming with <50ms latency
2. **PostgreSQL**: Persistent storage with connection pooling
3. **Observability**: Full metrics, logs, and traces available
4. **Documentation**: Complete OpenAPI spec with examples
5. **E2E Tests**: All critical workflows tested
6. **Security**: Pass security review, no critical vulnerabilities
