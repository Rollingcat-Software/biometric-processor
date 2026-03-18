"""Proctoring-specific Prometheus metrics."""

from prometheus_client import Counter, Gauge, Histogram

# Session metrics
PROCTOR_SESSIONS_TOTAL = Counter(
    "biometric_proctor_sessions_total",
    "Total proctoring sessions",
    ["tenant_id", "status"],
)

PROCTOR_SESSIONS_ACTIVE = Gauge(
    "biometric_proctor_sessions_active",
    "Currently active proctoring sessions",
    ["tenant_id"],
)

PROCTOR_SESSION_DURATION = Histogram(
    "biometric_proctor_session_duration_seconds",
    "Session duration in seconds",
    ["status"],
    buckets=(60, 300, 600, 1800, 3600, 7200, 14400),
)

# Verification metrics
PROCTOR_VERIFICATIONS_TOTAL = Counter(
    "biometric_proctor_verifications_total",
    "Total verification attempts",
    ["result"],  # success, failure
)

PROCTOR_VERIFICATION_LATENCY = Histogram(
    "biometric_proctor_verification_latency_seconds",
    "Verification latency",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)

# Incident metrics
PROCTOR_INCIDENTS_TOTAL = Counter(
    "biometric_proctor_incidents_total",
    "Total incidents created",
    ["type", "severity"],
)

PROCTOR_INCIDENTS_BY_TYPE = Counter(
    "biometric_proctor_incidents_by_type_total",
    "Incidents by type",
    ["incident_type"],
)

# Analysis metrics
PROCTOR_FRAME_ANALYSIS_LATENCY = Histogram(
    "biometric_proctor_frame_analysis_latency_seconds",
    "Frame analysis latency",
    ["component"],  # face, gaze, object, audio, deepfake, total
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0),
)

PROCTOR_FRAMES_PROCESSED = Counter(
    "biometric_proctor_frames_processed_total",
    "Total frames processed",
    ["tenant_id"],
)

# Risk metrics
PROCTOR_RISK_SCORE = Histogram(
    "biometric_proctor_risk_score",
    "Session risk scores",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

PROCTOR_HIGH_RISK_SESSIONS = Gauge(
    "biometric_proctor_high_risk_sessions",
    "Number of sessions with high risk score",
    ["tenant_id"],
)

# Deepfake detection metrics
PROCTOR_DEEPFAKE_DETECTIONS_TOTAL = Counter(
    "biometric_proctor_deepfake_detections_total",
    "Total deepfake detections",
    ["result", "method"],  # result: detected/clean, method: frequency/texture/temporal/ensemble
)

PROCTOR_DEEPFAKE_LATENCY = Histogram(
    "biometric_proctor_deepfake_latency_seconds",
    "Deepfake detection latency",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0),
)

# Gaze tracking metrics
PROCTOR_GAZE_ON_SCREEN = Counter(
    "biometric_proctor_gaze_on_screen_total",
    "Gaze tracking results",
    ["result"],  # on_screen, off_screen
)

PROCTOR_GAZE_AWAY_DURATION = Histogram(
    "biometric_proctor_gaze_away_duration_seconds",
    "Duration of gaze away events",
    buckets=(1, 2, 5, 10, 20, 30, 60),
)

# Object detection metrics
PROCTOR_OBJECTS_DETECTED = Counter(
    "biometric_proctor_objects_detected_total",
    "Objects detected",
    ["object_type", "prohibited"],
)

# Audio analysis metrics
PROCTOR_AUDIO_EVENTS = Counter(
    "biometric_proctor_audio_events_total",
    "Audio analysis events",
    ["event_type"],  # voice_activity, multiple_speakers, silence
)

# Rate limiting metrics (re-exported from resilience module)

# Circuit breaker metrics (re-exported from resilience module)


def record_session_created(tenant_id: str) -> None:
    """Record session creation."""
    PROCTOR_SESSIONS_TOTAL.labels(tenant_id=tenant_id, status="created").inc()


def record_session_started(tenant_id: str) -> None:
    """Record session start."""
    PROCTOR_SESSIONS_TOTAL.labels(tenant_id=tenant_id, status="started").inc()
    PROCTOR_SESSIONS_ACTIVE.labels(tenant_id=tenant_id).inc()


def record_session_ended(tenant_id: str, status: str, duration_seconds: float) -> None:
    """Record session end."""
    PROCTOR_SESSIONS_TOTAL.labels(tenant_id=tenant_id, status=status).inc()
    PROCTOR_SESSIONS_ACTIVE.labels(tenant_id=tenant_id).dec()
    PROCTOR_SESSION_DURATION.labels(status=status).observe(duration_seconds)


def record_verification(success: bool, latency_seconds: float) -> None:
    """Record verification attempt."""
    result = "success" if success else "failure"
    PROCTOR_VERIFICATIONS_TOTAL.labels(result=result).inc()
    PROCTOR_VERIFICATION_LATENCY.observe(latency_seconds)


def record_incident(incident_type: str, severity: str) -> None:
    """Record incident creation."""
    PROCTOR_INCIDENTS_TOTAL.labels(type=incident_type, severity=severity).inc()
    PROCTOR_INCIDENTS_BY_TYPE.labels(incident_type=incident_type).inc()


def record_frame_analysis(component: str, latency_seconds: float, tenant_id: str) -> None:
    """Record frame analysis."""
    PROCTOR_FRAME_ANALYSIS_LATENCY.labels(component=component).observe(latency_seconds)
    if component == "total":
        PROCTOR_FRAMES_PROCESSED.labels(tenant_id=tenant_id).inc()


def record_risk_score(score: float) -> None:
    """Record session risk score."""
    PROCTOR_RISK_SCORE.observe(score)


def record_deepfake_detection(
    is_deepfake: bool,
    method: str,
    latency_seconds: float,
) -> None:
    """Record deepfake detection result."""
    result = "detected" if is_deepfake else "clean"
    PROCTOR_DEEPFAKE_DETECTIONS_TOTAL.labels(result=result, method=method).inc()
    PROCTOR_DEEPFAKE_LATENCY.observe(latency_seconds)


def record_gaze_result(is_on_screen: bool, away_duration: float = None) -> None:
    """Record gaze tracking result."""
    result = "on_screen" if is_on_screen else "off_screen"
    PROCTOR_GAZE_ON_SCREEN.labels(result=result).inc()
    if away_duration is not None and away_duration > 0:
        PROCTOR_GAZE_AWAY_DURATION.observe(away_duration)


def record_object_detection(object_type: str, is_prohibited: bool) -> None:
    """Record object detection."""
    PROCTOR_OBJECTS_DETECTED.labels(
        object_type=object_type,
        prohibited=str(is_prohibited).lower(),
    ).inc()


def record_audio_event(event_type: str) -> None:
    """Record audio analysis event."""
    PROCTOR_AUDIO_EVENTS.labels(event_type=event_type).inc()
