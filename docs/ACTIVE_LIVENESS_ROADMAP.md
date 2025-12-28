# Active Liveness System - Comprehensive Roadmap & Implementation Plan

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Architecture Overview](#current-architecture-overview)
3. [Milestone Status Analysis](#milestone-status-analysis)
4. [Frontend-Backend Connection Map](#frontend-backend-connection-map)
5. [SE Checklist Compliance Analysis](#se-checklist-compliance-analysis)
6. [Implementation Plans for Missing Features](#implementation-plans-for-missing-features)
7. [Recommended Action Items](#recommended-action-items)

---

## Executive Summary

### Overall System Readiness: **70%**

| Milestone | Completion | Status |
|-----------|------------|--------|
| M1: Contracts & Scaffolding | 90% | Near Complete |
| M2: Puzzle Loop Frontend | 70% | Partial |
| M3: Backend Verification | 85% | Mostly Complete |
| M4: Hardening | 60% | In Progress |
| M5: Security & Metrics | 40% | Early Stage |

### Key Findings

**Strengths:**
- Robust multi-method liveness detection (texture + active combined)
- Production-ready ML detectors with performance optimizations
- Clean architecture following DDD principles
- Comprehensive API schemas with 7 challenge types
- Real-time WebSocket streaming with reconnection handling

**Critical Gaps:**
- Missing `generate-puzzle` and `verify` endpoints for proper challenge-response
- No Redis-backed session persistence (in-memory only)
- No anti-replay protection (timestamp validation)
- Frontend lacks explicit state machine for challenge flow
- No tenant-specific policy configuration

---

## Current Architecture Overview

```
+-----------------------------------------------------------------------------+
|                           DEMO-UI (Next.js 14)                               |
+-----------------------------------------------------------------------------+
|  Pages:                                                                      |
|  +-- /liveness (4 input modes: camera, upload, passive, active)             |
|  +-- /live-demo (real-time frame analysis)                                  |
|                                                                              |
|  Components:                                                                 |
|  +-- WebcamCapture (single-shot with oval guide)                            |
|  +-- ImageUploader (drag-drop file upload)                                  |
|  +-- LiveCameraStream (WebSocket streaming)                                 |
|  +-- ActiveLivenessChallenge (challenge UI with progress)                   |
|                                                                              |
|  Hooks:                                                                      |
|  +-- useLivenessCheck (REST mutation)                                       |
|  +-- useLiveCameraAnalysis (WebSocket management)                           |
|  +-- useWebSocket (generic with reconnection)                               |
+-----------------------------------------------------------------------------+
                                    |
        +---------------------------+---------------------------+
        |                                                       |
        v                                                       v
+-------------------+                               +------------------------+
| REST API          |                               | WebSocket API          |
| POST /liveness    |                               | WS /ws/live-analysis   |
+-------------------+                               +------------------------+
        |                                                       |
        v                                                       v
+-----------------------------------------------------------------------------+
|                      BIOMETRIC PROCESSOR (FastAPI)                           |
+-----------------------------------------------------------------------------+
|  Use Cases:                                                                  |
|  +-- CheckLivenessUseCase (orchestrates face detection + liveness)          |
|                                                                              |
|  Services:                                                                   |
|  +-- ActiveLivenessManager (session + challenge management)                 |
|                                                                              |
|  Detectors (Combined 40/60 Weighting):                                      |
|  +-- TextureLivenessDetector (40%)                                          |
|  |   +-- Laplacian variance (35%)                                           |
|  |   +-- HSV color analysis (25%)                                           |
|  |   +-- FFT frequency (25%)                                                |
|  |   +-- Moire/Gabor (15%)                                                  |
|  |                                                                           |
|  +-- ActiveLivenessDetector (60%)                                           |
|      +-- MediaPipe Face Mesh (468 landmarks)                                |
|      +-- EAR (Eye Aspect Ratio)                                             |
|      +-- MAR (Mouth Aspect Ratio)                                           |
|      +-- Head pose estimation                                               |
|                                                                              |
|  Domain Entities:                                                            |
|  +-- LivenessResult (immutable value object)                                |
|  +-- LivenessCheck (frozen dataclass)                                       |
+-----------------------------------------------------------------------------+
```

### Data Flow Diagram

```
                    +----------------+
                    |   User/Camera  |
                    +-------+--------+
                            |
                            v
+---------------------------+---------------------------+
|              Frontend Input Modes                      |
+--------------------------------------------------------+
|  [Camera]    [Upload]    [Passive WS]    [Active WS]  |
+----+------------+-------------+---------------+--------+
     |            |             |               |
     v            v             |               |
+----+------------+----+        |               |
| POST /api/v1/liveness|        |               |
| (single image)       |        |               |
+----------+-----------+        |               |
           |                    v               v
           |            +-------+---------------+-------+
           |            | WS /api/v1/ws/live-analysis   |
           |            | Config: {mode: 'liveness'|    |
           |            |         'active_liveness'}    |
           |            +---------------+---------------+
           |                            |
           v                            v
+----------+----------------------------+---------------+
|              CheckLivenessUseCase                      |
+--------------------------------------------------------+
|  1. Load image                                         |
|  2. Face detection (InsightFace)                       |
|  3. Crop face (40% padding)                            |
|  4. Liveness detection                                 |
+----------------------------+---------------------------+
                             |
              +--------------+--------------+
              |                             |
              v                             v
+-------------+-------------+  +------------+------------+
| TextureLivenessDetector   |  | ActiveLivenessDetector  |
| (40% weight)              |  | (60% weight)            |
+---------------------------+  +-------------------------+
| - Laplacian variance      |  | - MediaPipe landmarks   |
| - LBP texture (optimized) |  | - EAR calculation       |
| - HSV color naturalness   |  | - MAR calculation       |
| - FFT frequency analysis  |  | - Head pose estimation  |
| - Moire pattern detection |  | - Blink/smile detection |
+-------------+-------------+  +------------+------------+
              |                             |
              +-------------+---------------+
                            |
                            v
              +-------------+-------------+
              |  CombinedLivenessDetector |
              | (weighted score merge)    |
              +-------------+-------------+
                            |
                            v
              +-------------+-------------+
              |     LivenessResult        |
              | - is_live: boolean        |
              | - liveness_score: 0-100   |
              | - checks[]: individual    |
              | - spoof_type: classified  |
              +---------------------------+
```

---

## Milestone Status Analysis

### Milestone 1: Contracts & Scaffolding (90% Complete)

#### Completed Tasks

| Task | Status | File Location |
|------|--------|---------------|
| OpenAPI schema for liveness response | DONE | `app/api/schemas/liveness.py` |
| OpenAPI schema for live analysis | DONE | `app/api/schemas/live_analysis.py` |
| Active liveness schemas (7 challenge types) | DONE | `app/api/schemas/active_liveness.py` |
| Liveness feature folder in React | DONE | `demo-ui/src/app/(features)/liveness/` |
| Liveness route in React | DONE | `demo-ui/src/app/(features)/liveness/page.tsx` |
| Camera permission + preview | DONE | `demo-ui/src/components/media/webcam-capture.tsx` |
| Face positioning overlay guide | DONE | SVG oval in WebcamCapture component |
| Domain entities (LivenessResult) | DONE | `app/domain/entities/liveness_result.py` |
| Container/DI setup | DONE | `app/core/container.py` |

#### Missing Tasks

| Task | Priority | Impact |
|------|----------|--------|
| `POST /api/v1/liveness/generate-puzzle` endpoint | HIGH | Required for proper puzzle flow |
| `POST /api/v1/liveness/verify` endpoint | HIGH | Required for server verification |
| Puzzle request/response schemas | HIGH | Needed for above endpoints |

---

### Milestone 2: Puzzle Loop on Frontend (70% Complete)

#### Completed Tasks

| Task | Status | Implementation Notes |
|------|--------|----------------------|
| MediaPipe face landmarks | BACKEND | `active_liveness_detector.py` - 468 landmarks |
| EAR calculation | DONE | Threshold: 0.25 for eyes closed |
| MAR calculation | DONE | Threshold: 0.6 for smiling |
| Head pose metrics | PARTIAL | Turn detection at 0.15 threshold |
| Step pass logic | DONE | 7 challenge detectors implemented |
| UI: step list + timer | DONE | `active-liveness-challenge.tsx` |
| Challenge icons | DONE | Lucide icons for all types |
| Progress bar | DONE | Challenge completion circles |

#### Challenge Types Implemented

```typescript
enum ChallengeType {
  BLINK = "blink",           // Eye blink detection (EAR < 0.21)
  SMILE = "smile",           // Smile detection (MAR > 0.4)
  TURN_LEFT = "turn_left",   // Head turn left (threshold 0.15)
  TURN_RIGHT = "turn_right", // Head turn right (threshold 0.15)
  NOD = "nod",               // Head nod detection
  OPEN_MOUTH = "open_mouth", // Mouth open (MAR > 0.5)
  RAISE_EYEBROWS = "raise_eyebrows" // Eyebrow raise (threshold 0.08)
}
```

#### Missing Tasks

| Task | Priority | Notes |
|------|----------|-------|
| Client-side MediaPipe (Option A) | LOW | Currently using Option B (server-side) |
| Explicit FSM in frontend | MEDIUM | Using React hooks, not XState/custom FSM |
| Debounce logic for actions | LOW | Handled server-side |

---

### Milestone 3: Backend Verification + Storage (85% Complete)

#### Completed Tasks

| Component | Implementation | File |
|-----------|----------------|------|
| Texture analysis (Laplacian) | 35% weight | `texture_liveness_detector.py:85-95` |
| LBP score (scikit-image) | 5-10x faster | `enhanced_liveness_detector.py:115-135` |
| Color naturalness (HSV) | 25% weight | `texture_liveness_detector.py:97-115` |
| FFT frequency analysis | 25% weight | `texture_liveness_detector.py:117-143` |
| Moire detection (Gabor) | 15% weight | `texture_liveness_detector.py:145-175` |
| Active liveness manager | Full implementation | `active_liveness_manager.py` |
| Spoof type classification | 5 types | Returns specific attack type |
| Reason codes | Via checks[] | Individual pass/fail/score |

#### Spoof Types Detected

| Spoof Type | Detection Method |
|------------|------------------|
| `screen_replay` | High moire pattern score |
| `printed_photo` | Low texture variance |
| `digital_manipulation` | Unnatural color distribution |
| `static_image` | No movement detected |
| `suspected_spoof` | Low combined score |

#### Missing Tasks

| Task | Priority | Impact |
|------|----------|--------|
| Redis-backed puzzle store | HIGH | Session persistence across restarts |
| Puzzle TTL expiration | HIGH | Automatic cleanup of expired sessions |
| Anti-replay timestamp checks | MEDIUM | Prevent replay attacks |

---

### Milestone 4: Hardening (60% Complete)

#### Completed Tasks

| Task | Status | Implementation |
|------|--------|----------------|
| Multi-face detection | DONE | `MultipleFacesError` raised |
| Low light detection | BACKEND | Quality checks in live analysis |
| FPS display | DONE | Calculated from processing_time_ms |
| Camera error handling | DONE | Permissions, not found, in use |
| Stream cleanup | DONE | Proper unmount handling |

#### Missing Tasks

| Task | Priority | Implementation Needed |
|------|----------|----------------------|
| Tab visibility handling | MEDIUM | `visibilitychange` event listener |
| Camera pause detection | MEDIUM | Track ended event handlers |
| Rate limiting enforcement | MEDIUM | Redis-based rate limiter |
| Audit logging to Identity Core | LOW | Full trail integration |

---

### Milestone 5: Security & Metrics (40% Complete)

#### Completed Tasks

| Task | Status | Notes |
|------|--------|-------|
| Processing time logging | DONE | `processing_time_ms` in all responses |
| Failure reason distribution | DONE | Via `checks[]` and `spoof_type` |
| Configurable thresholds | DONE | Global settings in config |

#### Missing Tasks

| Task | Priority | Security Impact |
|------|----------|-----------------|
| Anti-replay checks | HIGH | Prevent recorded video attacks |
| Tenant policy flags | MEDIUM | Per-tenant liveness requirements |
| Session binding | MEDIUM | Tie puzzle to authenticated session |
| Challenge randomization audit | LOW | Ensure unpredictable sequences |

---

## Frontend-Backend Connection Map

### REST API Connection

```
+----------------------------------+
|  Frontend: useLivenessCheck()    |
|  File: use-liveness-check.ts     |
+----------------------------------+
              |
              | POST /api/v1/liveness
              | Content-Type: multipart/form-data
              | Body: { image: File | Blob }
              |
              v
+----------------------------------+
|  Backend: POST /liveness         |
|  File: app/api/routes/liveness.py|
+----------------------------------+
              |
              v
+----------------------------------+
|  Response:                       |
|  {                               |
|    is_live: boolean,             |
|    liveness_score: number,       |
|    challenge: string,            |
|    challenge_completed: boolean, |
|    checks: LivenessCheck[],      |
|    spoof_type: string | null,    |
|    processing_time_ms: number,   |
|    message: string               |
|  }                               |
+----------------------------------+
```

### WebSocket Connection

```
+----------------------------------------+
|  Frontend: useLiveCameraAnalysis()     |
|  File: use-live-camera-analysis.ts     |
+----------------------------------------+
              |
              | WS /api/v1/ws/live-analysis
              |
              v
+----------------------------------------+
|  Config Message:                       |
|  {                                     |
|    type: "config",                     |
|    mode: "liveness" | "active_liveness"|
|    user_id?: string,                   |
|    tenant_id?: string,                 |
|    quality_threshold?: number,         |
|    frame_skip?: number                 |
|  }                                     |
+----------------------------------------+
              |
              | Frame messages (continuous)
              | { type: "frame", data: base64 }
              |
              v
+----------------------------------------+
|  Backend: WS /ws/live-analysis         |
|  File: app/api/routes/live_analysis.py |
+----------------------------------------+
              |
              v
+----------------------------------------+
|  Response (per frame):                 |
|  {                                     |
|    type: "result",                     |
|    frame_number: number,               |
|    timestamp: number,                  |
|    processing_time_ms: number,         |
|    liveness?: {                        |
|      is_live, confidence, checks[]     |
|    },                                  |
|    active_liveness?: {                 |
|      current_challenge: string,        |
|      instruction: string,              |
|      feedback: string,                 |
|      time_remaining: number,           |
|      challenges_completed: number,     |
|      challenges_total: number,         |
|      action_detected: boolean,         |
|      action_confidence: number,        |
|      session_complete: boolean,        |
|      session_passed: boolean,          |
|      overall_score: number             |
|    }                                   |
|  }                                     |
+----------------------------------------+
```

---

## SE Checklist Compliance Analysis

### SOLID Principles Compliance

#### S - Single Responsibility Principle

| Component | Compliance | Analysis |
|-----------|------------|----------|
| `CheckLivenessUseCase` | PASS | Only orchestrates liveness flow |
| `TextureLivenessDetector` | PASS | Only texture-based detection |
| `ActiveLivenessDetector` | PASS | Only landmark-based detection |
| `CombinedLivenessDetector` | PASS | Only combines scores |
| `ActiveLivenessManager` | PARTIAL | Manages sessions AND detects actions - consider splitting |
| `LivenessResult` | PASS | Immutable data holder only |

**Recommendation:** Split `ActiveLivenessManager` into:
- `ActiveLivenessSessionManager` (session lifecycle)
- `ChallengeActionDetector` (action detection logic)

#### O - Open/Closed Principle

| Component | Compliance | Analysis |
|-----------|------------|----------|
| `ILivenessDetector` interface | PASS | New detectors can be added without modifying existing |
| Challenge types | PASS | Enum-based, new types addable |
| Spoof type detection | PARTIAL | Hard-coded logic in detectors |
| Score weighting | FAIL | Weights hard-coded in CombinedDetector |

**Recommendation:** Make score weights configurable:
```python
class CombinedLivenessDetector:
    def __init__(
        self,
        texture_weight: float = 0.4,  # Already configurable
        active_weight: float = 0.6,   # Already configurable
        # Add more granular weights
        texture_components: dict = None,  # New
    ):
        self.texture_components = texture_components or {
            "laplacian": 0.35,
            "color": 0.25,
            "frequency": 0.25,
            "moire": 0.15
        }
```

#### L - Liskov Substitution Principle

| Component | Compliance | Analysis |
|-----------|------------|----------|
| `ILivenessDetector` implementations | PASS | All return consistent `LivenessResult` |
| `IFaceDetector` implementations | PASS | Substitutable |
| Detector inheritance | N/A | Using composition over inheritance |

#### I - Interface Segregation Principle

| Component | Compliance | Analysis |
|-----------|------------|----------|
| `ILivenessDetector` | PASS | Single method: `check_liveness()` |
| `IFaceDetector` | PASS | Focused interface |
| WebSocket handlers | PARTIAL | Single handler for 10 modes |

**Recommendation:** Consider splitting WebSocket handler by mode:
```python
class LivenessWebSocketHandler:
    """Handles liveness mode only"""

class ActiveLivenessWebSocketHandler:
    """Handles active_liveness mode only"""
```

#### D - Dependency Inversion Principle

| Component | Compliance | Analysis |
|-----------|------------|----------|
| `CheckLivenessUseCase` | PASS | Depends on `ILivenessDetector`, `IFaceDetector` |
| Container DI | PASS | Factory functions with `@lru_cache` |
| ActiveLivenessManager | PARTIAL | Creates MediaPipe directly |

**Recommendation:** Inject MediaPipe face mesh:
```python
class ActiveLivenessManager:
    def __init__(
        self,
        face_mesh_factory: Callable[[], FaceMesh] = None
    ):
        self._face_mesh_factory = face_mesh_factory or self._default_factory
```

---

### DRY, KISS, YAGNI Compliance

#### DRY (Don't Repeat Yourself)

| Issue | Location | Severity |
|-------|----------|----------|
| EAR calculation duplicated | `ActiveLivenessDetector` + `ActiveLivenessManager` | MEDIUM |
| MAR calculation duplicated | Same as above | MEDIUM |
| Threshold constants scattered | Multiple detector files | LOW |

**Recommendation:** Extract to shared module:
```python
# app/domain/services/facial_metrics.py
class FacialMetricsCalculator:
    @staticmethod
    def calculate_ear(eye_landmarks: List) -> float:
        """Eye Aspect Ratio calculation"""

    @staticmethod
    def calculate_mar(mouth_landmarks: List) -> float:
        """Mouth Aspect Ratio calculation"""
```

#### KISS (Keep It Simple)

| Component | Compliance | Analysis |
|-----------|------------|----------|
| Liveness detection flow | PASS | Clear pipeline |
| WebSocket protocol | PASS | Simple message types |
| Challenge progression | PASS | Linear state flow |
| Score calculation | PARTIAL | Multiple weight layers |

#### YAGNI (You Aren't Gonna Need It)

| Feature | Compliance | Analysis |
|---------|------------|----------|
| 7 challenge types | OK | All potentially needed |
| 10 analysis modes | REVIEW | Some modes may not be used |
| Short clip submission | OK | Not implemented, not needed yet |

---

### Design Patterns Usage

| Pattern | Usage | Location | Compliance |
|---------|-------|----------|------------|
| **Factory** | Detector creation | `container.py` | GOOD |
| **Strategy** | Liveness detectors | `ILivenessDetector` | GOOD |
| **Singleton** | ML models | `@lru_cache` factories | GOOD |
| **Observer** | WebSocket events | `use-websocket.ts` | GOOD |
| **State** | Active liveness | `ActiveLivenessManager` | PARTIAL - no formal FSM |
| **Builder** | N/A | Not used | N/A |
| **Facade** | `CheckLivenessUseCase` | Simplifies detection | GOOD |

**Missing Pattern Recommendation:** Implement State pattern for challenge flow:
```python
class ChallengeState(ABC):
    @abstractmethod
    def process_frame(self, frame, context) -> 'ChallengeState': ...

class PendingState(ChallengeState): ...
class InProgressState(ChallengeState): ...
class CompletedState(ChallengeState): ...
class FailedState(ChallengeState): ...
```

---

### Anti-Patterns Check

| Anti-Pattern | Present? | Location | Severity |
|--------------|----------|----------|----------|
| **God Object** | NO | - | - |
| **Spaghetti Code** | NO | - | - |
| **Magic Numbers** | YES | Threshold values in detectors | LOW |
| **Dead Code** | MINOR | `StubLivenessDetector` (legacy) | LOW |
| **Shotgun Surgery** | NO | - | - |
| **Feature Envy** | NO | - | - |
| **Long Methods** | MINOR | Some detector methods | LOW |
| **Large Classes** | NO | - | - |
| **Big Ball of Mud** | NO | - | - |
| **Hard Coding** | YES | Some thresholds | MEDIUM |

**Recommendations:**
1. Move magic numbers to configuration:
```python
# app/core/config.py
class LivenessConfig:
    EAR_THRESHOLD: float = 0.25
    MAR_THRESHOLD: float = 0.6
    BLINK_THRESHOLD: float = 0.21
    HEAD_TURN_THRESHOLD: float = 0.15
    TEXTURE_LAPLACIAN_THRESHOLD: float = 100.0
```

2. Remove `StubLivenessDetector` or clearly mark as test-only

---

### Code Quality Assessment

| Criterion | Score | Notes |
|-----------|-------|-------|
| Meaningful names | 9/10 | Clear, descriptive naming |
| Small functions | 8/10 | Most under 30 lines |
| Self-documenting | 8/10 | Good docstrings |
| Consistent formatting | 9/10 | Black/Ruff enforced |
| Error handling | 8/10 | Custom exceptions used |
| Test coverage | 7/10 | Unit tests present, integration partial |

---

### Security Compliance

| Security Requirement | Status | Notes |
|---------------------|--------|-------|
| Input validation | PASS | Magic bytes validation, file type checks |
| Parameterized queries | N/A | No SQL |
| Authentication | PARTIAL | JWT headers supported, not enforced |
| Sensitive data encryption | N/A | No sensitive storage |
| Least privilege | PASS | Focused interfaces |
| Dependency updates | REVIEW | Check for CVEs |

**Security Gaps:**
1. No anti-replay protection
2. No rate limiting enforcement at endpoint level
3. No session binding for puzzles
4. WebSocket connections not authenticated

---

## Implementation Plans for Missing Features

### Plan 1: Puzzle Endpoints (`generate-puzzle`, `verify`)

#### 1.1 Schema Definitions

**File:** `app/api/schemas/puzzle.py` (NEW)

```python
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class PuzzleStep(BaseModel):
    """Single step in a liveness puzzle"""
    action: str  # ChallengeType value
    duration_seconds: float = Field(default=5.0, ge=2.0, le=30.0)
    order: int

class GeneratePuzzleRequest(BaseModel):
    """Request to generate a new liveness puzzle"""
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    difficulty: str = Field(default="standard", pattern="^(easy|standard|hard)$")
    min_steps: int = Field(default=3, ge=2, le=5)
    max_steps: int = Field(default=4, ge=3, le=7)

class GeneratePuzzleResponse(BaseModel):
    """Generated puzzle for liveness verification"""
    puzzle_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    steps: List[PuzzleStep]
    timeout_seconds: int = Field(default=60)
    expires_at: datetime
    thresholds: dict = Field(default_factory=lambda: {
        "ear_threshold": 0.21,
        "mar_threshold": 0.4,
        "head_turn_threshold": 0.15
    })

class StepEvidence(BaseModel):
    """Evidence for a completed step"""
    action: str
    start_timestamp: float
    end_timestamp: float
    confidence: float = Field(ge=0.0, le=1.0)
    metrics: dict  # e.g., {"min_ear": 0.15, "max_ear": 0.32}

class VerifyPuzzleRequest(BaseModel):
    """Request to verify puzzle completion"""
    puzzle_id: str
    results: List[StepEvidence]
    final_frame: Optional[str] = None  # Base64 encoded
    client_meta: dict = Field(default_factory=dict)

class VerifyPuzzleResponse(BaseModel):
    """Verification result"""
    success: bool
    liveness_confirmed: bool
    steps_completed: int
    total_steps: int
    completion_time_seconds: float
    reason_codes: List[str] = Field(default_factory=list)
    overall_score: float = Field(ge=0.0, le=100.0)
```

#### 1.2 Domain Entity

**File:** `app/domain/entities/puzzle.py` (NEW)

```python
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from enum import Enum
import uuid

class PuzzleDifficulty(Enum):
    EASY = "easy"      # 2 steps, longer duration
    STANDARD = "standard"  # 3-4 steps
    HARD = "hard"      # 5+ steps, shorter duration

@dataclass(frozen=True)
class PuzzleStep:
    """Immutable puzzle step"""
    action: str
    duration_seconds: float
    order: int

@dataclass
class Puzzle:
    """Liveness puzzle aggregate"""
    puzzle_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    steps: Tuple[PuzzleStep, ...] = field(default_factory=tuple)
    difficulty: PuzzleDifficulty = PuzzleDifficulty.STANDARD
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime = field(default=None)
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    completed: bool = False

    def __post_init__(self):
        if self.expires_at is None:
            self.expires_at = self.created_at + timedelta(minutes=5)

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def validate_steps(self, submitted: List[dict]) -> Tuple[bool, List[str]]:
        """Validate submitted steps match puzzle"""
        reasons = []
        if len(submitted) != len(self.steps):
            reasons.append("STEP_COUNT_MISMATCH")
            return False, reasons

        for i, (expected, actual) in enumerate(zip(self.steps, submitted)):
            if expected.action != actual.get("action"):
                reasons.append(f"STEP_{i}_ACTION_MISMATCH")

        return len(reasons) == 0, reasons
```

#### 1.3 Repository Interface

**File:** `app/domain/repositories/puzzle_repository.py` (NEW)

```python
from abc import ABC, abstractmethod
from typing import Optional
from app.domain.entities.puzzle import Puzzle

class IPuzzleRepository(ABC):
    """Repository interface for puzzle persistence"""

    @abstractmethod
    async def save(self, puzzle: Puzzle) -> None:
        """Save puzzle with TTL"""
        pass

    @abstractmethod
    async def get(self, puzzle_id: str) -> Optional[Puzzle]:
        """Get puzzle by ID"""
        pass

    @abstractmethod
    async def delete(self, puzzle_id: str) -> bool:
        """Delete puzzle"""
        pass

    @abstractmethod
    async def exists(self, puzzle_id: str) -> bool:
        """Check if puzzle exists"""
        pass
```

#### 1.4 Redis Repository Implementation

**File:** `app/infrastructure/persistence/repositories/redis_puzzle_repository.py` (NEW)

```python
import json
from typing import Optional
from datetime import datetime
import redis.asyncio as redis
from app.domain.entities.puzzle import Puzzle, PuzzleStep, PuzzleDifficulty
from app.domain.repositories.puzzle_repository import IPuzzleRepository

class RedisPuzzleRepository(IPuzzleRepository):
    """Redis-backed puzzle storage with TTL"""

    PUZZLE_PREFIX = "liveness:puzzle:"
    DEFAULT_TTL = 300  # 5 minutes

    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    def _key(self, puzzle_id: str) -> str:
        return f"{self.PUZZLE_PREFIX}{puzzle_id}"

    def _serialize(self, puzzle: Puzzle) -> str:
        return json.dumps({
            "puzzle_id": puzzle.puzzle_id,
            "steps": [
                {"action": s.action, "duration_seconds": s.duration_seconds, "order": s.order}
                for s in puzzle.steps
            ],
            "difficulty": puzzle.difficulty.value,
            "created_at": puzzle.created_at.isoformat(),
            "expires_at": puzzle.expires_at.isoformat(),
            "tenant_id": puzzle.tenant_id,
            "user_id": puzzle.user_id,
            "completed": puzzle.completed
        })

    def _deserialize(self, data: str) -> Puzzle:
        obj = json.loads(data)
        return Puzzle(
            puzzle_id=obj["puzzle_id"],
            steps=tuple(
                PuzzleStep(s["action"], s["duration_seconds"], s["order"])
                for s in obj["steps"]
            ),
            difficulty=PuzzleDifficulty(obj["difficulty"]),
            created_at=datetime.fromisoformat(obj["created_at"]),
            expires_at=datetime.fromisoformat(obj["expires_at"]),
            tenant_id=obj.get("tenant_id"),
            user_id=obj.get("user_id"),
            completed=obj.get("completed", False)
        )

    async def save(self, puzzle: Puzzle) -> None:
        ttl = int((puzzle.expires_at - datetime.utcnow()).total_seconds())
        ttl = max(ttl, 60)  # Minimum 60 seconds
        await self._redis.setex(
            self._key(puzzle.puzzle_id),
            ttl,
            self._serialize(puzzle)
        )

    async def get(self, puzzle_id: str) -> Optional[Puzzle]:
        data = await self._redis.get(self._key(puzzle_id))
        if data is None:
            return None
        return self._deserialize(data)

    async def delete(self, puzzle_id: str) -> bool:
        result = await self._redis.delete(self._key(puzzle_id))
        return result > 0

    async def exists(self, puzzle_id: str) -> bool:
        return await self._redis.exists(self._key(puzzle_id)) > 0
```

#### 1.5 Use Cases

**File:** `app/application/use_cases/generate_puzzle.py` (NEW)

```python
import random
from datetime import datetime, timedelta
from typing import List
from app.domain.entities.puzzle import Puzzle, PuzzleStep, PuzzleDifficulty
from app.domain.repositories.puzzle_repository import IPuzzleRepository
from app.api.schemas.active_liveness import ChallengeType

class GeneratePuzzleUseCase:
    """Generate a new liveness puzzle"""

    # Actions that shouldn't follow each other
    INCOMPATIBLE_SEQUENCES = [
        (ChallengeType.TURN_LEFT, ChallengeType.TURN_RIGHT),
        (ChallengeType.TURN_RIGHT, ChallengeType.TURN_LEFT),
    ]

    DIFFICULTY_CONFIG = {
        PuzzleDifficulty.EASY: {"steps": (2, 3), "duration": 7.0},
        PuzzleDifficulty.STANDARD: {"steps": (3, 4), "duration": 5.0},
        PuzzleDifficulty.HARD: {"steps": (4, 5), "duration": 4.0},
    }

    def __init__(self, puzzle_repository: IPuzzleRepository):
        self._repository = puzzle_repository

    def _generate_steps(
        self,
        difficulty: PuzzleDifficulty,
        min_steps: int,
        max_steps: int
    ) -> List[PuzzleStep]:
        config = self.DIFFICULTY_CONFIG[difficulty]
        num_steps = random.randint(
            max(min_steps, config["steps"][0]),
            min(max_steps, config["steps"][1])
        )

        available = list(ChallengeType)
        steps = []

        for i in range(num_steps):
            # Filter incompatible actions
            valid = [a for a in available if not self._is_incompatible(steps, a)]
            if not valid:
                valid = available

            action = random.choice(valid)
            steps.append(PuzzleStep(
                action=action.value,
                duration_seconds=config["duration"],
                order=i
            ))

        return steps

    def _is_incompatible(self, steps: List[PuzzleStep], action: ChallengeType) -> bool:
        if not steps:
            return False
        last_action = ChallengeType(steps[-1].action)
        return (last_action, action) in self.INCOMPATIBLE_SEQUENCES

    async def execute(
        self,
        tenant_id: str = None,
        user_id: str = None,
        difficulty: str = "standard",
        min_steps: int = 3,
        max_steps: int = 4,
        timeout_seconds: int = 60
    ) -> Puzzle:
        diff = PuzzleDifficulty(difficulty)
        steps = self._generate_steps(diff, min_steps, max_steps)

        puzzle = Puzzle(
            steps=tuple(steps),
            difficulty=diff,
            expires_at=datetime.utcnow() + timedelta(seconds=timeout_seconds + 60),
            tenant_id=tenant_id,
            user_id=user_id
        )

        await self._repository.save(puzzle)
        return puzzle
```

**File:** `app/application/use_cases/verify_puzzle.py` (NEW)

```python
from dataclasses import dataclass
from typing import List, Optional
from app.domain.entities.puzzle import Puzzle
from app.domain.repositories.puzzle_repository import IPuzzleRepository

@dataclass
class VerificationResult:
    success: bool
    liveness_confirmed: bool
    steps_completed: int
    total_steps: int
    completion_time_seconds: float
    reason_codes: List[str]
    overall_score: float

class VerifyPuzzleUseCase:
    """Verify puzzle completion"""

    MIN_CONFIDENCE = 0.6

    def __init__(self, puzzle_repository: IPuzzleRepository):
        self._repository = puzzle_repository

    async def execute(
        self,
        puzzle_id: str,
        results: List[dict],
        final_frame: Optional[str] = None,
        client_meta: dict = None
    ) -> VerificationResult:
        reason_codes = []

        # Get puzzle
        puzzle = await self._repository.get(puzzle_id)
        if puzzle is None:
            return VerificationResult(
                success=False,
                liveness_confirmed=False,
                steps_completed=0,
                total_steps=0,
                completion_time_seconds=0,
                reason_codes=["PUZZLE_NOT_FOUND"],
                overall_score=0.0
            )

        # Check expiration
        if puzzle.is_expired():
            reason_codes.append("PUZZLE_EXPIRED")
            return VerificationResult(
                success=False,
                liveness_confirmed=False,
                steps_completed=0,
                total_steps=len(puzzle.steps),
                completion_time_seconds=0,
                reason_codes=reason_codes,
                overall_score=0.0
            )

        # Check already completed
        if puzzle.completed:
            reason_codes.append("PUZZLE_ALREADY_COMPLETED")

        # Validate steps match
        valid, step_reasons = puzzle.validate_steps(results)
        reason_codes.extend(step_reasons)

        # Calculate score
        total_confidence = 0.0
        steps_passed = 0
        timestamps = []

        for i, result in enumerate(results):
            confidence = result.get("confidence", 0)
            total_confidence += confidence
            if confidence >= self.MIN_CONFIDENCE:
                steps_passed += 1
            else:
                reason_codes.append(f"STEP_{i}_LOW_CONFIDENCE")

            timestamps.append((result.get("start_timestamp", 0), result.get("end_timestamp", 0)))

        # Check timestamp monotonicity (anti-replay)
        for i in range(1, len(timestamps)):
            if timestamps[i][0] < timestamps[i-1][1]:
                reason_codes.append("TIMESTAMP_NOT_MONOTONIC")
                break

        # Calculate completion time
        if timestamps:
            completion_time = timestamps[-1][1] - timestamps[0][0]
        else:
            completion_time = 0

        # Overall score
        overall_score = (total_confidence / len(results) * 100) if results else 0
        liveness_confirmed = steps_passed == len(puzzle.steps) and len(reason_codes) == 0

        # Mark completed
        if liveness_confirmed:
            puzzle.completed = True
            await self._repository.save(puzzle)

        return VerificationResult(
            success=len(reason_codes) == 0,
            liveness_confirmed=liveness_confirmed,
            steps_completed=steps_passed,
            total_steps=len(puzzle.steps),
            completion_time_seconds=completion_time,
            reason_codes=reason_codes,
            overall_score=overall_score
        )
```

#### 1.6 API Endpoints

**File:** `app/api/routes/puzzle.py` (NEW)

```python
from fastapi import APIRouter, Depends, HTTPException
from app.api.schemas.puzzle import (
    GeneratePuzzleRequest,
    GeneratePuzzleResponse,
    VerifyPuzzleRequest,
    VerifyPuzzleResponse,
    PuzzleStep
)
from app.application.use_cases.generate_puzzle import GeneratePuzzleUseCase
from app.application.use_cases.verify_puzzle import VerifyPuzzleUseCase
from app.core.container import get_puzzle_repository

router = APIRouter(prefix="/liveness", tags=["Liveness Puzzle"])

@router.post("/generate-puzzle", response_model=GeneratePuzzleResponse)
async def generate_puzzle(
    request: GeneratePuzzleRequest,
    use_case: GeneratePuzzleUseCase = Depends(lambda: GeneratePuzzleUseCase(get_puzzle_repository()))
):
    """Generate a new liveness puzzle"""
    puzzle = await use_case.execute(
        tenant_id=request.tenant_id,
        user_id=request.user_id,
        difficulty=request.difficulty,
        min_steps=request.min_steps,
        max_steps=request.max_steps
    )

    return GeneratePuzzleResponse(
        puzzle_id=puzzle.puzzle_id,
        steps=[
            PuzzleStep(action=s.action, duration_seconds=s.duration_seconds, order=s.order)
            for s in puzzle.steps
        ],
        timeout_seconds=60,
        expires_at=puzzle.expires_at
    )

@router.post("/verify", response_model=VerifyPuzzleResponse)
async def verify_puzzle(
    request: VerifyPuzzleRequest,
    use_case: VerifyPuzzleUseCase = Depends(lambda: VerifyPuzzleUseCase(get_puzzle_repository()))
):
    """Verify puzzle completion"""
    result = await use_case.execute(
        puzzle_id=request.puzzle_id,
        results=[r.dict() for r in request.results],
        final_frame=request.final_frame,
        client_meta=request.client_meta
    )

    return VerifyPuzzleResponse(
        success=result.success,
        liveness_confirmed=result.liveness_confirmed,
        steps_completed=result.steps_completed,
        total_steps=result.total_steps,
        completion_time_seconds=result.completion_time_seconds,
        reason_codes=result.reason_codes,
        overall_score=result.overall_score
    )
```

---

### Plan 2: Frontend State Machine

#### 2.1 State Machine Definition

**File:** `demo-ui/src/lib/liveness/state-machine.ts` (NEW)

```typescript
export type LivenessState =
  | 'IDLE'
  | 'PERMISSION_REQUESTED'
  | 'PERMISSION_DENIED'
  | 'CAMERA_READY'
  | 'PUZZLE_LOADING'
  | 'STEP_RUNNING'
  | 'STEP_PASSED'
  | 'STEP_FAILED'
  | 'VERIFYING_BACKEND'
  | 'SUCCESS'
  | 'FAILED'
  | 'TIMEOUT';

export type LivenessEvent =
  | { type: 'REQUEST_PERMISSION' }
  | { type: 'PERMISSION_GRANTED' }
  | { type: 'PERMISSION_DENIED'; reason: string }
  | { type: 'CAMERA_READY' }
  | { type: 'CAMERA_ERROR'; error: string }
  | { type: 'LOAD_PUZZLE' }
  | { type: 'PUZZLE_LOADED'; puzzle: Puzzle }
  | { type: 'START_STEP'; stepIndex: number }
  | { type: 'ACTION_DETECTED'; confidence: number }
  | { type: 'STEP_COMPLETE' }
  | { type: 'STEP_TIMEOUT' }
  | { type: 'VERIFY' }
  | { type: 'VERIFICATION_SUCCESS' }
  | { type: 'VERIFICATION_FAILED'; reasons: string[] }
  | { type: 'RESET' };

export interface LivenessContext {
  puzzle: Puzzle | null;
  currentStepIndex: number;
  stepResults: StepResult[];
  error: string | null;
  startTime: number | null;
}

export interface Puzzle {
  puzzle_id: string;
  steps: PuzzleStep[];
  timeout_seconds: number;
  expires_at: string;
}

export interface PuzzleStep {
  action: string;
  duration_seconds: number;
  order: number;
}

export interface StepResult {
  action: string;
  start_timestamp: number;
  end_timestamp: number;
  confidence: number;
  metrics: Record<string, number>;
}

// State transition function
export function livenessMachine(
  state: LivenessState,
  event: LivenessEvent,
  context: LivenessContext
): { state: LivenessState; context: LivenessContext } {
  switch (state) {
    case 'IDLE':
      if (event.type === 'REQUEST_PERMISSION') {
        return { state: 'PERMISSION_REQUESTED', context };
      }
      break;

    case 'PERMISSION_REQUESTED':
      if (event.type === 'PERMISSION_GRANTED') {
        return { state: 'CAMERA_READY', context };
      }
      if (event.type === 'PERMISSION_DENIED') {
        return {
          state: 'PERMISSION_DENIED',
          context: { ...context, error: event.reason }
        };
      }
      break;

    case 'CAMERA_READY':
      if (event.type === 'LOAD_PUZZLE') {
        return { state: 'PUZZLE_LOADING', context };
      }
      break;

    case 'PUZZLE_LOADING':
      if (event.type === 'PUZZLE_LOADED') {
        return {
          state: 'STEP_RUNNING',
          context: {
            ...context,
            puzzle: event.puzzle,
            currentStepIndex: 0,
            startTime: Date.now()
          }
        };
      }
      break;

    case 'STEP_RUNNING':
      if (event.type === 'STEP_COMPLETE') {
        const nextIndex = context.currentStepIndex + 1;
        if (nextIndex >= (context.puzzle?.steps.length ?? 0)) {
          return { state: 'VERIFYING_BACKEND', context };
        }
        return {
          state: 'STEP_RUNNING',
          context: { ...context, currentStepIndex: nextIndex }
        };
      }
      if (event.type === 'STEP_TIMEOUT') {
        return { state: 'STEP_FAILED', context };
      }
      break;

    case 'STEP_FAILED':
      // Allow retry or fail completely
      if (event.type === 'RESET') {
        return {
          state: 'IDLE',
          context: {
            puzzle: null,
            currentStepIndex: 0,
            stepResults: [],
            error: null,
            startTime: null
          }
        };
      }
      break;

    case 'VERIFYING_BACKEND':
      if (event.type === 'VERIFICATION_SUCCESS') {
        return { state: 'SUCCESS', context };
      }
      if (event.type === 'VERIFICATION_FAILED') {
        return {
          state: 'FAILED',
          context: { ...context, error: event.reasons.join(', ') }
        };
      }
      break;

    case 'SUCCESS':
    case 'FAILED':
      if (event.type === 'RESET') {
        return {
          state: 'IDLE',
          context: {
            puzzle: null,
            currentStepIndex: 0,
            stepResults: [],
            error: null,
            startTime: null
          }
        };
      }
      break;
  }

  // No transition
  return { state, context };
}
```

#### 2.2 React Hook for State Machine

**File:** `demo-ui/src/hooks/use-liveness-machine.ts` (NEW)

```typescript
import { useReducer, useCallback } from 'react';
import {
  LivenessState,
  LivenessEvent,
  LivenessContext,
  livenessMachine,
  Puzzle
} from '@/lib/liveness/state-machine';

const initialContext: LivenessContext = {
  puzzle: null,
  currentStepIndex: 0,
  stepResults: [],
  error: null,
  startTime: null
};

interface MachineState {
  state: LivenessState;
  context: LivenessContext;
}

function reducer(current: MachineState, event: LivenessEvent): MachineState {
  return livenessMachine(current.state, event, current.context);
}

export function useLivenessMachine() {
  const [machine, dispatch] = useReducer(reducer, {
    state: 'IDLE',
    context: initialContext
  });

  const send = useCallback((event: LivenessEvent) => {
    dispatch(event);
  }, []);

  const requestPermission = useCallback(() => {
    send({ type: 'REQUEST_PERMISSION' });
  }, [send]);

  const grantPermission = useCallback(() => {
    send({ type: 'PERMISSION_GRANTED' });
  }, [send]);

  const denyPermission = useCallback((reason: string) => {
    send({ type: 'PERMISSION_DENIED', reason });
  }, [send]);

  const loadPuzzle = useCallback(() => {
    send({ type: 'LOAD_PUZZLE' });
  }, [send]);

  const setPuzzleLoaded = useCallback((puzzle: Puzzle) => {
    send({ type: 'PUZZLE_LOADED', puzzle });
  }, [send]);

  const completeStep = useCallback(() => {
    send({ type: 'STEP_COMPLETE' });
  }, [send]);

  const timeoutStep = useCallback(() => {
    send({ type: 'STEP_TIMEOUT' });
  }, [send]);

  const verifySuccess = useCallback(() => {
    send({ type: 'VERIFICATION_SUCCESS' });
  }, [send]);

  const verifyFailed = useCallback((reasons: string[]) => {
    send({ type: 'VERIFICATION_FAILED', reasons });
  }, [send]);

  const reset = useCallback(() => {
    send({ type: 'RESET' });
  }, [send]);

  return {
    state: machine.state,
    context: machine.context,
    currentStep: machine.context.puzzle?.steps[machine.context.currentStepIndex],
    isIdle: machine.state === 'IDLE',
    isRunning: machine.state === 'STEP_RUNNING',
    isSuccess: machine.state === 'SUCCESS',
    isFailed: machine.state === 'FAILED' || machine.state === 'STEP_FAILED',
    isLoading: machine.state === 'PUZZLE_LOADING' || machine.state === 'VERIFYING_BACKEND',
    actions: {
      requestPermission,
      grantPermission,
      denyPermission,
      loadPuzzle,
      setPuzzleLoaded,
      completeStep,
      timeoutStep,
      verifySuccess,
      verifyFailed,
      reset
    }
  };
}
```

---

### Plan 3: Anti-Replay Protection

#### 3.1 Timestamp Validation

**File:** `app/domain/services/anti_replay.py` (NEW)

```python
from dataclasses import dataclass
from typing import List, Tuple
import hashlib
import hmac
from datetime import datetime

@dataclass
class TimestampValidation:
    valid: bool
    reason: str = ""

class AntiReplayValidator:
    """Validates timestamps and frame sequences to prevent replay attacks"""

    MAX_CLOCK_SKEW_SECONDS = 5.0
    MIN_STEP_DURATION_SECONDS = 0.5

    def __init__(self, secret_key: str):
        self._secret = secret_key.encode()

    def validate_timestamps(
        self,
        results: List[dict],
        puzzle_created_at: datetime
    ) -> TimestampValidation:
        """Validate timestamp sequence"""
        if not results:
            return TimestampValidation(False, "NO_TIMESTAMPS")

        puzzle_ts = puzzle_created_at.timestamp()

        # Check first timestamp is after puzzle creation
        first_start = results[0].get("start_timestamp", 0)
        if first_start < puzzle_ts - self.MAX_CLOCK_SKEW_SECONDS:
            return TimestampValidation(False, "TIMESTAMP_BEFORE_PUZZLE")

        # Check monotonicity
        for i in range(len(results)):
            start = results[i].get("start_timestamp", 0)
            end = results[i].get("end_timestamp", 0)

            # End must be after start
            if end <= start:
                return TimestampValidation(False, f"STEP_{i}_END_BEFORE_START")

            # Minimum duration check
            if end - start < self.MIN_STEP_DURATION_SECONDS:
                return TimestampValidation(False, f"STEP_{i}_TOO_SHORT")

            # Next step must start after previous ends
            if i > 0:
                prev_end = results[i-1].get("end_timestamp", 0)
                if start < prev_end:
                    return TimestampValidation(False, "TIMESTAMPS_OVERLAP")

        return TimestampValidation(True)

    def generate_challenge_token(self, puzzle_id: str, step_index: int) -> str:
        """Generate HMAC token for challenge verification"""
        message = f"{puzzle_id}:{step_index}:{datetime.utcnow().isoformat()}"
        return hmac.new(self._secret, message.encode(), hashlib.sha256).hexdigest()[:16]

    def validate_frame_hash(
        self,
        frame_data: bytes,
        expected_hash: str
    ) -> bool:
        """Validate frame hasn't been tampered with"""
        actual_hash = hashlib.sha256(frame_data).hexdigest()[:16]
        return hmac.compare_digest(actual_hash, expected_hash)
```

---

### Plan 4: Tab Visibility Handling (Frontend)

**File:** `demo-ui/src/hooks/use-visibility.ts` (NEW)

```typescript
import { useEffect, useCallback, useRef } from 'react';

interface VisibilityOptions {
  onVisible?: () => void;
  onHidden?: () => void;
  pauseOnHidden?: boolean;
}

export function useVisibility(options: VisibilityOptions = {}) {
  const { onVisible, onHidden, pauseOnHidden = true } = options;
  const hiddenTimeRef = useRef<number | null>(null);

  const handleVisibilityChange = useCallback(() => {
    if (document.hidden) {
      hiddenTimeRef.current = Date.now();
      onHidden?.();
    } else {
      const hiddenDuration = hiddenTimeRef.current
        ? Date.now() - hiddenTimeRef.current
        : 0;
      hiddenTimeRef.current = null;
      onVisible?.();
    }
  }, [onVisible, onHidden]);

  useEffect(() => {
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [handleVisibilityChange]);

  return {
    isVisible: !document.hidden,
    wasHidden: hiddenTimeRef.current !== null
  };
}
```

**Integration in LiveCameraStream:**

```typescript
// In LiveCameraStream component
import { useVisibility } from '@/hooks/use-visibility';

function LiveCameraStream({ mode, onResult }) {
  const { sendFrame, pause, resume } = useLiveCameraAnalysis();

  useVisibility({
    onHidden: () => {
      pause();
      // Optionally notify backend
    },
    onVisible: () => {
      resume();
    }
  });

  // ... rest of component
}
```

---

## Recommended Action Items

### High Priority (Week 1-2)

1. **Implement puzzle endpoints** (`generate-puzzle`, `verify`)
   - Create schemas, entities, repositories, use cases, routes
   - Add Redis repository for session persistence
   - Follow implementation plan in Section 6.1

2. **Add anti-replay validation**
   - Implement timestamp monotonicity checks
   - Add challenge tokens
   - Follow implementation plan in Section 6.3

3. **Fix DRY violations**
   - Extract EAR/MAR calculations to shared module
   - Centralize threshold constants

### Medium Priority (Week 3-4)

4. **Implement frontend state machine**
   - Add state machine implementation
   - Replace ad-hoc state management
   - Follow implementation plan in Section 6.2

5. **Add tab visibility handling**
   - Implement visibility hook
   - Pause/resume liveness on tab switch
   - Follow implementation plan in Section 6.4

6. **Split ActiveLivenessManager**
   - Separate session management from action detection
   - Improve Single Responsibility compliance

### Lower Priority (Week 5+)

7. **Add tenant policy configuration**
   - Create policy entity
   - Add per-tenant liveness settings
   - Integrate with Identity Core

8. **Improve test coverage**
   - Add integration tests for puzzle flow
   - Add WebSocket endpoint tests
   - Test anti-replay protection

9. **Remove deprecated code**
   - Delete `StubLivenessDetector`
   - Clean up any dead code

---

## Appendix: File Structure for New Components

```
app/
├── api/
│   ├── routes/
│   │   └── puzzle.py          # NEW: Puzzle endpoints
│   └── schemas/
│       └── puzzle.py          # NEW: Puzzle request/response
├── application/
│   └── use_cases/
│       ├── generate_puzzle.py # NEW: Generate puzzle use case
│       └── verify_puzzle.py   # NEW: Verify puzzle use case
├── domain/
│   ├── entities/
│   │   └── puzzle.py          # NEW: Puzzle aggregate
│   ├── repositories/
│   │   └── puzzle_repository.py # NEW: Repository interface
│   └── services/
│       ├── facial_metrics.py  # NEW: Shared EAR/MAR calculator
│       └── anti_replay.py     # NEW: Anti-replay validator
└── infrastructure/
    └── persistence/
        └── repositories/
            └── redis_puzzle_repository.py # NEW: Redis implementation

demo-ui/src/
├── hooks/
│   ├── use-liveness-machine.ts # NEW: State machine hook
│   └── use-visibility.ts       # NEW: Tab visibility hook
└── lib/
    └── liveness/
        └── state-machine.ts    # NEW: FSM definition
```

---

*Document generated: 2024-12-28*
*System Readiness: 70%*
*Next Review: After Milestone 1 gaps are addressed*
