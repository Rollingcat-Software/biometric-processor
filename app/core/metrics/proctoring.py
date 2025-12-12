"""Proctoring-specific Prometheus metrics."""

import logging
from typing import Optional

try:
    from prometheus_client import Counter, Gauge, Histogram
except ImportError:
    Counter = None
    Gauge = None
    Histogram = None

logger = logging.getLogger(__name__)


class ProctorMetrics:
    """Proctoring-specific Prometheus metrics collector.

    Tracks:
    - Session lifecycle metrics
    - Frame processing metrics
    - ML analysis metrics
    - Incident metrics
    - WebSocket metrics
    - Rate limiting metrics
    """

    def __init__(self, prefix: str = "proctor"):
        """Initialize proctoring metrics.

        Args:
            prefix: Metric name prefix
        """
        if Counter is None:
            logger.warning("prometheus_client not installed, metrics disabled")
            self._enabled = False
            return

        self._enabled = True
        self._prefix = prefix

        # Session metrics
        self.sessions_total = Counter(
            f"{prefix}_sessions_total",
            "Total proctoring sessions created",
            ["tenant_id", "status"],
        )

        self.sessions_active = Gauge(
            f"{prefix}_sessions_active",
            "Currently active proctoring sessions",
            ["tenant_id"],
        )

        self.session_duration_seconds = Histogram(
            f"{prefix}_session_duration_seconds",
            "Session duration in seconds",
            ["tenant_id", "termination_reason"],
            buckets=[60, 300, 600, 1800, 3600, 7200, 14400],
        )

        # Frame processing metrics
        self.frames_processed_total = Counter(
            f"{prefix}_frames_processed_total",
            "Total frames processed",
            ["tenant_id"],
        )

        self.frame_processing_duration_ms = Histogram(
            f"{prefix}_frame_processing_duration_ms",
            "Frame processing duration in milliseconds",
            ["tenant_id"],
            buckets=[10, 25, 50, 100, 250, 500, 1000, 2500],
        )

        self.frame_processing_errors = Counter(
            f"{prefix}_frame_processing_errors_total",
            "Frame processing errors",
            ["tenant_id", "error_type"],
        )

        # ML analysis metrics
        self.gaze_analysis_duration_ms = Histogram(
            f"{prefix}_gaze_analysis_duration_ms",
            "Gaze analysis duration in milliseconds",
            buckets=[5, 10, 25, 50, 100, 250],
        )

        self.object_detection_duration_ms = Histogram(
            f"{prefix}_object_detection_duration_ms",
            "Object detection duration in milliseconds",
            buckets=[10, 25, 50, 100, 250, 500],
        )

        self.deepfake_detection_duration_ms = Histogram(
            f"{prefix}_deepfake_detection_duration_ms",
            "Deepfake detection duration in milliseconds",
            buckets=[10, 25, 50, 100, 250, 500],
        )

        self.face_verification_duration_ms = Histogram(
            f"{prefix}_face_verification_duration_ms",
            "Face verification duration in milliseconds",
            buckets=[10, 25, 50, 100, 250, 500],
        )

        # Incident metrics
        self.incidents_total = Counter(
            f"{prefix}_incidents_total",
            "Total incidents created",
            ["tenant_id", "incident_type", "severity"],
        )

        self.incidents_reviewed_total = Counter(
            f"{prefix}_incidents_reviewed_total",
            "Total incidents reviewed",
            ["tenant_id", "action"],
        )

        # Risk score distribution
        self.risk_score_histogram = Histogram(
            f"{prefix}_risk_score",
            "Session risk score distribution",
            ["tenant_id"],
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        )

        # WebSocket metrics
        self.ws_connections_active = Gauge(
            f"{prefix}_ws_connections_active",
            "Active WebSocket connections",
        )

        self.ws_messages_received = Counter(
            f"{prefix}_ws_messages_received_total",
            "WebSocket messages received",
            ["message_type"],
        )

        self.ws_messages_sent = Counter(
            f"{prefix}_ws_messages_sent_total",
            "WebSocket messages sent",
            ["message_type"],
        )

        self.ws_errors = Counter(
            f"{prefix}_ws_errors_total",
            "WebSocket errors",
            ["error_type"],
        )

        # Rate limiting metrics
        self.rate_limit_violations = Counter(
            f"{prefix}_rate_limit_violations_total",
            "Rate limit violations",
            ["tenant_id"],
        )

        self.rate_limit_throttled_frames = Counter(
            f"{prefix}_rate_limit_throttled_frames_total",
            "Frames throttled due to rate limiting",
            ["tenant_id"],
        )

    # Session recording methods
    def record_session_created(self, tenant_id: str) -> None:
        """Record a new session creation."""
        if not self._enabled:
            return
        self.sessions_total.labels(tenant_id=tenant_id, status="created").inc()

    def record_session_started(self, tenant_id: str) -> None:
        """Record session started."""
        if not self._enabled:
            return
        self.sessions_active.labels(tenant_id=tenant_id).inc()

    def record_session_ended(
        self,
        tenant_id: str,
        duration_seconds: float,
        termination_reason: str,
    ) -> None:
        """Record session ended."""
        if not self._enabled:
            return
        self.sessions_active.labels(tenant_id=tenant_id).dec()
        self.session_duration_seconds.labels(
            tenant_id=tenant_id,
            termination_reason=termination_reason,
        ).observe(duration_seconds)

    # Frame recording methods
    def record_frame_processed(
        self,
        tenant_id: str,
        duration_ms: float,
    ) -> None:
        """Record frame processing."""
        if not self._enabled:
            return
        self.frames_processed_total.labels(tenant_id=tenant_id).inc()
        self.frame_processing_duration_ms.labels(tenant_id=tenant_id).observe(duration_ms)

    def record_frame_error(self, tenant_id: str, error_type: str) -> None:
        """Record frame processing error."""
        if not self._enabled:
            return
        self.frame_processing_errors.labels(
            tenant_id=tenant_id,
            error_type=error_type,
        ).inc()

    # ML analysis recording methods
    def record_gaze_analysis(self, duration_ms: float) -> None:
        """Record gaze analysis duration."""
        if not self._enabled:
            return
        self.gaze_analysis_duration_ms.observe(duration_ms)

    def record_object_detection(self, duration_ms: float) -> None:
        """Record object detection duration."""
        if not self._enabled:
            return
        self.object_detection_duration_ms.observe(duration_ms)

    def record_deepfake_detection(self, duration_ms: float) -> None:
        """Record deepfake detection duration."""
        if not self._enabled:
            return
        self.deepfake_detection_duration_ms.observe(duration_ms)

    def record_face_verification(self, duration_ms: float) -> None:
        """Record face verification duration."""
        if not self._enabled:
            return
        self.face_verification_duration_ms.observe(duration_ms)

    # Incident recording methods
    def record_incident(
        self,
        tenant_id: str,
        incident_type: str,
        severity: str,
    ) -> None:
        """Record incident creation."""
        if not self._enabled:
            return
        self.incidents_total.labels(
            tenant_id=tenant_id,
            incident_type=incident_type,
            severity=severity,
        ).inc()

    def record_incident_reviewed(self, tenant_id: str, action: str) -> None:
        """Record incident review."""
        if not self._enabled:
            return
        self.incidents_reviewed_total.labels(
            tenant_id=tenant_id,
            action=action,
        ).inc()

    def record_risk_score(self, tenant_id: str, risk_score: float) -> None:
        """Record session risk score."""
        if not self._enabled:
            return
        self.risk_score_histogram.labels(tenant_id=tenant_id).observe(risk_score)

    # WebSocket recording methods
    def record_ws_connected(self) -> None:
        """Record WebSocket connection."""
        if not self._enabled:
            return
        self.ws_connections_active.inc()

    def record_ws_disconnected(self) -> None:
        """Record WebSocket disconnection."""
        if not self._enabled:
            return
        self.ws_connections_active.dec()

    def record_ws_message_received(self, message_type: str) -> None:
        """Record WebSocket message received."""
        if not self._enabled:
            return
        self.ws_messages_received.labels(message_type=message_type).inc()

    def record_ws_message_sent(self, message_type: str) -> None:
        """Record WebSocket message sent."""
        if not self._enabled:
            return
        self.ws_messages_sent.labels(message_type=message_type).inc()

    def record_ws_error(self, error_type: str) -> None:
        """Record WebSocket error."""
        if not self._enabled:
            return
        self.ws_errors.labels(error_type=error_type).inc()

    # Rate limiting recording methods
    def record_rate_limit_violation(self, tenant_id: str) -> None:
        """Record rate limit violation."""
        if not self._enabled:
            return
        self.rate_limit_violations.labels(tenant_id=tenant_id).inc()

    def record_throttled_frame(self, tenant_id: str) -> None:
        """Record throttled frame."""
        if not self._enabled:
            return
        self.rate_limit_throttled_frames.labels(tenant_id=tenant_id).inc()


# Global metrics instance
_proctor_metrics: Optional[ProctorMetrics] = None


def get_proctor_metrics() -> ProctorMetrics:
    """Get or create the global proctoring metrics instance.

    Returns:
        ProctorMetrics instance
    """
    global _proctor_metrics
    if _proctor_metrics is None:
        _proctor_metrics = ProctorMetrics()
    return _proctor_metrics


def init_proctor_metrics(prefix: str = "proctor") -> ProctorMetrics:
    """Initialize proctoring metrics with custom prefix.

    Args:
        prefix: Metric name prefix

    Returns:
        Initialized ProctorMetrics instance
    """
    global _proctor_metrics
    _proctor_metrics = ProctorMetrics(prefix=prefix)
    return _proctor_metrics
