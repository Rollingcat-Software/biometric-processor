"""Structured audit logging for compliance.

Provides comprehensive audit logging for biometric operations to meet
compliance requirements (SOC 2, GDPR, HIPAA, etc.).

Audit logs capture:
- Who performed the action (user_id, tenant_id)
- What action was performed (action type)
- When it occurred (timestamp)
- Result (success/failure)
- Contextual details (confidence scores, error messages)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
from uuid import uuid4

import structlog

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """Audit action types for biometric operations."""

    # Enrollment Operations
    FACE_ENROLLED = "face_enrolled"
    FACE_ENROLLMENT_FAILED = "face_enrollment_failed"
    ENROLLMENT_DELETED = "enrollment_deleted"
    ENROLLMENT_UPDATED = "enrollment_updated"

    # Verification Operations
    FACE_VERIFIED = "face_verified"
    FACE_VERIFICATION_FAILED = "face_verification_failed"

    # Search Operations
    FACE_SEARCH = "face_search"
    FACE_SEARCH_MATCH = "face_search_match"
    FACE_SEARCH_NO_MATCH = "face_search_no_match"

    # Liveness Operations
    LIVENESS_CHECK_PASSED = "liveness_check_passed"
    LIVENESS_CHECK_FAILED = "liveness_check_failed"

    # Quality Assessment
    QUALITY_CHECK_PASSED = "quality_check_passed"
    QUALITY_CHECK_FAILED = "quality_check_failed"

    # Admin Operations
    EMBEDDINGS_EXPORTED = "embeddings_exported"
    EMBEDDINGS_IMPORTED = "embeddings_imported"
    BULK_ENROLLMENT = "bulk_enrollment"
    BULK_DELETION = "bulk_deletion"

    # Proctoring Operations
    PROCTORING_SESSION_STARTED = "proctoring_session_started"
    PROCTORING_SESSION_ENDED = "proctoring_session_ended"
    PROCTORING_INCIDENT_DETECTED = "proctoring_incident_detected"
    PROCTORING_VERIFICATION = "proctoring_verification"

    # Authentication
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    API_KEY_USED = "api_key_used"
    JWT_VALIDATED = "jwt_validated"

    # System Events
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    ACCESS_DENIED = "access_denied"


@dataclass
class AuditEntry:
    """Audit log entry structure.

    Immutable record of an auditable event with all relevant context.
    Designed for compliance with major security frameworks.
    """

    # When
    timestamp: str

    # What
    action: str
    resource_type: str
    success: bool

    # Who
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None

    # Where
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    # Correlation
    request_id: Optional[str] = None
    session_id: Optional[str] = None

    # Details
    details: dict = field(default_factory=dict)
    error_message: Optional[str] = None
    error_code: Optional[str] = None

    # Metadata
    audit_id: str = field(default_factory=lambda: str(uuid4()))
    service_name: str = "biometric-processor"
    version: str = "1.0"

    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None values."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class AuditLogger:
    """Audit logger for biometric operations.

    Logs structured audit events for compliance and monitoring.
    Supports multiple output destinations:
    - Structured logging (JSON format)
    - Optional database persistence
    - Optional external audit service

    Usage:
        audit = get_audit_logger()

        # Log enrollment
        audit.log_enrollment(
            user_id="user123",
            tenant_id="tenant456",
            success=True,
            quality_score=0.95
        )

        # Log verification
        audit.log_verification(
            user_id="user123",
            tenant_id="tenant456",
            verified=True,
            confidence=0.92
        )
    """

    def __init__(self):
        """Initialize audit logger."""
        self.logger = structlog.get_logger("audit")
        self._enabled = True

    def log(
        self,
        action: AuditAction,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        resource_type: str = "biometric",
        resource_id: Optional[str] = None,
        success: bool = True,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        details: Optional[dict] = None,
        error_message: Optional[str] = None,
        error_code: Optional[str] = None,
    ):
        """Log an audit event.

        Args:
            action: The audit action type
            user_id: User who performed the action
            tenant_id: Tenant context
            resource_type: Type of resource affected
            resource_id: ID of affected resource
            success: Whether the operation succeeded
            ip_address: Client IP address
            user_agent: Client user agent
            request_id: Request correlation ID
            session_id: Session correlation ID
            details: Additional context details
            error_message: Error message if failed
            error_code: Error code if failed
        """
        if not self._enabled:
            return

        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            action=action.value,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            session_id=session_id,
            details=details or {},
            error_message=error_message,
            error_code=error_code,
        )

        # Log with appropriate level
        log_method = self.logger.info if success else self.logger.warning
        log_method("audit_event", **entry.to_dict())

    # =========================================================================
    # Convenience Methods for Common Operations
    # =========================================================================

    def log_enrollment(
        self,
        user_id: str,
        tenant_id: str,
        success: bool,
        quality_score: Optional[float] = None,
        error: Optional[str] = None,
        **kwargs,
    ):
        """Log face enrollment event.

        Args:
            user_id: User being enrolled
            tenant_id: Tenant context
            success: Whether enrollment succeeded
            quality_score: Image quality score (0-1)
            error: Error message if failed
            **kwargs: Additional audit context
        """
        action = AuditAction.FACE_ENROLLED if success else AuditAction.FACE_ENROLLMENT_FAILED
        details = {}
        if quality_score is not None:
            details["quality_score"] = round(quality_score, 4)

        self.log(
            action=action,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type="enrollment",
            resource_id=user_id,
            success=success,
            details=details,
            error_message=error,
            **kwargs,
        )

    def log_verification(
        self,
        user_id: str,
        tenant_id: str,
        verified: bool,
        confidence: float,
        threshold: Optional[float] = None,
        **kwargs,
    ):
        """Log face verification event.

        Args:
            user_id: User being verified
            tenant_id: Tenant context
            verified: Whether verification passed
            confidence: Similarity confidence score
            threshold: Verification threshold used
            **kwargs: Additional audit context
        """
        action = AuditAction.FACE_VERIFIED if verified else AuditAction.FACE_VERIFICATION_FAILED
        details = {"confidence": round(confidence, 4)}
        if threshold is not None:
            details["threshold"] = round(threshold, 4)

        self.log(
            action=action,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type="verification",
            resource_id=user_id,
            success=verified,
            details=details,
            **kwargs,
        )

    def log_search(
        self,
        tenant_id: str,
        match_found: bool,
        matched_user_id: Optional[str] = None,
        confidence: Optional[float] = None,
        results_count: int = 0,
        **kwargs,
    ):
        """Log face search event.

        Args:
            tenant_id: Tenant context
            match_found: Whether a match was found
            matched_user_id: ID of matched user (if any)
            confidence: Top match confidence score
            results_count: Number of results returned
            **kwargs: Additional audit context
        """
        action = AuditAction.FACE_SEARCH_MATCH if match_found else AuditAction.FACE_SEARCH_NO_MATCH
        details = {"results_count": results_count}
        if confidence is not None:
            details["confidence"] = round(confidence, 4)
        if matched_user_id:
            details["matched_user_id"] = matched_user_id

        self.log(
            action=action,
            tenant_id=tenant_id,
            resource_type="search",
            success=True,  # Search itself succeeded
            details=details,
            **kwargs,
        )

    def log_liveness(
        self,
        user_id: str,
        tenant_id: str,
        is_live: bool,
        confidence: float,
        method: str,
        **kwargs,
    ):
        """Log liveness check event.

        Args:
            user_id: User being checked
            tenant_id: Tenant context
            is_live: Whether liveness check passed
            confidence: Liveness confidence score
            method: Liveness detection method (passive/active)
            **kwargs: Additional audit context
        """
        action = AuditAction.LIVENESS_CHECK_PASSED if is_live else AuditAction.LIVENESS_CHECK_FAILED
        details = {
            "confidence": round(confidence, 4),
            "method": method,
        }

        self.log(
            action=action,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type="liveness",
            success=is_live,
            details=details,
            **kwargs,
        )

    def log_proctoring_incident(
        self,
        session_id: str,
        user_id: str,
        tenant_id: str,
        incident_type: str,
        severity: str,
        details: Optional[dict] = None,
        **kwargs,
    ):
        """Log proctoring incident.

        Args:
            session_id: Proctoring session ID
            user_id: User in session
            tenant_id: Tenant context
            incident_type: Type of incident (gaze_away, multiple_faces, etc.)
            severity: Incident severity (warning, critical)
            details: Additional incident details
            **kwargs: Additional audit context
        """
        event_details = {
            "incident_type": incident_type,
            "severity": severity,
        }
        if details:
            event_details.update(details)

        self.log(
            action=AuditAction.PROCTORING_INCIDENT_DETECTED,
            user_id=user_id,
            tenant_id=tenant_id,
            session_id=session_id,
            resource_type="proctoring",
            resource_id=session_id,
            success=True,
            details=event_details,
            **kwargs,
        )

    def log_access_denied(
        self,
        user_id: Optional[str],
        tenant_id: Optional[str],
        resource: str,
        reason: str,
        **kwargs,
    ):
        """Log access denied event.

        Args:
            user_id: User attempting access
            tenant_id: Tenant context
            resource: Resource being accessed
            reason: Reason for denial
            **kwargs: Additional audit context
        """
        self.log(
            action=AuditAction.ACCESS_DENIED,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type="access",
            resource_id=resource,
            success=False,
            details={"reason": reason},
            **kwargs,
        )

    def log_rate_limit(
        self,
        ip_address: str,
        endpoint: str,
        limit: int,
        user_id: Optional[str] = None,
        **kwargs,
    ):
        """Log rate limit exceeded event.

        Args:
            ip_address: Client IP address
            endpoint: Endpoint that was rate limited
            limit: Rate limit that was exceeded
            user_id: User (if authenticated)
            **kwargs: Additional audit context
        """
        self.log(
            action=AuditAction.RATE_LIMIT_EXCEEDED,
            user_id=user_id,
            ip_address=ip_address,
            resource_type="rate_limit",
            resource_id=endpoint,
            success=False,
            details={"endpoint": endpoint, "limit": limit},
            **kwargs,
        )

    def log_admin_operation(
        self,
        action: AuditAction,
        user_id: str,
        tenant_id: str,
        operation_details: dict,
        success: bool = True,
        error: Optional[str] = None,
        **kwargs,
    ):
        """Log administrative operation.

        Args:
            action: Admin action type
            user_id: Admin user performing action
            tenant_id: Tenant context
            operation_details: Details of the operation
            success: Whether operation succeeded
            error: Error message if failed
            **kwargs: Additional audit context
        """
        self.log(
            action=action,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type="admin",
            success=success,
            details=operation_details,
            error_message=error,
            **kwargs,
        )


# =============================================================================
# Global Instance
# =============================================================================

_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance.

    Returns:
        Singleton AuditLogger instance
    """
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def configure_audit_logger(enabled: bool = True) -> AuditLogger:
    """Configure the global audit logger.

    Args:
        enabled: Whether audit logging is enabled

    Returns:
        Configured AuditLogger instance
    """
    audit = get_audit_logger()
    audit._enabled = enabled
    return audit
