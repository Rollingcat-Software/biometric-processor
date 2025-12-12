"""Proctoring API routes."""

import base64
import logging
from typing import Optional
from uuid import UUID

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Header, Query, status

from app.api.schemas.proctor import (
    CreateIncidentRequest,
    CreateIncidentResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    EndSessionRequest,
    EndSessionResponse,
    IncidentListResponse,
    IncidentResponse,
    RateLimitStatusResponse,
    ReviewIncidentRequest,
    SessionListResponse,
    SessionReportResponse,
    SessionResponse,
    StartSessionRequest,
    StartSessionResponse,
    SubmitFrameRequest,
    SubmitFrameResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/proctor", tags=["proctoring"])


def get_tenant_id(x_tenant_id: str = Header(..., alias="X-Tenant-ID")) -> str:
    """Extract tenant ID from header."""
    return x_tenant_id


def get_reviewer_id(x_reviewer_id: str = Header(None, alias="X-Reviewer-ID")) -> Optional[str]:
    """Extract reviewer ID from header."""
    return x_reviewer_id


# Session management endpoints

@router.post("/sessions", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: CreateSessionRequest,
    tenant_id: str = Depends(get_tenant_id),
):
    """Create a new proctoring session.

    Creates a new session for monitoring an exam-taker. The session must be
    started separately to begin active monitoring.
    """
    try:
        from app.application.use_cases.proctor.create_session import (
            CreateProctorSession,
            CreateSessionRequest as UseCaseRequest,
        )
        from app.api.dependencies import get_session_repository

        repository = await get_session_repository()
        use_case = CreateProctorSession(repository)

        result = await use_case.execute(
            UseCaseRequest(
                exam_id=request.exam_id,
                user_id=request.user_id,
                tenant_id=tenant_id,
                config=request.config.dict() if request.config else None,
                metadata=request.metadata,
            )
        )

        return CreateSessionResponse(
            session_id=result.session_id,
            exam_id=result.exam_id,
            user_id=result.user_id,
            status=result.status,
            config=result.config,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session",
        )


@router.post("/sessions/{session_id}/start", response_model=StartSessionResponse)
async def start_session(
    session_id: UUID,
    request: StartSessionRequest = None,
    tenant_id: str = Depends(get_tenant_id),
):
    """Start a proctoring session.

    Begins active monitoring. Requires a baseline image or existing user embedding.
    """
    try:
        from app.application.use_cases.proctor.start_session import (
            StartProctorSession,
            StartSessionRequest as UseCaseRequest,
        )
        from app.api.dependencies import get_session_repository, get_embedding_repository

        session_repo = await get_session_repository()
        embedding_repo = await get_embedding_repository()

        use_case = StartProctorSession(
            session_repository=session_repo,
            embedding_repository=embedding_repo,
        )

        # Decode baseline image if provided
        baseline_image = None
        if request and request.baseline_image_base64:
            import cv2
            image_bytes = base64.b64decode(request.baseline_image_base64)
            nparr = np.frombuffer(image_bytes, np.uint8)
            baseline_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        result = await use_case.execute(
            UseCaseRequest(
                session_id=session_id,
                tenant_id=tenant_id,
                baseline_image=baseline_image,
            )
        )

        return StartSessionResponse(
            session_id=result.session_id,
            status=result.status,
            started_at=result.started_at,
            has_baseline=result.has_baseline,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start session",
        )


@router.post("/sessions/{session_id}/pause")
async def pause_session(
    session_id: UUID,
    tenant_id: str = Depends(get_tenant_id),
):
    """Pause a proctoring session."""
    try:
        from app.application.use_cases.proctor.end_session import PauseProctorSession
        from app.api.dependencies import get_session_repository

        repository = await get_session_repository()
        use_case = PauseProctorSession(repository)

        result = await use_case.execute(session_id, tenant_id)
        return result

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/sessions/{session_id}/resume")
async def resume_session(
    session_id: UUID,
    tenant_id: str = Depends(get_tenant_id),
):
    """Resume a paused proctoring session."""
    try:
        from app.application.use_cases.proctor.end_session import ResumeProctorSession
        from app.api.dependencies import get_session_repository

        repository = await get_session_repository()
        use_case = ResumeProctorSession(repository)

        result = await use_case.execute(session_id, tenant_id)
        return result

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/sessions/{session_id}/end", response_model=EndSessionResponse)
async def end_session(
    session_id: UUID,
    request: EndSessionRequest = None,
    tenant_id: str = Depends(get_tenant_id),
):
    """End a proctoring session."""
    try:
        from app.application.use_cases.proctor.end_session import (
            EndProctorSession,
            EndSessionRequest as UseCaseRequest,
        )
        from app.api.dependencies import get_session_repository

        repository = await get_session_repository()
        use_case = EndProctorSession(repository)

        result = await use_case.execute(
            UseCaseRequest(
                session_id=session_id,
                tenant_id=tenant_id,
                reason=request.reason if request else None,
            )
        )

        return EndSessionResponse(
            session_id=result.session_id,
            status=result.status,
            ended_at=result.ended_at,
            duration_seconds=result.duration_seconds,
            termination_reason=result.termination_reason,
            final_risk_score=result.final_risk_score,
            total_incidents=result.total_incidents,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    tenant_id: str = Depends(get_tenant_id),
):
    """Get session details."""
    try:
        from app.api.dependencies import get_session_repository

        repository = await get_session_repository()
        session = await repository.get_by_id(session_id, tenant_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found",
            )

        return SessionResponse(**session.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get session",
        )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    tenant_id: str = Depends(get_tenant_id),
    exam_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List proctoring sessions with optional filters."""
    try:
        from app.api.dependencies import get_session_repository
        from app.domain.entities.proctor_session import SessionStatus

        repository = await get_session_repository()

        if exam_id:
            sessions = await repository.get_sessions_by_exam(
                exam_id, tenant_id, limit, offset
            )
        elif user_id:
            sessions = await repository.get_sessions_by_user(
                user_id, tenant_id, limit, offset
            )
        elif status:
            try:
                session_status = SessionStatus(status)
                sessions = await repository.get_sessions_by_status(
                    session_status, tenant_id, limit, offset
                )
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status}",
                )
        else:
            sessions = await repository.get_active_sessions(tenant_id, limit, offset)

        return SessionListResponse(
            sessions=[SessionResponse(**s.to_dict()) for s in sessions],
            total=len(sessions),
            limit=limit,
            offset=offset,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list sessions",
        )


# Frame submission endpoints

@router.post("/sessions/{session_id}/frames", response_model=SubmitFrameResponse)
async def submit_frame(
    session_id: UUID,
    request: SubmitFrameRequest,
    tenant_id: str = Depends(get_tenant_id),
):
    """Submit a frame for analysis.

    Analyzes the frame for face verification, gaze tracking, object detection,
    and other proctoring checks. Returns analysis results and any incidents created.
    """
    try:
        import cv2
        from app.application.use_cases.proctor.submit_frame import (
            SubmitFrame,
            SubmitFrameRequest as UseCaseRequest,
        )
        from app.api.dependencies import (
            get_session_repository,
            get_incident_repository,
            get_rate_limiter,
        )

        # Decode frame
        frame_bytes = base64.b64decode(request.frame_base64)
        nparr = np.frombuffer(frame_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image data",
            )

        # Decode audio if provided
        audio_data = None
        if request.audio_base64:
            audio_data = base64.b64decode(request.audio_base64)

        session_repo = await get_session_repository()
        incident_repo = await get_incident_repository()
        rate_limiter = await get_rate_limiter()

        use_case = SubmitFrame(
            session_repository=session_repo,
            incident_repository=incident_repo,
            rate_limiter=rate_limiter,
        )

        result = await use_case.execute(
            UseCaseRequest(
                session_id=session_id,
                tenant_id=tenant_id,
                frame=frame,
                frame_number=request.frame_number,
                audio_data=audio_data,
                audio_sample_rate=request.audio_sample_rate,
            )
        )

        return SubmitFrameResponse(
            session_id=result.session_id,
            frame_number=result.frame_number,
            risk_score=result.risk_score,
            face_detected=result.face_detected,
            face_matched=result.face_matched,
            incidents_created=result.incidents_created,
            processing_time_ms=result.processing_time_ms,
            analysis=result.analysis,
            rate_limit=result.rate_limit,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process frame: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process frame",
        )


# Incident endpoints

@router.post(
    "/sessions/{session_id}/incidents",
    response_model=CreateIncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_incident(
    session_id: UUID,
    request: CreateIncidentRequest,
    tenant_id: str = Depends(get_tenant_id),
):
    """Manually create an incident for a session."""
    try:
        from app.application.use_cases.proctor.create_incident import (
            CreateIncident,
            CreateIncidentRequest as UseCaseRequest,
        )
        from app.api.dependencies import get_session_repository, get_incident_repository

        session_repo = await get_session_repository()
        incident_repo = await get_incident_repository()

        use_case = CreateIncident(
            incident_repository=incident_repo,
            session_repository=session_repo,
        )

        result = await use_case.execute(
            UseCaseRequest(
                session_id=session_id,
                tenant_id=tenant_id,
                incident_type=request.incident_type,
                confidence=request.confidence,
                severity=request.severity,
                details=request.details,
            )
        )

        return CreateIncidentResponse(
            incident_id=result.incident_id,
            session_id=result.session_id,
            incident_type=result.incident_type,
            severity=result.severity,
            confidence=result.confidence,
            risk_contribution=result.risk_contribution,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/sessions/{session_id}/incidents", response_model=IncidentListResponse)
async def list_incidents(
    session_id: UUID,
    severity: Optional[str] = Query(None),
    reviewed: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List incidents for a session."""
    try:
        from app.application.use_cases.proctor.get_session_report import (
            ListSessionIncidents,
        )
        from app.api.dependencies import get_incident_repository

        repository = await get_incident_repository()
        use_case = ListSessionIncidents(repository)

        incidents = await use_case.execute(
            session_id=session_id,
            severity=severity,
            reviewed=reviewed,
            limit=limit,
            offset=offset,
        )

        return IncidentListResponse(
            incidents=[IncidentResponse(**i) for i in incidents],
            total=len(incidents),
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/incidents/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: UUID):
    """Get incident details."""
    try:
        from app.api.dependencies import get_incident_repository

        repository = await get_incident_repository()
        incident = await repository.get_by_id(incident_id)

        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident {incident_id} not found",
            )

        return IncidentResponse(**incident.to_dict())

    except HTTPException:
        raise


@router.post("/incidents/{incident_id}/review")
async def review_incident(
    incident_id: UUID,
    request: ReviewIncidentRequest,
    reviewer_id: str = Depends(get_reviewer_id),
):
    """Review an incident and take action."""
    if not reviewer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Reviewer-ID header required",
        )

    try:
        from app.application.use_cases.proctor.create_incident import (
            ReviewIncident,
            ReviewIncidentRequest as UseCaseRequest,
        )
        from app.api.dependencies import get_incident_repository

        repository = await get_incident_repository()
        use_case = ReviewIncident(repository)

        result = await use_case.execute(
            UseCaseRequest(
                incident_id=incident_id,
                reviewer=reviewer_id,
                action=request.action,
                notes=request.notes,
            )
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Report endpoints

@router.get("/sessions/{session_id}/report", response_model=SessionReportResponse)
async def get_session_report(
    session_id: UUID,
    tenant_id: str = Depends(get_tenant_id),
):
    """Get comprehensive session report."""
    try:
        from app.application.use_cases.proctor.get_session_report import GetSessionReport
        from app.api.dependencies import get_session_repository, get_incident_repository

        session_repo = await get_session_repository()
        incident_repo = await get_incident_repository()

        use_case = GetSessionReport(
            session_repository=session_repo,
            incident_repository=incident_repo,
        )

        report = await use_case.execute(session_id, tenant_id)

        return SessionReportResponse(
            session_id=report.session_id,
            exam_id=report.exam_id,
            user_id=report.user_id,
            status=report.status,
            duration_seconds=report.duration_seconds,
            risk_score=report.risk_score,
            verification_count=report.verification_count,
            verification_failures=report.verification_failures,
            verification_success_rate=report.verification_success_rate,
            total_incidents=report.total_incidents,
            incidents_by_severity=report.incidents_by_severity,
            critical_incidents=report.critical_incidents,
            timeline=report.timeline,
            summary=report.summary,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Rate limit endpoints

@router.get("/sessions/{session_id}/rate-limit", response_model=RateLimitStatusResponse)
async def get_rate_limit_status(
    session_id: UUID,
):
    """Get rate limit status for a session."""
    try:
        from app.api.dependencies import get_rate_limiter

        rate_limiter = await get_rate_limiter()
        if not rate_limiter:
            return RateLimitStatusResponse(
                session_id=str(session_id),
                frames_last_minute=0,
                remaining_this_minute=60,
                violation_count=0,
                is_throttled=False,
            )

        stats = await rate_limiter.get_session_stats(session_id)

        return RateLimitStatusResponse(
            session_id=str(session_id),
            **stats,
        )

    except Exception as e:
        logger.error(f"Failed to get rate limit status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get rate limit status",
        )
