# Proctoring Service Phase 2 - Production Readiness Design

**Version**: 1.0
**Date**: 2024-12-12
**Status**: Draft
**Author**: Architecture Team

---

## 1. Overview

### 1.1 Purpose

This document designs the production readiness features for the Proctoring Service:

1. **Configuration Management** - Environment-based settings for proctoring
2. **PostgreSQL Repositories** - Production-grade data persistence
3. **Integration Tests** - Full API flow testing
4. **Performance Benchmarks** - ML pipeline latency validation

### 1.2 Goals

| Goal | Description | Success Metric |
|------|-------------|----------------|
| **Configurability** | All thresholds externalized | 100% settings in environment |
| **Persistence** | Production database support | PostgreSQL repositories working |
| **Quality Assurance** | Comprehensive test coverage | >80% code coverage on new code |
| **Performance** | Validated latency targets | <500ms p95 frame analysis |

### 1.3 Non-Goals

- WebSocket real-time API (future phase)
- Kubernetes deployment manifests (DevOps responsibility)
- Load testing infrastructure (separate initiative)

---

## 2. Configuration Management Design

### 2.1 Environment Variables

Following the existing pattern in `app/core/config.py`:

```python
# Proctoring Service Configuration
# Section: Session Management
PROCTOR_ENABLED: bool = True
PROCTOR_MAX_SESSIONS_PER_USER: int = 1
PROCTOR_SESSION_TIMEOUT_MINUTES: int = 180

# Section: Verification Thresholds
PROCTOR_VERIFICATION_INTERVAL_SEC: int = 60
PROCTOR_VERIFICATION_THRESHOLD: float = 0.6
PROCTOR_LIVENESS_THRESHOLD: float = 0.7

# Section: Gaze Tracking
PROCTOR_GAZE_ENABLED: bool = True
PROCTOR_GAZE_THRESHOLD: float = 0.3
PROCTOR_GAZE_AWAY_THRESHOLD_SEC: float = 5.0

# Section: Object Detection
PROCTOR_OBJECT_DETECTION_ENABLED: bool = True
PROCTOR_OBJECT_MODEL_SIZE: str = "nano"  # nano, small, medium, large
PROCTOR_OBJECT_CONFIDENCE_THRESHOLD: float = 0.5
PROCTOR_MAX_PERSONS_ALLOWED: int = 1

# Section: Deepfake Detection
PROCTOR_DEEPFAKE_ENABLED: bool = True
PROCTOR_DEEPFAKE_THRESHOLD: float = 0.6
PROCTOR_DEEPFAKE_TEMPORAL_WINDOW: int = 10

# Section: Audio Analysis
PROCTOR_AUDIO_ENABLED: bool = False
PROCTOR_AUDIO_SAMPLE_RATE: int = 16000
PROCTOR_AUDIO_VAD_THRESHOLD: float = 0.5

# Section: Risk Management
PROCTOR_RISK_THRESHOLD_WARNING: float = 0.5
PROCTOR_RISK_THRESHOLD_CRITICAL: float = 0.8
PROCTOR_AUTO_TERMINATE_ON_CRITICAL: bool = False

# Section: Rate Limiting
PROCTOR_RATE_LIMIT_ENABLED: bool = True
PROCTOR_MAX_FRAMES_PER_SECOND: int = 5
PROCTOR_MAX_FRAMES_PER_MINUTE: int = 120
PROCTOR_RATE_LIMIT_BURST_ALLOWANCE: int = 10

# Section: Circuit Breaker
PROCTOR_CIRCUIT_BREAKER_ENABLED: bool = True
PROCTOR_CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 3
PROCTOR_CIRCUIT_BREAKER_SUCCESS_THRESHOLD: int = 2
PROCTOR_CIRCUIT_BREAKER_TIMEOUT_SEC: float = 30.0

# Section: Database
PROCTOR_DB_POOL_SIZE: int = 10
PROCTOR_DB_MAX_OVERFLOW: int = 20
```

### 2.2 Configuration Class Design

```python
@dataclass
class ProctorSettings:
    """Proctoring service configuration."""

    # Feature flags
    enabled: bool = True
    gaze_enabled: bool = True
    object_detection_enabled: bool = True
    deepfake_enabled: bool = True
    audio_enabled: bool = False

    # Session settings
    max_sessions_per_user: int = 1
    session_timeout_minutes: int = 180

    # Verification
    verification_interval_sec: int = 60
    verification_threshold: float = 0.6
    liveness_threshold: float = 0.7

    # Gaze tracking
    gaze_threshold: float = 0.3
    gaze_away_threshold_sec: float = 5.0

    # Object detection
    object_model_size: str = "nano"
    object_confidence_threshold: float = 0.5
    max_persons_allowed: int = 1

    # Deepfake detection
    deepfake_threshold: float = 0.6
    deepfake_temporal_window: int = 10

    # Audio
    audio_sample_rate: int = 16000
    audio_vad_threshold: float = 0.5

    # Risk management
    risk_threshold_warning: float = 0.5
    risk_threshold_critical: float = 0.8
    auto_terminate_on_critical: bool = False

    # Rate limiting
    rate_limit_enabled: bool = True
    max_frames_per_second: int = 5
    max_frames_per_minute: int = 120
    rate_limit_burst_allowance: int = 10

    # Circuit breaker
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 3
    circuit_breaker_success_threshold: int = 2
    circuit_breaker_timeout_sec: float = 30.0

    def to_session_config(self) -> dict:
        """Convert to SessionConfig dict for session creation."""
        return {
            "verification_interval_sec": self.verification_interval_sec,
            "verification_threshold": self.verification_threshold,
            "liveness_threshold": self.liveness_threshold,
            "gaze_away_threshold_sec": self.gaze_away_threshold_sec,
            "risk_threshold_warning": self.risk_threshold_warning,
            "risk_threshold_critical": self.risk_threshold_critical,
            "enable_gaze_tracking": self.gaze_enabled,
            "enable_object_detection": self.object_detection_enabled,
            "enable_audio_monitoring": self.audio_enabled,
        }
```

### 2.3 Configuration Validation

```python
def __post_init__(self):
    """Validate configuration values."""
    # Threshold validations
    if not 0.0 <= self.verification_threshold <= 1.0:
        raise ValueError("verification_threshold must be 0-1")
    if not 0.0 <= self.liveness_threshold <= 1.0:
        raise ValueError("liveness_threshold must be 0-1")
    if not 0.0 <= self.risk_threshold_warning <= 1.0:
        raise ValueError("risk_threshold_warning must be 0-1")
    if self.risk_threshold_warning >= self.risk_threshold_critical:
        raise ValueError("warning threshold must be less than critical")

    # Model validation
    if self.object_model_size not in ["nano", "small", "medium", "large"]:
        raise ValueError("Invalid object_model_size")

    # Rate limit validation
    if self.max_frames_per_second > self.max_frames_per_minute / 60:
        raise ValueError("frames_per_second exceeds frames_per_minute rate")
```

---

## 3. PostgreSQL Repository Design

### 3.1 Connection Management

Following existing patterns in the codebase:

```python
from asyncpg import Pool, create_pool
from contextlib import asynccontextmanager

class PostgresConnectionManager:
    """Manages PostgreSQL connection pool for proctoring."""

    def __init__(
        self,
        dsn: str,
        min_size: int = 5,
        max_size: int = 20,
    ):
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._pool: Optional[Pool] = None

    async def initialize(self) -> None:
        """Initialize connection pool."""
        self._pool = await create_pool(
            self._dsn,
            min_size=self._min_size,
            max_size=self._max_size,
        )

    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()

    @asynccontextmanager
    async def connection(self):
        """Get connection from pool."""
        async with self._pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self):
        """Get connection with transaction."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                yield conn
```

### 3.2 Session Repository Implementation

```python
class PostgresProctorSessionRepository(IProctorSessionRepository):
    """PostgreSQL implementation of proctoring session repository."""

    def __init__(self, connection_manager: PostgresConnectionManager):
        self._conn_manager = connection_manager

    async def save(self, session: ProctorSession) -> None:
        """Save or update a proctoring session."""
        query = """
            INSERT INTO proctor_sessions (
                id, exam_id, user_id, tenant_id, status,
                config, baseline_embedding, risk_score,
                verification_count, verification_failures,
                created_at, started_at, ended_at,
                termination_reason, metadata
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15
            )
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                risk_score = EXCLUDED.risk_score,
                verification_count = EXCLUDED.verification_count,
                verification_failures = EXCLUDED.verification_failures,
                ended_at = EXCLUDED.ended_at,
                termination_reason = EXCLUDED.termination_reason
        """
        async with self._conn_manager.connection() as conn:
            await conn.execute(
                query,
                session.id,
                session.exam_id,
                session.user_id,
                session.tenant_id,
                session.status.value,
                json.dumps(session.config.to_dict()) if session.config else None,
                session.baseline_embedding.tolist() if session.baseline_embedding else None,
                session.risk_score,
                session.verification_count,
                session.verification_failures,
                session.created_at,
                session.started_at,
                session.ended_at,
                session.termination_reason.value if session.termination_reason else None,
                json.dumps(session.metadata) if session.metadata else None,
            )

    async def get_by_id(
        self,
        session_id: UUID,
        tenant_id: str,
    ) -> Optional[ProctorSession]:
        """Get session by ID with tenant isolation."""
        query = """
            SELECT * FROM proctor_sessions
            WHERE id = $1 AND tenant_id = $2
        """
        async with self._conn_manager.connection() as conn:
            row = await conn.fetchrow(query, session_id, tenant_id)
            if row:
                return self._row_to_session(row)
            return None

    async def get_active_sessions(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorSession]:
        """Get all active sessions for tenant."""
        query = """
            SELECT * FROM proctor_sessions
            WHERE tenant_id = $1 AND status IN ('active', 'initializing', 'flagged')
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """
        async with self._conn_manager.connection() as conn:
            rows = await conn.fetch(query, tenant_id, limit, offset)
            return [self._row_to_session(row) for row in rows]

    # ... additional methods following same pattern

    def _row_to_session(self, row: Record) -> ProctorSession:
        """Convert database row to ProctorSession entity."""
        config = None
        if row['config']:
            config = SessionConfig.from_dict(json.loads(row['config']))

        baseline = None
        if row['baseline_embedding']:
            baseline = np.array(row['baseline_embedding'])

        return ProctorSession(
            id=row['id'],
            exam_id=row['exam_id'],
            user_id=row['user_id'],
            tenant_id=row['tenant_id'],
            status=SessionStatus(row['status']),
            config=config,
            baseline_embedding=baseline,
            risk_score=row['risk_score'],
            verification_count=row['verification_count'],
            verification_failures=row['verification_failures'],
            created_at=row['created_at'],
            started_at=row['started_at'],
            ended_at=row['ended_at'],
            termination_reason=TerminationReason(row['termination_reason']) if row['termination_reason'] else None,
            metadata=json.loads(row['metadata']) if row['metadata'] else None,
        )
```

### 3.3 Incident Repository Implementation

```python
class PostgresProctorIncidentRepository(IProctorIncidentRepository):
    """PostgreSQL implementation of proctoring incident repository."""

    def __init__(self, connection_manager: PostgresConnectionManager):
        self._conn_manager = connection_manager

    async def save(self, incident: ProctorIncident) -> None:
        """Save or update an incident."""
        query = """
            INSERT INTO proctor_incidents (
                id, session_id, incident_type, severity,
                confidence, timestamp, details,
                reviewed, reviewed_by, reviewed_at, review_notes, review_action
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
            )
            ON CONFLICT (id) DO UPDATE SET
                reviewed = EXCLUDED.reviewed,
                reviewed_by = EXCLUDED.reviewed_by,
                reviewed_at = EXCLUDED.reviewed_at,
                review_notes = EXCLUDED.review_notes,
                review_action = EXCLUDED.review_action
        """
        async with self._conn_manager.connection() as conn:
            await conn.execute(
                query,
                incident.id,
                incident.session_id,
                incident.incident_type.value,
                incident.severity.value,
                incident.confidence,
                incident.timestamp,
                json.dumps(incident.details) if incident.details else None,
                incident.reviewed,
                incident.reviewed_by,
                incident.reviewed_at,
                incident.review_notes,
                incident.review_action.value if incident.review_action else None,
            )

    async def get_by_session(
        self,
        session_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ProctorIncident]:
        """Get all incidents for a session."""
        query = """
            SELECT * FROM proctor_incidents
            WHERE session_id = $1
            ORDER BY timestamp DESC
            LIMIT $2 OFFSET $3
        """
        async with self._conn_manager.connection() as conn:
            rows = await conn.fetch(query, session_id, limit, offset)
            return [self._row_to_incident(row) for row in rows]

    async def count_by_severity(
        self,
        session_id: UUID,
        severity: IncidentSeverity,
    ) -> int:
        """Count incidents by severity."""
        query = """
            SELECT COUNT(*) FROM proctor_incidents
            WHERE session_id = $1 AND severity = $2
        """
        async with self._conn_manager.connection() as conn:
            return await conn.fetchval(query, session_id, severity.value)

    # ... additional methods

    def _row_to_incident(self, row: Record) -> ProctorIncident:
        """Convert database row to ProctorIncident entity."""
        return ProctorIncident(
            id=row['id'],
            session_id=row['session_id'],
            incident_type=IncidentType(row['incident_type']),
            severity=IncidentSeverity(row['severity']),
            confidence=row['confidence'],
            timestamp=row['timestamp'],
            details=json.loads(row['details']) if row['details'] else None,
            reviewed=row['reviewed'],
            reviewed_by=row['reviewed_by'],
            reviewed_at=row['reviewed_at'],
            review_notes=row['review_notes'],
            review_action=ReviewAction(row['review_action']) if row['review_action'] else None,
        )
```

### 3.4 Repository Factory

```python
class ProctorRepositoryFactory:
    """Factory for creating proctoring repositories."""

    @staticmethod
    def create_session_repository(
        storage_type: str = "memory",
        connection_manager: Optional[PostgresConnectionManager] = None,
    ) -> IProctorSessionRepository:
        """Create session repository based on storage type."""
        if storage_type == "postgres":
            if not connection_manager:
                raise ValueError("connection_manager required for postgres")
            return PostgresProctorSessionRepository(connection_manager)
        else:
            return InMemoryProctorSessionRepository()

    @staticmethod
    def create_incident_repository(
        storage_type: str = "memory",
        connection_manager: Optional[PostgresConnectionManager] = None,
    ) -> IProctorIncidentRepository:
        """Create incident repository based on storage type."""
        if storage_type == "postgres":
            if not connection_manager:
                raise ValueError("connection_manager required for postgres")
            return PostgresProctorIncidentRepository(connection_manager)
        else:
            return InMemoryProctorIncidentRepository()
```

---

## 4. Integration Tests Design

### 4.1 Test Categories

| Category | Description | Count |
|----------|-------------|-------|
| **Session Lifecycle** | Create, start, pause, resume, end | 8 tests |
| **Frame Analysis** | Submit frames with various conditions | 10 tests |
| **Incident Management** | Create, list, review incidents | 6 tests |
| **Reports** | Session reports and summaries | 4 tests |
| **Error Handling** | Invalid inputs, not found scenarios | 6 tests |
| **Rate Limiting** | Frame submission throttling | 4 tests |
| **Total** | | **38 tests** |

### 4.2 Test Fixtures

```python
@pytest.fixture
async def test_client():
    """Create test client with app."""
    from app.main import app
    from httpx import AsyncClient

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
def tenant_headers():
    """Headers with tenant ID."""
    return {"X-Tenant-ID": "test-tenant"}

@pytest.fixture
def sample_frame_base64():
    """Generate a valid test frame."""
    import cv2
    import base64

    # Create a simple test image
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:] = (100, 100, 100)  # Gray background

    # Encode to base64
    _, buffer = cv2.imencode('.jpg', img)
    return base64.b64encode(buffer).decode('utf-8')

@pytest.fixture
async def created_session(test_client, tenant_headers):
    """Create a session for testing."""
    response = await test_client.post(
        "/api/v1/proctoring/sessions",
        headers=tenant_headers,
        json={
            "exam_id": "exam-001",
            "user_id": "user-001",
        }
    )
    return response.json()
```

### 4.3 Session Lifecycle Tests

```python
class TestSessionLifecycle:
    """Integration tests for session lifecycle."""

    @pytest.mark.asyncio
    async def test_create_session(self, test_client, tenant_headers):
        """Test creating a new proctoring session."""
        response = await test_client.post(
            "/api/v1/proctoring/sessions",
            headers=tenant_headers,
            json={
                "exam_id": "exam-001",
                "user_id": "user-001",
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert data["status"] == "created"
        assert data["exam_id"] == "exam-001"

    @pytest.mark.asyncio
    async def test_start_session(self, test_client, tenant_headers, created_session):
        """Test starting a session."""
        session_id = created_session["session_id"]

        response = await test_client.post(
            f"/api/v1/proctoring/sessions/{session_id}/start",
            headers=tenant_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_pause_resume_session(self, test_client, tenant_headers, created_session):
        """Test pausing and resuming a session."""
        session_id = created_session["session_id"]

        # Start first
        await test_client.post(
            f"/api/v1/proctoring/sessions/{session_id}/start",
            headers=tenant_headers,
        )

        # Pause
        response = await test_client.post(
            f"/api/v1/proctoring/sessions/{session_id}/pause",
            headers=tenant_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "paused"

        # Resume
        response = await test_client.post(
            f"/api/v1/proctoring/sessions/{session_id}/resume",
            headers=tenant_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "active"

    @pytest.mark.asyncio
    async def test_end_session(self, test_client, tenant_headers, created_session):
        """Test ending a session."""
        session_id = created_session["session_id"]

        # Start first
        await test_client.post(
            f"/api/v1/proctoring/sessions/{session_id}/start",
            headers=tenant_headers,
        )

        # End
        response = await test_client.post(
            f"/api/v1/proctoring/sessions/{session_id}/end",
            headers=tenant_headers,
            json={"reason": "completed"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert "duration_seconds" in data
```

### 4.4 Frame Analysis Tests

```python
class TestFrameAnalysis:
    """Integration tests for frame analysis."""

    @pytest.mark.asyncio
    async def test_submit_frame_success(
        self, test_client, tenant_headers, created_session, sample_frame_base64
    ):
        """Test successful frame submission."""
        session_id = created_session["session_id"]

        # Start session
        await test_client.post(
            f"/api/v1/proctoring/sessions/{session_id}/start",
            headers=tenant_headers,
        )

        # Submit frame
        response = await test_client.post(
            f"/api/v1/proctoring/sessions/{session_id}/frames",
            headers=tenant_headers,
            json={
                "frame_base64": sample_frame_base64,
                "frame_number": 1,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "risk_score" in data
        assert "processing_time_ms" in data

    @pytest.mark.asyncio
    async def test_submit_frame_invalid_session(
        self, test_client, tenant_headers, sample_frame_base64
    ):
        """Test frame submission with invalid session."""
        fake_session_id = str(uuid4())

        response = await test_client.post(
            f"/api/v1/proctoring/sessions/{fake_session_id}/frames",
            headers=tenant_headers,
            json={
                "frame_base64": sample_frame_base64,
                "frame_number": 1,
            }
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_submit_frame_rate_limited(
        self, test_client, tenant_headers, created_session, sample_frame_base64
    ):
        """Test frame submission rate limiting."""
        session_id = created_session["session_id"]

        # Start session
        await test_client.post(
            f"/api/v1/proctoring/sessions/{session_id}/start",
            headers=tenant_headers,
        )

        # Submit many frames rapidly
        for i in range(15):
            response = await test_client.post(
                f"/api/v1/proctoring/sessions/{session_id}/frames",
                headers=tenant_headers,
                json={
                    "frame_base64": sample_frame_base64,
                    "frame_number": i,
                }
            )

        # Should see rate limit info in response
        data = response.json()
        assert "rate_limit" in data
```

### 4.5 Incident Tests

```python
class TestIncidentManagement:
    """Integration tests for incident management."""

    @pytest.mark.asyncio
    async def test_create_incident(self, test_client, tenant_headers, created_session):
        """Test creating an incident manually."""
        session_id = created_session["session_id"]

        # Start session
        await test_client.post(
            f"/api/v1/proctoring/sessions/{session_id}/start",
            headers=tenant_headers,
        )

        # Create incident
        response = await test_client.post(
            f"/api/v1/proctoring/sessions/{session_id}/incidents",
            headers=tenant_headers,
            json={
                "incident_type": "FACE_NOT_DETECTED",
                "confidence": 0.95,
                "details": {"reason": "User looked away"},
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert "incident_id" in data
        assert data["incident_type"] == "FACE_NOT_DETECTED"

    @pytest.mark.asyncio
    async def test_list_incidents(self, test_client, tenant_headers, created_session):
        """Test listing incidents for a session."""
        session_id = created_session["session_id"]

        response = await test_client.get(
            f"/api/v1/proctoring/sessions/{session_id}/incidents",
            headers=tenant_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "incidents" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_review_incident(self, test_client, tenant_headers, created_session):
        """Test reviewing an incident."""
        session_id = created_session["session_id"]

        # Start and create incident
        await test_client.post(
            f"/api/v1/proctoring/sessions/{session_id}/start",
            headers=tenant_headers,
        )

        incident_response = await test_client.post(
            f"/api/v1/proctoring/sessions/{session_id}/incidents",
            headers=tenant_headers,
            json={
                "incident_type": "FACE_NOT_DETECTED",
                "confidence": 0.95,
            }
        )
        incident_id = incident_response.json()["incident_id"]

        # Review it
        review_headers = {**tenant_headers, "X-Reviewer-ID": "admin-001"}
        response = await test_client.post(
            f"/api/v1/proctoring/incidents/{incident_id}/review",
            headers=review_headers,
            json={
                "action": "DISMISSED",
                "notes": "False positive - user sneezed",
            }
        )

        assert response.status_code == 200
```

---

## 5. Performance Benchmarks Design

### 5.1 Benchmark Categories

| Benchmark | Target | Method |
|-----------|--------|--------|
| **Frame Analysis** | <500ms p95 | pytest-benchmark |
| **Session Create** | <100ms p95 | pytest-benchmark |
| **Database Query** | <50ms p95 | pytest-benchmark |
| **ML Pipeline** | <400ms p95 | Component timing |

### 5.2 Benchmark Implementation

```python
import pytest
from pytest_benchmark.fixture import BenchmarkFixture

class TestPerformanceBenchmarks:
    """Performance benchmarks for proctoring service."""

    @pytest.mark.benchmark(group="session")
    def test_session_create_performance(self, benchmark):
        """Benchmark session creation."""
        from app.domain.entities.proctor_session import ProctorSession

        def create_session():
            return ProctorSession.create(
                exam_id="exam-001",
                user_id="user-001",
                tenant_id="tenant-001",
            )

        result = benchmark(create_session)
        assert result is not None

    @pytest.mark.benchmark(group="analysis")
    def test_gaze_analysis_performance(self, benchmark, sample_image):
        """Benchmark gaze tracking analysis."""
        from app.infrastructure.ml.proctoring import MediaPipeGazeTracker

        tracker = MediaPipeGazeTracker()
        session_id = uuid4()

        async def analyze():
            return await tracker.analyze(sample_image, session_id)

        result = benchmark.pedantic(
            lambda: asyncio.run(analyze()),
            rounds=50,
            warmup_rounds=5,
        )
        # Target: <100ms per frame for gaze

    @pytest.mark.benchmark(group="analysis")
    def test_object_detection_performance(self, benchmark, sample_image):
        """Benchmark object detection."""
        from app.infrastructure.ml.proctoring import YOLOObjectDetector

        detector = YOLOObjectDetector(model_name="yolov8n.pt")
        session_id = uuid4()

        async def detect():
            return await detector.detect(sample_image, session_id)

        result = benchmark.pedantic(
            lambda: asyncio.run(detect()),
            rounds=50,
            warmup_rounds=5,
        )
        # Target: <200ms per frame for YOLO nano

    @pytest.mark.benchmark(group="analysis")
    def test_deepfake_detection_performance(self, benchmark, sample_image):
        """Benchmark deepfake detection."""
        from app.infrastructure.ml.proctoring import TextureDeepfakeDetector

        detector = TextureDeepfakeDetector()
        session_id = uuid4()

        async def detect():
            return await detector.detect(sample_image, session_id)

        result = benchmark.pedantic(
            lambda: asyncio.run(detect()),
            rounds=50,
            warmup_rounds=5,
        )
        # Target: <100ms per frame for texture analysis

    @pytest.mark.benchmark(group="database")
    def test_session_save_performance(self, benchmark, session, db_connection):
        """Benchmark session database save."""
        from app.infrastructure.persistence.repositories.postgres_session_repository import (
            PostgresProctorSessionRepository
        )

        repo = PostgresProctorSessionRepository(db_connection)

        async def save():
            await repo.save(session)

        result = benchmark.pedantic(
            lambda: asyncio.run(save()),
            rounds=100,
            warmup_rounds=10,
        )
        # Target: <20ms per save
```

### 5.3 Performance Metrics Collection

```python
class PerformanceMetrics:
    """Collect and report performance metrics."""

    def __init__(self):
        self.metrics = {}

    def record(self, name: str, duration_ms: float):
        """Record a timing metric."""
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(duration_ms)

    def get_statistics(self, name: str) -> dict:
        """Get statistics for a metric."""
        values = self.metrics.get(name, [])
        if not values:
            return {}

        import numpy as np

        return {
            "count": len(values),
            "min": np.min(values),
            "max": np.max(values),
            "mean": np.mean(values),
            "p50": np.percentile(values, 50),
            "p95": np.percentile(values, 95),
            "p99": np.percentile(values, 99),
        }

    def report(self) -> str:
        """Generate performance report."""
        lines = ["Performance Report", "=" * 50]

        for name in sorted(self.metrics.keys()):
            stats = self.get_statistics(name)
            lines.append(f"\n{name}:")
            lines.append(f"  Count: {stats['count']}")
            lines.append(f"  Min: {stats['min']:.2f}ms")
            lines.append(f"  Mean: {stats['mean']:.2f}ms")
            lines.append(f"  P95: {stats['p95']:.2f}ms")
            lines.append(f"  P99: {stats['p99']:.2f}ms")
            lines.append(f"  Max: {stats['max']:.2f}ms")

        return "\n".join(lines)
```

---

## 6. Implementation Plan

### 6.1 Phase Breakdown

| Step | Task | Duration |
|------|------|----------|
| 1 | Add configuration to config.py | 30 min |
| 2 | Update dependencies with config | 30 min |
| 3 | Implement PostgreSQL session repository | 1 hour |
| 4 | Implement PostgreSQL incident repository | 45 min |
| 5 | Create repository factory | 30 min |
| 6 | Write integration tests | 1.5 hours |
| 7 | Write performance benchmarks | 45 min |
| 8 | Run tests and fix issues | 30 min |
| 9 | Commit and document | 15 min |

### 6.2 Dependencies

```
# Additional test dependencies
pytest-benchmark>=4.0.0
pytest-asyncio>=0.21.0
httpx>=0.24.0
```

---

## 7. SE Checklist Compliance Matrix

| Category | Requirement | Status | Evidence |
|----------|-------------|--------|----------|
| **SOLID - SRP** | Each class single responsibility | ✅ | Config, Repository, Tests separate |
| **SOLID - OCP** | Open for extension | ✅ | Repository factory pattern |
| **SOLID - LSP** | Substitutable implementations | ✅ | Memory/Postgres repositories |
| **SOLID - ISP** | Focused interfaces | ✅ | IProctorSessionRepository, IProctorIncidentRepository |
| **SOLID - DIP** | Depend on abstractions | ✅ | Dependencies use interfaces |
| **DRY** | No duplicate logic | ✅ | Shared _row_to_entity methods |
| **KISS** | Simple solutions | ✅ | Standard pytest patterns |
| **YAGNI** | No premature features | ✅ | Only essential benchmarks |
| **Design Patterns** | Appropriate patterns | ✅ | Factory, Repository |
| **Error Handling** | Proper exceptions | ✅ | Validation with context |
| **Testing** | Comprehensive tests | ✅ | 38 integration tests planned |
| **Security** | Input validation | ✅ | Config validation |
| **Performance** | Measured targets | ✅ | Benchmarks with p95 targets |
| **Documentation** | Clear documentation | ✅ | This design document |

---

## 8. Acceptance Criteria

### 8.1 Configuration

- [ ] All proctoring settings configurable via environment
- [ ] Validation on all threshold values
- [ ] Default values match design document

### 8.2 Repositories

- [ ] PostgreSQL session repository implements all interface methods
- [ ] PostgreSQL incident repository implements all interface methods
- [ ] Factory creates correct repository based on config

### 8.3 Integration Tests

- [ ] All 38 tests passing
- [ ] >80% code coverage on new code
- [ ] Tests run in CI pipeline

### 8.4 Performance

- [ ] Frame analysis <500ms p95
- [ ] Session operations <100ms p95
- [ ] Database operations <50ms p95

---

**Document Status**: Ready for implementation
**Approval**: Self-certified compliant with SE checklist
