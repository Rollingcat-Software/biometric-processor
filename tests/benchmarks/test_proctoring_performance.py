"""Performance benchmarks for proctoring service.

Run with: pytest tests/benchmarks/ -v --benchmark-only
"""

import sys
import time
from typing import Dict, List
from unittest.mock import Mock
from uuid import uuid4

import numpy as np
import pytest

# Mock heavy ML dependencies for isolated benchmarks
sys.modules['mediapipe'] = Mock()
sys.modules['ultralytics'] = Mock()


# ============================================================================
# Performance Metrics Collector
# ============================================================================


class PerformanceMetrics:
    """Collect and report performance metrics."""

    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}

    def record(self, name: str, duration_ms: float) -> None:
        """Record a timing metric."""
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(duration_ms)

    def get_statistics(self, name: str) -> dict:
        """Get statistics for a metric."""
        values = self.metrics.get(name, [])
        if not values:
            return {}

        return {
            "count": len(values),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "mean": float(np.mean(values)),
            "p50": float(np.percentile(values, 50)),
            "p95": float(np.percentile(values, 95)),
            "p99": float(np.percentile(values, 99)),
        }

    def report(self) -> str:
        """Generate performance report."""
        lines = ["", "=" * 60, "PROCTORING PERFORMANCE REPORT", "=" * 60]

        for name in sorted(self.metrics.keys()):
            stats = self.get_statistics(name)
            if stats:
                lines.append(f"\n{name}:")
                lines.append(f"  Count: {stats['count']}")
                lines.append(f"  Min:   {stats['min']:.2f}ms")
                lines.append(f"  Mean:  {stats['mean']:.2f}ms")
                lines.append(f"  P50:   {stats['p50']:.2f}ms")
                lines.append(f"  P95:   {stats['p95']:.2f}ms")
                lines.append(f"  P99:   {stats['p99']:.2f}ms")
                lines.append(f"  Max:   {stats['max']:.2f}ms")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)

    def assert_target(self, name: str, p95_target_ms: float) -> None:
        """Assert that p95 is below target."""
        stats = self.get_statistics(name)
        if stats:
            p95 = stats["p95"]
            assert p95 < p95_target_ms, (
                f"{name} p95 ({p95:.2f}ms) exceeds target ({p95_target_ms}ms)"
            )


# Global metrics collector
metrics = PerformanceMetrics()


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_image():
    """Generate sample image for benchmarks."""
    import cv2

    # Create realistic-ish test image
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:] = (100, 100, 100)

    # Add some texture
    noise = np.random.randint(0, 30, (480, 640, 3), dtype=np.uint8)
    img = cv2.add(img, noise)

    return img


@pytest.fixture
def session_id():
    """Generate session ID."""
    return uuid4()


# ============================================================================
# Entity Creation Benchmarks
# ============================================================================


class TestEntityCreationPerformance:
    """Benchmark entity creation."""

    def test_session_creation_performance(self):
        """Benchmark session creation (target: <10ms)."""
        from app.domain.entities.proctor_session import ProctorSession

        iterations = 1000

        start = time.perf_counter()
        for i in range(iterations):
            session = ProctorSession.create(
                exam_id=f"exam-{i}",
                user_id=f"user-{i}",
                tenant_id="tenant-001",
            )
        end = time.perf_counter()

        total_ms = (end - start) * 1000
        per_op_ms = total_ms / iterations

        metrics.record("session_create", per_op_ms)

        print(f"\nSession creation: {per_op_ms:.3f}ms per operation")
        assert per_op_ms < 1.0  # Should be < 1ms

    def test_incident_creation_performance(self):
        """Benchmark incident creation (target: <5ms)."""
        from app.domain.entities.proctor_incident import ProctorIncident, IncidentType

        session_id = uuid4()
        iterations = 1000

        start = time.perf_counter()
        for i in range(iterations):
            incident = ProctorIncident.create(
                session_id=session_id,
                incident_type=IncidentType.FACE_NOT_DETECTED,
                confidence=0.95,
                details={"frame_number": i},
            )
        end = time.perf_counter()

        total_ms = (end - start) * 1000
        per_op_ms = total_ms / iterations

        metrics.record("incident_create", per_op_ms)

        print(f"\nIncident creation: {per_op_ms:.3f}ms per operation")
        assert per_op_ms < 1.0  # Should be < 1ms

    def test_session_config_creation_performance(self):
        """Benchmark session config creation."""
        from app.domain.entities.proctor_session import SessionConfig

        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            config = SessionConfig(
                verification_interval_sec=60,
                verification_threshold=0.6,
                liveness_threshold=0.7,
                gaze_away_threshold_sec=5.0,
                risk_threshold_warning=0.5,
                risk_threshold_critical=0.8,
            )
        end = time.perf_counter()

        per_op_ms = (end - start) * 1000 / iterations
        metrics.record("config_create", per_op_ms)

        print(f"\nConfig creation: {per_op_ms:.3f}ms per operation")
        assert per_op_ms < 0.5  # Should be very fast


# ============================================================================
# State Machine Benchmarks
# ============================================================================


class TestStateMachinePerformance:
    """Benchmark state transitions."""

    def test_session_state_transitions(self):
        """Benchmark full session lifecycle."""
        from app.domain.entities.proctor_session import ProctorSession

        iterations = 500

        start = time.perf_counter()
        for _ in range(iterations):
            session = ProctorSession.create(
                exam_id="exam-001",
                user_id="user-001",
                tenant_id="tenant-001",
            )
            session.start()
            session.update_risk_score(0.3)
            session.record_verification(success=True)
            session.record_verification(success=True)
            session.pause()
            session.resume()
            session.complete()
        end = time.perf_counter()

        per_op_ms = (end - start) * 1000 / iterations
        metrics.record("session_lifecycle", per_op_ms)

        print(f"\nSession lifecycle: {per_op_ms:.3f}ms per lifecycle")
        assert per_op_ms < 5.0  # Full lifecycle < 5ms


# ============================================================================
# Repository Benchmarks (In-Memory)
# ============================================================================


class TestRepositoryPerformance:
    """Benchmark repository operations."""

    @pytest.mark.asyncio
    async def test_session_save_performance(self):
        """Benchmark session save (target: <5ms for in-memory)."""
        from app.domain.entities.proctor_session import ProctorSession
        from app.infrastructure.persistence.repositories.memory_proctor_repository import (
            InMemoryProctorSessionRepository,
        )

        repo = InMemoryProctorSessionRepository()
        iterations = 500

        # Create sessions first
        sessions = [
            ProctorSession.create(
                exam_id=f"exam-{i}",
                user_id=f"user-{i}",
                tenant_id="tenant-001",
            )
            for i in range(iterations)
        ]

        start = time.perf_counter()
        for session in sessions:
            await repo.save(session)
        end = time.perf_counter()

        per_op_ms = (end - start) * 1000 / iterations
        metrics.record("session_save_memory", per_op_ms)

        print(f"\nSession save (memory): {per_op_ms:.3f}ms per save")
        assert per_op_ms < 1.0  # In-memory should be very fast

    @pytest.mark.asyncio
    async def test_session_get_by_id_performance(self):
        """Benchmark session retrieval."""
        from app.domain.entities.proctor_session import ProctorSession
        from app.infrastructure.persistence.repositories.memory_proctor_repository import (
            InMemoryProctorSessionRepository,
        )

        repo = InMemoryProctorSessionRepository()

        # Populate repository
        sessions = []
        for i in range(100):
            session = ProctorSession.create(
                exam_id=f"exam-{i}",
                user_id=f"user-{i}",
                tenant_id="tenant-001",
            )
            await repo.save(session)
            sessions.append(session)

        iterations = 500

        start = time.perf_counter()
        for i in range(iterations):
            session = sessions[i % len(sessions)]
            await repo.get_by_id(session.id, "tenant-001")
        end = time.perf_counter()

        per_op_ms = (end - start) * 1000 / iterations
        metrics.record("session_get_memory", per_op_ms)

        print(f"\nSession get (memory): {per_op_ms:.3f}ms per get")
        assert per_op_ms < 0.5  # In-memory lookup should be very fast

    @pytest.mark.asyncio
    async def test_incident_save_performance(self):
        """Benchmark incident save."""
        from app.domain.entities.proctor_incident import ProctorIncident, IncidentType
        from app.infrastructure.persistence.repositories.memory_proctor_repository import (
            InMemoryProctorIncidentRepository,
        )

        repo = InMemoryProctorIncidentRepository()
        session_id = uuid4()
        iterations = 500

        # Create incidents
        incidents = [
            ProctorIncident.create(
                session_id=session_id,
                incident_type=IncidentType.FACE_NOT_DETECTED,
                confidence=0.9,
            )
            for _ in range(iterations)
        ]

        start = time.perf_counter()
        for incident in incidents:
            await repo.save(incident)
        end = time.perf_counter()

        per_op_ms = (end - start) * 1000 / iterations
        metrics.record("incident_save_memory", per_op_ms)

        print(f"\nIncident save (memory): {per_op_ms:.3f}ms per save")
        assert per_op_ms < 1.0


# ============================================================================
# Rate Limiter Benchmarks
# ============================================================================


class TestRateLimiterPerformance:
    """Benchmark rate limiter."""

    @pytest.mark.asyncio
    async def test_rate_limiter_check_performance(self):
        """Benchmark rate limit checks."""
        from app.infrastructure.resilience.session_rate_limiter import (
            InMemorySessionRateLimiter,
        )

        limiter = InMemorySessionRateLimiter(
            max_frames_per_second=5,
            max_frames_per_minute=120,
        )

        session_id = uuid4()
        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            await limiter.check(session_id)
        end = time.perf_counter()

        per_op_ms = (end - start) * 1000 / iterations
        metrics.record("rate_limit_check", per_op_ms)

        print(f"\nRate limit check: {per_op_ms:.3f}ms per check")
        assert per_op_ms < 1.0  # Rate limit check should be fast


# ============================================================================
# Serialization Benchmarks
# ============================================================================


class TestSerializationPerformance:
    """Benchmark serialization."""

    def test_session_to_dict_performance(self):
        """Benchmark session serialization."""
        from app.domain.entities.proctor_session import ProctorSession

        session = ProctorSession.create(
            exam_id="exam-001",
            user_id="user-001",
            tenant_id="tenant-001",
        )
        session.start()
        session.record_verification(success=True)

        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            session.to_dict()
        end = time.perf_counter()

        per_op_ms = (end - start) * 1000 / iterations
        metrics.record("session_serialize", per_op_ms)

        print(f"\nSession to_dict: {per_op_ms:.3f}ms per call")
        assert per_op_ms < 1.0

    def test_incident_to_dict_performance(self):
        """Benchmark incident serialization."""
        from app.domain.entities.proctor_incident import ProctorIncident, IncidentType

        incident = ProctorIncident.create(
            session_id=uuid4(),
            incident_type=IncidentType.FACE_NOT_DETECTED,
            confidence=0.9,
            details={"frame": 100, "analysis": {"score": 0.5}},
        )

        iterations = 1000

        start = time.perf_counter()
        for _ in range(iterations):
            incident.to_dict()
        end = time.perf_counter()

        per_op_ms = (end - start) * 1000 / iterations
        metrics.record("incident_serialize", per_op_ms)

        print(f"\nIncident to_dict: {per_op_ms:.3f}ms per call")
        assert per_op_ms < 1.0


# ============================================================================
# Report Generation
# ============================================================================


@pytest.fixture(scope="session", autouse=True)
def print_report(request):
    """Print performance report at end of session."""
    yield

    if metrics.metrics:
        print(metrics.report())

        # Assert targets
        print("\nPerformance Target Validation:")
        targets = {
            "session_create": 1.0,
            "incident_create": 1.0,
            "session_lifecycle": 5.0,
            "session_save_memory": 1.0,
            "session_get_memory": 0.5,
            "rate_limit_check": 1.0,
            "session_serialize": 1.0,
        }

        for name, target in targets.items():
            stats = metrics.get_statistics(name)
            if stats:
                p95 = stats["p95"]
                status = "✅ PASS" if p95 < target else "❌ FAIL"
                print(f"  {name}: {p95:.2f}ms (target: <{target}ms) {status}")
