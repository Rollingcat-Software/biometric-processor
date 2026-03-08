"""Liveness puzzle API routes.

This module provides endpoints for the liveness puzzle challenge-response system:
- POST /liveness/generate-puzzle: Generate a new liveness puzzle
- POST /liveness/verify: Verify puzzle completion
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header

from app.api.schemas.puzzle import (
    GeneratePuzzleRequest,
    GeneratePuzzleResponse,
    PuzzleStep,
    VerifyPuzzleRequest,
    VerifyPuzzleResponse,
)
from app.application.use_cases.generate_puzzle import GeneratePuzzleUseCase
from app.application.use_cases.verify_puzzle import VerifyPuzzleUseCase
from app.core.container import get_generate_puzzle_use_case, get_verify_puzzle_use_case

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/liveness", tags=["Liveness Puzzle"])


@router.post(
    "/generate-puzzle",
    response_model=GeneratePuzzleResponse,
    summary="Generate a liveness puzzle",
    description="""
Generate a new liveness puzzle with randomized challenge steps.

The puzzle contains a sequence of actions the user must perform
(blink, smile, turn head, etc.) within a time limit.

**Difficulty Levels:**
- `easy`: 2-3 steps, 7 seconds per step
- `standard`: 3-4 steps, 5 seconds per step
- `hard`: 4-5 steps, 4 seconds per step

**Response includes:**
- Unique puzzle ID (required for verification)
- Ordered list of challenge steps
- Detection thresholds for client-side processing
- Expiration timestamp

**Flow:**
1. Client calls this endpoint to get a puzzle
2. Client displays challenges and captures user actions
3. Client calls /verify with collected evidence
    """,
    responses={
        200: {
            "description": "Puzzle generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "puzzle_id": "550e8400-e29b-41d4-a716-446655440000",
                        "steps": [
                            {"action": "blink", "duration_seconds": 5.0, "order": 0},
                            {"action": "smile", "duration_seconds": 5.0, "order": 1},
                            {"action": "turn_left", "duration_seconds": 5.0, "order": 2},
                        ],
                        "timeout_seconds": 60,
                        "expires_at": "2024-12-28T12:00:00Z",
                        "thresholds": {
                            "ear_threshold": 0.21,
                            "mar_threshold": 0.4,
                        },
                    }
                }
            },
        },
        400: {"description": "Invalid request parameters"},
        500: {"description": "Internal server error"},
    },
)
async def generate_puzzle(
    request: GeneratePuzzleRequest,
    x_tenant_id: Optional[str] = Header(default=None, alias="X-Tenant-ID"),
    use_case: GeneratePuzzleUseCase = Depends(get_generate_puzzle_use_case),
) -> GeneratePuzzleResponse:
    """Generate a new liveness puzzle.

    Args:
        request: Puzzle generation parameters
        x_tenant_id: Optional tenant identifier from header
        use_case: Injected use case

    Returns:
        Generated puzzle with steps and thresholds
    """
    start_time = time.time()

    try:
        # Use tenant from header if not in request
        tenant_id = request.tenant_id or x_tenant_id

        puzzle = await use_case.execute(
            tenant_id=tenant_id,
            user_id=request.user_id,
            difficulty=request.difficulty.value,
            min_steps=request.min_steps,
            max_steps=request.max_steps,
            timeout_seconds=request.timeout_seconds,
        )

        processing_time = (time.time() - start_time) * 1000

        logger.info(
            f"Generated puzzle {puzzle.puzzle_id} in {processing_time:.1f}ms"
        )

        return GeneratePuzzleResponse(
            puzzle_id=puzzle.puzzle_id,
            steps=[
                PuzzleStep(
                    action=step.action,
                    duration_seconds=step.duration_seconds,
                    order=step.order,
                )
                for step in puzzle.steps
            ],
            timeout_seconds=request.timeout_seconds,
            expires_at=puzzle.expires_at,
            thresholds=use_case.get_thresholds(),
        )

    except ValueError as e:
        logger.warning(f"Invalid puzzle request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating puzzle: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate puzzle. Please try again.",
        )


@router.post(
    "/verify",
    response_model=VerifyPuzzleResponse,
    summary="Verify puzzle completion",
    description="""
Verify that a liveness puzzle was completed successfully.

The client submits evidence for each step including:
- Action performed
- Start and end timestamps
- Detection confidence
- Optional metrics (EAR, MAR values)

**Validation includes:**
- Puzzle existence and expiration
- Step sequence matches puzzle
- Timestamp monotonicity (anti-replay)
- Minimum confidence per step
- Overall score threshold

**Response includes:**
- Success/failure status
- Liveness confirmation
- Reason codes for failures
- Overall liveness score (0-100)
    """,
    responses={
        200: {
            "description": "Verification completed",
            "content": {
                "application/json": {
                    "examples": {
                        "success": {
                            "summary": "Successful verification",
                            "value": {
                                "success": True,
                                "liveness_confirmed": True,
                                "steps_completed": 3,
                                "total_steps": 3,
                                "completion_time_seconds": 12.5,
                                "reason_codes": [],
                                "overall_score": 85.2,
                                "message": "Liveness verified successfully",
                            },
                        },
                        "failed": {
                            "summary": "Failed verification",
                            "value": {
                                "success": False,
                                "liveness_confirmed": False,
                                "steps_completed": 2,
                                "total_steps": 3,
                                "completion_time_seconds": 15.0,
                                "reason_codes": ["STEP_2_LOW_CONFIDENCE"],
                                "overall_score": 45.0,
                                "message": "Liveness check failed",
                            },
                        },
                    }
                }
            },
        },
        400: {"description": "Invalid request"},
        404: {"description": "Puzzle not found"},
        500: {"description": "Internal server error"},
    },
)
async def verify_puzzle(
    request: VerifyPuzzleRequest,
    use_case: VerifyPuzzleUseCase = Depends(get_verify_puzzle_use_case),
) -> VerifyPuzzleResponse:
    """Verify liveness puzzle completion.

    Args:
        request: Verification request with step evidence
        use_case: Injected use case

    Returns:
        Verification result with liveness status
    """
    start_time = time.time()

    try:
        result = await use_case.execute(
            puzzle_id=request.puzzle_id,
            results=[r.model_dump() for r in request.results],
            final_frame=request.final_frame,
            client_meta=request.client_meta.model_dump() if request.client_meta else None,
        )

        processing_time = (time.time() - start_time) * 1000

        # Generate message
        if result.liveness_confirmed:
            message = "Liveness verified successfully"
        elif "PUZZLE_NOT_FOUND" in result.reason_codes:
            message = "Puzzle not found or expired"
        elif "PUZZLE_EXPIRED" in result.reason_codes:
            message = "Puzzle has expired"
        elif "PUZZLE_ALREADY_COMPLETED" in result.reason_codes:
            message = "Puzzle was already completed"
        else:
            message = "Liveness check failed"

        logger.info(
            f"Verified puzzle {request.puzzle_id} in {processing_time:.1f}ms: "
            f"success={result.success}, score={result.overall_score:.1f}"
        )

        return VerifyPuzzleResponse(
            success=result.success,
            liveness_confirmed=result.liveness_confirmed,
            steps_completed=result.steps_completed,
            total_steps=result.total_steps,
            completion_time_seconds=result.completion_time_seconds,
            reason_codes=result.reason_codes,
            overall_score=result.overall_score,
            message=message,
        )

    except Exception as e:
        logger.error(f"Error verifying puzzle: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to verify puzzle. Please try again.",
        )
