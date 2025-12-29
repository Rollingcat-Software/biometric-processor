# Biometric Processor - Professional Implementation Plan V2.0

**Created**: 2025-11-17
**Status**: ✅ READY FOR IMPLEMENTATION
**Estimated Duration**: 8 weeks
**Team Size**: 1-2 developers

---

## 🎯 Overview

This plan implements a **professional, SOLID-compliant, testable architecture** for the Biometric Processor module.

### Key Improvements Over Original Plan
- ✅ Proper layered architecture (Clean Architecture)
- ✅ SOLID principles compliance
- ✅ Design patterns (Repository, Factory, Strategy, DI, etc.)
- ✅ Comprehensive testing strategy
- ✅ Production-ready error handling and logging
- ✅ Security best practices

---

## 📅 Sprint Overview

| Sprint | Duration | Focus | Status |
|--------|----------|-------|--------|
| **Sprint 1** | Week 1-2 | Foundation & Architecture | ⏸️ Not Started |
| **Sprint 2** | Week 3 | Testing & Quality | ⏸️ Not Started |
| **Sprint 3** | Week 4-5 | Liveness Detection | ⏸️ Not Started |
| **Sprint 4** | Week 6 | Database Integration | ⏸️ Not Started |
| **Sprint 5** | Week 7-8 | Production Readiness | ⏸️ Not Started |

**MVP Delivery**: End of Sprint 3 (Week 5)
**Production Ready**: End of Sprint 5 (Week 8)

---

## 🏗️ Sprint 1: Foundation & Architecture (Week 1-2)

### Objectives
- ✅ Establish clean architecture
- ✅ Implement dependency injection
- ✅ Fix critical security issues
- ✅ Enable testability

### Day 1-2: Domain Layer

**Create domain interfaces** (`app/domain/interfaces/`):

```python
# app/domain/interfaces/face_detector.py
from typing import Protocol
import numpy as np

class IFaceDetector(Protocol):
    async def detect(self, image: np.ndarray) -> FaceDetectionResult:
        """Detect faces in image"""
        ...

# app/domain/interfaces/embedding_extractor.py
class IEmbeddingExtractor(Protocol):
    async def extract(self, face_image: np.ndarray) -> np.ndarray:
        """Extract face embedding"""
        ...

# app/domain/interfaces/quality_assessor.py
class IQualityAssessor(Protocol):
    async def assess(self, face_image: np.ndarray) -> QualityAssessment:
        """Assess image quality"""
        ...

# app/domain/interfaces/similarity_calculator.py
class ISimilarityCalculator(Protocol):
    def calculate(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Calculate similarity distance"""
        ...

# app/domain/interfaces/embedding_repository.py
class IEmbeddingRepository(Protocol):
    async def save(self, user_id: str, embedding: np.ndarray) -> None: ...
    async def find_by_user_id(self, user_id: str) -> Optional[np.ndarray]: ...

# app/domain/interfaces/file_storage.py
class IFileStorage(Protocol):
    async def save_temp(self, file: UploadFile) -> str: ...
    async def cleanup(self, file_path: str) -> None: ...
```

**Create domain entities** (`app/domain/entities/`):

```python
# app/domain/entities/face_embedding.py
from dataclasses import dataclass
import numpy as np

@dataclass
class FaceEmbedding:
    user_id: str
    vector: np.ndarray
    quality_score: float
    created_at: datetime

# app/domain/entities/face_detection.py
@dataclass
class FaceDetectionResult:
    found: bool
    bounding_box: Optional[Tuple[int, int, int, int]]
    landmarks: Optional[np.ndarray]
    confidence: float

# app/domain/entities/quality_assessment.py
@dataclass
class QualityAssessment:
    score: float  # 0-100
    blur_score: float
    lighting_score: float
    face_size: int
    is_acceptable: bool
```

**Create domain exceptions** (`app/domain/exceptions/`):

```python
# app/domain/exceptions/base.py
class BiometricProcessorError(Exception):
    def __init__(self, message: str, error_code: str):
        self.message = message
        self.error_code = error_code
        super().__init__(message)

# app/domain/exceptions/face_errors.py
class FaceNotDetectedError(BiometricProcessorError):
    def __init__(self):
        super().__init__(
            message="No face detected in image",
            error_code="FACE_NOT_DETECTED"
        )

class MultipleFacesError(BiometricProcessorError):
    def __init__(self, count: int):
        super().__init__(
            message=f"Multiple faces detected ({count})",
            error_code="MULTIPLE_FACES"
        )

class PoorImageQualityError(BiometricProcessorError):
    def __init__(self, quality_score: float):
        super().__init__(
            message=f"Image quality too low ({quality_score:.0f}/100)",
            error_code="POOR_IMAGE_QUALITY"
        )

class EmbeddingNotFoundError(BiometricProcessorError):
    def __init__(self, user_id: str):
        super().__init__(
            message=f"No embedding found for user {user_id}",
            error_code="EMBEDDING_NOT_FOUND"
        )
```

**Checklist**:
- [ ] Create `app/domain/interfaces/` with all protocol files
- [ ] Create `app/domain/entities/` with all entity files
- [ ] Create `app/domain/exceptions/` with exception hierarchy
- [ ] Add type hints everywhere
- [ ] Write docstrings

**Files Created**: ~15 files
**Estimated Time**: 2 days

---

### Day 3-5: Infrastructure Layer

**Refactor existing ML code into clean implementations**:

```python
# app/infrastructure/ml/detectors/mtcnn_detector.py
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.exceptions.face_errors import FaceNotDetectedError, MultipleFacesError

class MTCNNDetector:
    """MTCNN-based face detector"""

    def __init__(self):
        # Initialize MTCNN model
        self._detector = MTCNN()

    async def detect(self, image: np.ndarray) -> FaceDetectionResult:
        faces = self._detector.detect_faces(image)

        if len(faces) == 0:
            raise FaceNotDetectedError()

        if len(faces) > 1:
            raise MultipleFacesError(count=len(faces))

        face = faces[0]
        return FaceDetectionResult(
            found=True,
            bounding_box=face['box'],
            landmarks=face.get('keypoints'),
            confidence=face['confidence']
        )

# app/infrastructure/ml/extractors/deepface_extractor.py
class DeepFaceExtractor:
    """DeepFace-based embedding extractor"""

    def __init__(self, model_name: str = "Facenet"):
        self._model_name = model_name
        self._model = DeepFace.build_model(model_name)

    async def extract(self, face_image: np.ndarray) -> np.ndarray:
        embedding = DeepFace.represent(
            img_path=face_image,
            model_name=self._model_name,
            enforce_detection=False
        )[0]['embedding']

        return np.array(embedding)

# app/infrastructure/ml/quality/quality_assessor.py
class QualityAssessor:
    """Assesses face image quality"""

    def __init__(
        self,
        blur_threshold: float = 100.0,
        min_face_size: int = 80
    ):
        self._blur_threshold = blur_threshold
        self._min_face_size = min_face_size

    async def assess(self, face_image: np.ndarray) -> QualityAssessment:
        # Calculate blur score
        gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()

        # Calculate lighting score
        lighting_score = np.mean(gray)

        # Get face size
        h, w = face_image.shape[:2]
        face_size = min(h, w)

        # Overall quality score (0-100)
        quality_score = self._calculate_overall_score(
            blur_score, lighting_score, face_size
        )

        # Check if acceptable
        is_acceptable = (
            blur_score >= self._blur_threshold and
            face_size >= self._min_face_size and
            quality_score >= 70
        )

        return QualityAssessment(
            score=quality_score,
            blur_score=blur_score,
            lighting_score=lighting_score,
            face_size=face_size,
            is_acceptable=is_acceptable
        )

# app/infrastructure/ml/similarity/cosine_similarity.py
class CosineSimilarityCalculator:
    """Cosine similarity calculation"""

    def __init__(self, threshold: float = 0.6):
        self._threshold = threshold

    def calculate(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        # L2 normalize
        emb1_norm = emb1 / np.linalg.norm(emb1)
        emb2_norm = emb2 / np.linalg.norm(emb2)

        # Cosine similarity
        similarity = np.dot(emb1_norm, emb2_norm)

        # Convert to distance
        distance = 1.0 - similarity

        return float(distance)

    def get_threshold(self) -> float:
        return self._threshold

# app/infrastructure/storage/local_storage.py
class LocalFileStorage:
    """Local filesystem storage"""

    def __init__(self, upload_folder: str):
        self._upload_folder = upload_folder
        os.makedirs(upload_folder, exist_ok=True)

    async def save_temp(self, file: UploadFile) -> str:
        file_extension = os.path.splitext(file.filename)[1]
        temp_filename = f"{uuid.uuid4()}{file_extension}"
        temp_file_path = os.path.join(self._upload_folder, temp_filename)

        with open(temp_file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        return temp_file_path

    async def cleanup(self, file_path: str) -> None:
        if os.path.exists(file_path):
            os.remove(file_path)

# app/infrastructure/persistence/repositories/memory_embedding.py
class InMemoryEmbeddingRepository:
    """In-memory embedding repository for MVP"""

    def __init__(self):
        self._embeddings: Dict[str, np.ndarray] = {}

    async def save(self, user_id: str, embedding: np.ndarray) -> None:
        self._embeddings[user_id] = embedding

    async def find_by_user_id(self, user_id: str) -> Optional[np.ndarray]:
        return self._embeddings.get(user_id)
```

**Create factories**:

```python
# app/infrastructure/ml/factories/detector_factory.py
class FaceDetectorFactory:
    @staticmethod
    def create(detector_type: str) -> IFaceDetector:
        if detector_type == "mtcnn":
            return MTCNNDetector()
        elif detector_type == "mediapipe":
            return MediaPipeDetector()
        else:
            raise ValueError(f"Unknown detector: {detector_type}")

# app/infrastructure/ml/factories/extractor_factory.py
class EmbeddingExtractorFactory:
    @staticmethod
    def create(model_type: str) -> IEmbeddingExtractor:
        if model_type == "facenet":
            return DeepFaceExtractor(model_name="Facenet")
        elif model_type == "vggface":
            return DeepFaceExtractor(model_name="VGG-Face")
        else:
            raise ValueError(f"Unknown model: {model_type}")
```

**Checklist**:
- [ ] Create `MTCNNDetector` or similar
- [ ] Create embedding extractor (DeepFace or FaceNet)
- [ ] Create `QualityAssessor`
- [ ] Create `CosineSimilarityCalculator`
- [ ] Create `LocalFileStorage`
- [ ] Create `InMemoryEmbeddingRepository`
- [ ] Create factories
- [ ] Write unit tests for each component

**Files Created**: ~10 files
**Estimated Time**: 3 days

---

### Day 6-7: Application Layer (Use Cases)

```python
# app/application/use_cases/enroll_face.py
from app.domain.interfaces.face_detector import IFaceDetector
from app.domain.interfaces.embedding_extractor import IEmbeddingExtractor
from app.domain.interfaces.quality_assessor import IQualityAssessor
from app.domain.interfaces.embedding_repository import IEmbeddingRepository
from app.domain.entities.face_embedding import FaceEmbedding

class EnrollFaceUseCase:
    """Use case for enrolling a face"""

    def __init__(
        self,
        detector: IFaceDetector,
        extractor: IEmbeddingExtractor,
        quality_assessor: IQualityAssessor,
        repository: IEmbeddingRepository
    ):
        self._detector = detector
        self._extractor = extractor
        self._quality_assessor = quality_assessor
        self._repository = repository

    async def execute(
        self,
        user_id: str,
        image: np.ndarray
    ) -> FaceEmbedding:
        """
        Execute face enrollment

        Raises:
            FaceNotDetectedError: No face found
            MultipleFacesError: Multiple faces found
            PoorImageQualityError: Quality too low
        """
        # Step 1: Detect face
        detection = await self._detector.detect(image)

        # Step 2: Extract face region
        x, y, w, h = detection.bounding_box
        face_region = image[y:y+h, x:x+w]

        # Step 3: Assess quality
        quality = await self._quality_assessor.assess(face_region)

        if not quality.is_acceptable:
            raise PoorImageQualityError(quality.score)

        # Step 4: Extract embedding
        embedding = await self._extractor.extract(face_region)

        # Step 5: Save to repository
        await self._repository.save(user_id, embedding)

        # Step 6: Return result
        return FaceEmbedding(
            user_id=user_id,
            vector=embedding,
            quality_score=quality.score,
            created_at=datetime.utcnow()
        )

# app/application/use_cases/verify_face.py
class VerifyFaceUseCase:
    """Use case for verifying a face"""

    def __init__(
        self,
        detector: IFaceDetector,
        extractor: IEmbeddingExtractor,
        similarity_calculator: ISimilarityCalculator,
        repository: IEmbeddingRepository
    ):
        self._detector = detector
        self._extractor = extractor
        self._similarity_calculator = similarity_calculator
        self._repository = repository

    async def execute(
        self,
        user_id: str,
        image: np.ndarray
    ) -> VerificationResult:
        """
        Execute face verification

        Raises:
            FaceNotDetectedError: No face found
            EmbeddingNotFoundError: No stored embedding for user
        """
        # Step 1: Detect face
        detection = await self._detector.detect(image)

        # Step 2: Extract face region
        x, y, w, h = detection.bounding_box
        face_region = image[y:y+h, x:x+w]

        # Step 3: Extract embedding
        new_embedding = await self._extractor.extract(face_region)

        # Step 4: Retrieve stored embedding
        stored_embedding = await self._repository.find_by_user_id(user_id)

        if stored_embedding is None:
            raise EmbeddingNotFoundError(user_id)

        # Step 5: Calculate similarity
        distance = self._similarity_calculator.calculate(
            new_embedding,
            stored_embedding
        )

        # Step 6: Verify against threshold
        threshold = self._similarity_calculator.get_threshold()
        verified = distance < threshold
        confidence = 1.0 - distance

        return VerificationResult(
            verified=verified,
            confidence=confidence,
            distance=distance
        )

@dataclass
class VerificationResult:
    verified: bool
    confidence: float
    distance: float
```

**Checklist**:
- [ ] Create `EnrollFaceUseCase`
- [ ] Create `VerifyFaceUseCase`
- [ ] Create stub `CheckLivenessUseCase` (implement in Sprint 3)
- [ ] Write unit tests with mocks

**Files Created**: ~5 files
**Estimated Time**: 2 days

---

### Day 8-9: Dependency Injection Container

```bash
pip install dependency-injector
```

```python
# app/core/container.py
from dependency_injector import containers, providers
from app.infrastructure.ml.factories.detector_factory import FaceDetectorFactory
from app.infrastructure.ml.factories.extractor_factory import EmbeddingExtractorFactory
# ... other imports

class Container(containers.DeclarativeContainer):
    """Dependency Injection Container"""

    # Configuration
    config = providers.Configuration()

    # Infrastructure - ML Components
    face_detector = providers.Singleton(
        FaceDetectorFactory.create,
        detector_type=config.face_detection_model
    )

    embedding_extractor = providers.Singleton(
        EmbeddingExtractorFactory.create,
        model_type=config.face_recognition_model
    )

    quality_assessor = providers.Singleton(
        QualityAssessor,
        blur_threshold=config.blur_threshold,
        min_face_size=config.min_face_size
    )

    similarity_calculator = providers.Singleton(
        CosineSimilarityCalculator,
        threshold=config.verification_threshold
    )

    # Infrastructure - Storage
    file_storage = providers.Singleton(
        LocalFileStorage,
        upload_folder=config.upload_folder
    )

    embedding_repository = providers.Singleton(
        InMemoryEmbeddingRepository
    )

    # Application - Use Cases
    enroll_face_use_case = providers.Factory(
        EnrollFaceUseCase,
        detector=face_detector,
        extractor=embedding_extractor,
        quality_assessor=quality_assessor,
        repository=embedding_repository
    )

    verify_face_use_case = providers.Factory(
        VerifyFaceUseCase,
        detector=face_detector,
        extractor=embedding_extractor,
        similarity_calculator=similarity_calculator,
        repository=embedding_repository
    )

# app/main.py
from app.core.container import Container
from app.core.config import settings

# Create container
container = Container()
container.config.from_dict(settings.dict())

# Wire up dependencies
container.wire(modules=[
    "app.api.routes.v1.enrollment",
    "app.api.routes.v1.verification"
])

app = FastAPI()

# ... rest of app setup
```

**Checklist**:
- [ ] Install `dependency-injector`
- [ ] Create `Container` class
- [ ] Wire up all dependencies
- [ ] Integrate with FastAPI
- [ ] Test dependency injection works

**Files Created**: 2 files
**Estimated Time**: 1 day

---

### Day 10: API Layer with DTOs

```python
# app/api/schemas/enrollment.py
from pydantic import BaseModel, Field

class EnrollmentResponse(BaseModel):
    success: bool
    user_id: str
    quality_score: float = Field(..., ge=0, le=100)
    message: str

# app/api/schemas/verification.py
class VerificationResponse(BaseModel):
    verified: bool
    confidence: float = Field(..., ge=0, le=1)
    distance: float
    message: str

# app/api/schemas/common.py
class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None

# app/api/routes/v1/enrollment.py
from dependency_injector.wiring import inject, Provide
from app.core.container import Container
from app.application.use_cases.enroll_face import EnrollFaceUseCase

router = APIRouter()

@router.post("/enroll", response_model=EnrollmentResponse)
@inject
async def enroll_face(
    user_id: str = Form(...),
    file: UploadFile = File(...),
    use_case: EnrollFaceUseCase = Depends(Provide[Container.enroll_face_use_case]),
    storage: IFileStorage = Depends(Provide[Container.file_storage])
):
    """Enroll a user's face"""

    # Save uploaded file
    image_path = await storage.save_temp(file)

    try:
        # Load image
        image = cv2.imread(image_path)

        # Execute use case
        result = await use_case.execute(user_id, image)

        return EnrollmentResponse(
            success=True,
            user_id=result.user_id,
            quality_score=result.quality_score,
            message="Face enrolled successfully"
        )

    finally:
        # Cleanup
        await storage.cleanup(image_path)

# app/api/routes/v1/verification.py
@router.post("/verify", response_model=VerificationResponse)
@inject
async def verify_face(
    user_id: str = Form(...),
    file: UploadFile = File(...),
    use_case: VerifyFaceUseCase = Depends(Provide[Container.verify_face_use_case]),
    storage: IFileStorage = Depends(Provide[Container.file_storage])
):
    """Verify a user's face"""

    image_path = await storage.save_temp(file)

    try:
        image = cv2.imread(image_path)
        result = await use_case.execute(user_id, image)

        return VerificationResponse(
            verified=result.verified,
            confidence=result.confidence,
            distance=result.distance,
            message="Face verified" if result.verified else "Face does not match"
        )

    finally:
        await storage.cleanup(image_path)
```

**Checklist**:
- [ ] Create Pydantic schemas
- [ ] Create API routes with dependency injection
- [ ] Remove old endpoint files
- [ ] Test endpoints

**Files Created**: ~8 files
**Estimated Time**: 1 day

---

### Day 11: Error Handling & Security

```python
# app/api/middleware/error_handler.py
from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.domain.exceptions.base import BiometricProcessorError
from app.domain.exceptions.face_errors import *

@app.exception_handler(BiometricProcessorError)
async def biometric_error_handler(
    request: Request,
    exc: BiometricProcessorError
) -> JSONResponse:
    """Handle domain exceptions"""

    status_map = {
        "FACE_NOT_DETECTED": status.HTTP_400_BAD_REQUEST,
        "MULTIPLE_FACES": status.HTTP_400_BAD_REQUEST,
        "POOR_IMAGE_QUALITY": status.HTTP_400_BAD_REQUEST,
        "EMBEDDING_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    }

    status_code = status_map.get(exc.error_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message
        }
    )

# Fix CORS in app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # NOT ["*"]
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Add rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.post("/enroll")
@limiter.limit("10/minute")  # 10 requests per minute
async def enroll_face(...):
    ...
```

**Update config**:

```python
# app/core/config.py
class Settings(BaseSettings):
    # ... existing settings ...

    # CORS - NO WILDCARD
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000"])

    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

# .env.example
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
```

**Checklist**:
- [ ] Implement global exception handler
- [ ] Fix CORS configuration
- [ ] Add rate limiting
- [ ] Update config validation

**Files Modified**: 3 files
**Estimated Time**: 0.5 day

---

### Day 12: Structured Logging

```bash
pip install structlog
```

```python
# app/core/logging.py
import structlog
import logging

def configure_logging(log_level: str = "INFO"):
    """Configure structured logging"""

    logging.basicConfig(
        format="%(message)s",
        level=log_level
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

# app/api/middleware/correlation_id.py
import uuid
import structlog
from fastapi import Request

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    """Add correlation ID to all requests"""

    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))

    structlog.contextvars.bind_contextvars(
        correlation_id=correlation_id,
        path=request.url.path,
        method=request.method
    )

    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id

    structlog.contextvars.clear_contextvars()

    return response

# Usage in use cases
import structlog

logger = structlog.get_logger()

async def execute(self, user_id: str, image: np.ndarray):
    logger.info("enrollment_started", user_id=user_id)

    try:
        # ... processing ...
        logger.info("enrollment_completed", user_id=user_id, quality_score=quality)
        return result

    except Exception as e:
        logger.error("enrollment_failed", user_id=user_id, error=str(e), exc_info=True)
        raise
```

**Checklist**:
- [ ] Install structlog
- [ ] Configure structured logging
- [ ] Add correlation ID middleware
- [ ] Add logging to all use cases
- [ ] Test logging output

**Files Created**: 3 files
**Estimated Time**: 0.5 day

---

### Sprint 1 Deliverables

**Architecture**:
- ✅ Clean layered architecture
- ✅ Domain layer with interfaces and entities
- ✅ Infrastructure layer with ML implementations
- ✅ Application layer with use cases
- ✅ API layer with DTOs
- ✅ Dependency injection container

**Code Quality**:
- ✅ SOLID principles compliance
- ✅ Design patterns (Repository, Factory, DI)
- ✅ Type hints everywhere
- ✅ Comprehensive docstrings

**Security**:
- ✅ Fixed CORS vulnerability
- ✅ Rate limiting
- ✅ Input validation

**Observability**:
- ✅ Structured logging
- ✅ Correlation IDs
- ✅ Error tracking

**Testing**:
- ✅ Unit tests for domain entities
- ✅ Unit tests for use cases (with mocks)
- ✅ Unit tests for infrastructure components

**Estimated Lines of Code**: ~2500 lines
**Files Created**: ~40 files

---

## 🧪 Sprint 2: Testing & Quality (Week 3)

### Objectives
- ✅ Comprehensive test coverage
- ✅ Code quality automation
- ✅ CI/CD foundation

### Day 1-3: Unit Tests

**Test structure**:

```
tests/
├── unit/
│   ├── domain/
│   │   ├── test_entities.py
│   │   └── test_exceptions.py
│   ├── application/
│   │   ├── test_enroll_face_use_case.py
│   │   └── test_verify_face_use_case.py
│   └── infrastructure/
│       ├── test_mtcnn_detector.py
│       ├── test_deepface_extractor.py
│       ├── test_quality_assessor.py
│       └── test_cosine_similarity.py
```

**Example test**:

```python
# tests/unit/application/test_enroll_face_use_case.py
import pytest
from unittest.mock import Mock, AsyncMock
import numpy as np

from app.application.use_cases.enroll_face import EnrollFaceUseCase
from app.domain.entities.face_detection import FaceDetectionResult
from app.domain.entities.quality_assessment import QualityAssessment
from app.domain.exceptions.face_errors import FaceNotDetectedError, PoorImageQualityError

@pytest.fixture
def mock_detector():
    detector = Mock()
    detector.detect = AsyncMock(return_value=FaceDetectionResult(
        found=True,
        bounding_box=(10, 10, 100, 100),
        landmarks=None,
        confidence=0.99
    ))
    return detector

@pytest.fixture
def mock_extractor():
    extractor = Mock()
    extractor.extract = AsyncMock(return_value=np.random.rand(128))
    return extractor

@pytest.fixture
def mock_quality_assessor():
    assessor = Mock()
    assessor.assess = AsyncMock(return_value=QualityAssessment(
        score=85.0,
        blur_score=150.0,
        lighting_score=120.0,
        face_size=100,
        is_acceptable=True
    ))
    return assessor

@pytest.fixture
def mock_repository():
    repo = Mock()
    repo.save = AsyncMock()
    return repo

@pytest.fixture
def use_case(mock_detector, mock_extractor, mock_quality_assessor, mock_repository):
    return EnrollFaceUseCase(
        detector=mock_detector,
        extractor=mock_extractor,
        quality_assessor=mock_quality_assessor,
        repository=mock_repository
    )

@pytest.mark.asyncio
async def test_enroll_face_success(use_case, mock_repository):
    """Test successful face enrollment"""
    # Arrange
    user_id = "user123"
    image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)

    # Act
    result = await use_case.execute(user_id, image)

    # Assert
    assert result.user_id == user_id
    assert result.quality_score == 85.0
    assert result.vector.shape == (128,)
    mock_repository.save.assert_called_once()

@pytest.mark.asyncio
async def test_enroll_face_no_face_detected(use_case, mock_detector):
    """Test enrollment fails when no face detected"""
    # Arrange
    user_id = "user123"
    image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
    mock_detector.detect = AsyncMock(side_effect=FaceNotDetectedError())

    # Act & Assert
    with pytest.raises(FaceNotDetectedError):
        await use_case.execute(user_id, image)

@pytest.mark.asyncio
async def test_enroll_face_poor_quality(use_case, mock_quality_assessor):
    """Test enrollment fails when image quality is poor"""
    # Arrange
    user_id = "user123"
    image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
    mock_quality_assessor.assess = AsyncMock(return_value=QualityAssessment(
        score=40.0,
        blur_score=50.0,
        lighting_score=60.0,
        face_size=100,
        is_acceptable=False
    ))

    # Act & Assert
    with pytest.raises(PoorImageQualityError):
        await use_case.execute(user_id, image)
```

**Checklist**:
- [ ] Write unit tests for all domain entities
- [ ] Write unit tests for all use cases (with mocks)
- [ ] Write unit tests for all infrastructure components
- [ ] Achieve 80%+ code coverage
- [ ] Run tests: `pytest --cov=app tests/`

**Estimated Time**: 3 days

---

### Day 4-5: Integration Tests

```python
# tests/integration/test_enrollment_flow.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_full_enrollment_flow():
    """Test complete enrollment flow through API"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Prepare test image
        with open("tests/fixtures/sample_face.jpg", "rb") as f:
            files = {"file": ("test.jpg", f, "image/jpeg")}
            data = {"user_id": "test_user_123"}

            # Call enrollment endpoint
            response = await client.post(
                "/api/v1/enroll",
                files=files,
                data=data
            )

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["user_id"] == "test_user_123"
            assert data["quality_score"] > 0

@pytest.mark.asyncio
async def test_verification_after_enrollment():
    """Test verification works after enrollment"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Enroll
        with open("tests/fixtures/sample_face.jpg", "rb") as f:
            await client.post(
                "/api/v1/enroll",
                files={"file": ("test.jpg", f, "image/jpeg")},
                data={"user_id": "test_user"}
            )

        # Verify with same image
        with open("tests/fixtures/sample_face.jpg", "rb") as f:
            response = await client.post(
                "/api/v1/verify",
                files={"file": ("test.jpg", f, "image/jpeg")},
                data={"user_id": "test_user"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["verified"] is True
            assert data["confidence"] > 0.8

@pytest.mark.asyncio
async def test_no_face_detected_returns_400():
    """Test API returns 400 when no face detected"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Upload image with no face
        with open("tests/fixtures/no_face.jpg", "rb") as f:
            response = await client.post(
                "/api/v1/enroll",
                files={"file": ("test.jpg", f, "image/jpeg")},
                data={"user_id": "test_user"}
            )

            assert response.status_code == 400
            data = response.json()
            assert data["error_code"] == "FACE_NOT_DETECTED"
```

**Checklist**:
- [ ] Test complete enrollment flow
- [ ] Test complete verification flow
- [ ] Test error cases (no face, poor quality, etc.)
- [ ] Test API error responses
- [ ] Prepare test fixtures (sample images)

**Estimated Time**: 2 days

---

### Day 6: Code Quality Tools

**Install tools**:

```bash
pip install black isort mypy pylint pytest-cov
```

**Configure tools**:

```toml
# pyproject.toml
[tool.black]
line-length = 100
target-version = ['py310']

[tool.isort]
profile = "black"
line_length = 100

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pylint.messages_control]
max-line-length = 100
disable = [
    "C0111",  # missing-docstring
    "R0903",  # too-few-public-methods
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Pre-commit hooks**:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy

  - repo: https://github.com/pycqa/pylint
    rev: v3.0.0
    hooks:
      - id: pylint
```

**Checklist**:
- [ ] Install code quality tools
- [ ] Configure black, isort, mypy, pylint
- [ ] Setup pre-commit hooks
- [ ] Run formatter on all code
- [ ] Fix all type errors
- [ ] Fix all linting errors

**Estimated Time**: 1 day

---

### Sprint 2 Deliverables

- ✅ 80%+ test coverage
- ✅ Unit tests for all layers
- ✅ Integration tests for API
- ✅ Code formatting (black)
- ✅ Import sorting (isort)
- ✅ Type checking (mypy)
- ✅ Linting (pylint)
- ✅ Pre-commit hooks

---

## 🎭 Sprint 3: Liveness Detection (Week 4-5)

### Objectives
- ✅ Implement smile-based liveness detection
- ✅ Add liveness API endpoint
- ✅ MVP complete

### Day 1-3: Smile Liveness Detection

```python
# app/infrastructure/ml/liveness/smile_detector.py
import dlib
import numpy as np
from scipy.spatial import distance

class SmileLivenessDetector:
    """Detect smile for liveness check"""

    def __init__(self):
        # Load facial landmark predictor
        self._predictor = dlib.shape_predictor("models/shape_predictor_68_face_landmarks.dat")
        self._detector = dlib.get_frontal_face_detector()

    async def detect_smile(self, image: np.ndarray) -> float:
        """
        Detect smile in image

        Returns:
            float: Smile score (0-1), higher = more smile
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Detect face
        faces = self._detector(gray)

        if len(faces) == 0:
            raise FaceNotDetectedError()

        # Get landmarks
        shape = self._predictor(gray, faces[0])
        landmarks = self._shape_to_np(shape)

        # Calculate mouth aspect ratio (MAR)
        mar = self._mouth_aspect_ratio(landmarks)

        # Convert to smile score (0-1)
        smile_score = min(mar / 0.5, 1.0)  # 0.5 is typical smile threshold

        return smile_score

    def _mouth_aspect_ratio(self, landmarks: np.ndarray) -> float:
        """Calculate mouth aspect ratio"""
        # Mouth landmarks: 48-67
        # Vertical distances
        A = distance.euclidean(landmarks[51], landmarks[57])  # Top to bottom (center)
        B = distance.euclidean(landmarks[62], landmarks[66])  # Inner vertical

        # Horizontal distance
        C = distance.euclidean(landmarks[48], landmarks[54])  # Left to right

        # MAR formula
        mar = (A + B) / (2.0 * C)

        return mar

    def _shape_to_np(self, shape) -> np.ndarray:
        """Convert dlib shape to numpy array"""
        coords = np.zeros((68, 2), dtype=int)
        for i in range(68):
            coords[i] = (shape.part(i).x, shape.part(i).y)
        return coords

# app/domain/interfaces/liveness_detector.py
class ILivenessDetector(Protocol):
    async def check_liveness(self, image: np.ndarray) -> LivenessResult: ...

@dataclass
class LivenessResult:
    is_live: bool
    liveness_score: float  # 0-100
    challenge: str
    challenge_completed: bool

# app/application/use_cases/check_liveness.py
class CheckLivenessUseCase:
    """Use case for checking liveness"""

    def __init__(
        self,
        detector: IFaceDetector,
        liveness_detector: ILivenessDetector
    ):
        self._detector = detector
        self._liveness_detector = liveness_detector

    async def execute(self, image: np.ndarray) -> LivenessResult:
        """
        Check if image shows live person

        Challenge: "Please smile"
        """
        # Detect face first
        detection = await self._detector.detect(image)

        # Check for smile
        smile_score = await self._liveness_detector.detect_smile(image)

        # Determine if live
        is_live = smile_score > 0.4  # 40% smile threshold
        liveness_score = smile_score * 100  # Convert to 0-100

        return LivenessResult(
            is_live=is_live,
            liveness_score=liveness_score,
            challenge="smile",
            challenge_completed=is_live
        )
```

**Checklist**:
- [ ] Download dlib shape predictor model
- [ ] Implement smile detection
- [ ] Create `SmileLivenessDetector`
- [ ] Create `CheckLivenessUseCase`
- [ ] Write unit tests
- [ ] Test with sample images

**Estimated Time**: 3 days

---

### Day 4: Liveness API

```python
# app/api/routes/v1/liveness.py
@router.post("/liveness", response_model=LivenessResponse)
@inject
async def check_liveness(
    file: UploadFile = File(...),
    use_case: CheckLivenessUseCase = Depends(Provide[Container.check_liveness_use_case]),
    storage: IFileStorage = Depends(Provide[Container.file_storage])
):
    """Check liveness (smile detection)"""

    image_path = await storage.save_temp(file)

    try:
        image = cv2.imread(image_path)
        result = await use_case.execute(image)

        return LivenessResponse(
            is_live=result.is_live,
            liveness_score=result.liveness_score,
            challenge=result.challenge,
            challenge_completed=result.challenge_completed
        )

    finally:
        await storage.cleanup(image_path)

# app/api/schemas/liveness.py
class LivenessResponse(BaseModel):
    is_live: bool
    liveness_score: float = Field(..., ge=0, le=100)
    challenge: str
    challenge_completed: bool
```

**Checklist**:
- [ ] Create liveness API endpoint
- [ ] Add to DI container
- [ ] Write integration tests
- [ ] Test with Postman/curl

**Estimated Time**: 1 day

---

### Day 5: Integration & Testing

- [ ] Test enrollment + liveness flow
- [ ] Test verification + liveness flow
- [ ] Performance testing
- [ ] Documentation

**Estimated Time**: 1 day

---

### Sprint 3 Deliverables

- ✅ Smile-based liveness detection
- ✅ POST /api/v1/liveness endpoint
- ✅ Integration tests
- ✅ **MVP COMPLETE**

**MVP Features**:
- ✅ Face enrollment
- ✅ Face verification (1:1)
- ✅ Liveness detection (smile)
- ✅ Quality assessment
- ✅ Professional architecture
- ✅ Comprehensive tests

---

## 🗄️ Sprint 4: Database Integration (Week 6)

### Objectives
- ✅ Persistent storage
- ✅ PostgreSQL with pgvector
- ✅ Production-ready

### Day 1-2: Database Setup

```bash
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: biometric
      POSTGRES_PASSWORD: biometric_pass
      POSTGRES_DB: biometric_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

**Install dependencies**:

```bash
pip install asyncpg sqlalchemy[asyncio] alembic
```

**Database models**:

```python
# app/infrastructure/persistence/models/embedding.py
from sqlalchemy import Column, String, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class EmbeddingModel(Base):
    __tablename__ = "embeddings"

    id = Column(String, primary_key=True)
    user_id = Column(String, unique=True, nullable=False, index=True)
    tenant_id = Column(String, nullable=True, index=True)
    embedding = Column(Vector(128), nullable=False)  # 128-D vector
    quality_score = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=True)

# Alembic migration
alembic init migrations
alembic revision --autogenerate -m "Create embeddings table"
alembic upgrade head
```

**Checklist**:
- [ ] Setup PostgreSQL with pgvector in Docker
- [ ] Install SQLAlchemy and asyncpg
- [ ] Create database models
- [ ] Setup Alembic migrations
- [ ] Run migrations

**Estimated Time**: 2 days

---

### Day 3-4: Repository Implementation

```python
# app/infrastructure/persistence/repositories/postgres_embedding.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.domain.interfaces.embedding_repository import IEmbeddingRepository
from app.infrastructure.persistence.models.embedding import EmbeddingModel

class PostgresEmbeddingRepository:
    """PostgreSQL repository with pgvector similarity search"""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, user_id: str, embedding: np.ndarray) -> None:
        """Save embedding to database"""
        model = EmbeddingModel(
            id=str(uuid.uuid4()),
            user_id=user_id,
            embedding=embedding.tolist(),
            quality_score=0.0,  # Set from caller
            created_at=datetime.utcnow()
        )

        self._session.add(model)
        await self._session.commit()

    async def find_by_user_id(self, user_id: str) -> Optional[np.ndarray]:
        """Find embedding by user ID"""
        result = await self._session.execute(
            select(EmbeddingModel).where(EmbeddingModel.user_id == user_id)
        )

        model = result.scalar_one_or_none()

        if model is None:
            return None

        return np.array(model.embedding)

    async def find_similar(
        self,
        embedding: np.ndarray,
        threshold: float,
        limit: int = 5
    ) -> List[Tuple[str, float]]:
        """Find similar embeddings using pgvector"""
        # pgvector cosine distance operator: <=>
        result = await self._session.execute(
            select(
                EmbeddingModel.user_id,
                EmbeddingModel.embedding.cosine_distance(embedding).label("distance")
            )
            .where(EmbeddingModel.embedding.cosine_distance(embedding) < threshold)
            .order_by("distance")
            .limit(limit)
        )

        return [(row.user_id, row.distance) for row in result]
```

**Update DI container**:

```python
# app/core/container.py
class Container(containers.DeclarativeContainer):
    # ... existing ...

    # Database
    database_session = providers.Resource(
        get_database_session,
        database_url=config.database_url
    )

    # Update repository to use Postgres
    embedding_repository = providers.Singleton(
        PostgresEmbeddingRepository,
        session=database_session
    )
```

**Checklist**:
- [ ] Implement `PostgresEmbeddingRepository`
- [ ] Update DI container
- [ ] Write repository tests
- [ ] Test similarity search

**Estimated Time**: 2 days

---

### Day 5: Migration & Testing

- [ ] Migrate from in-memory to Postgres
- [ ] Integration testing with database
- [ ] Performance testing
- [ ] Documentation

**Estimated Time**: 1 day

---

### Sprint 4 Deliverables

- ✅ PostgreSQL with pgvector
- ✅ Database migrations
- ✅ `PostgresEmbeddingRepository`
- ✅ Similarity search
- ✅ Production-ready storage

---

## 🚀 Sprint 5: Production Readiness (Week 7-8)

### Objectives
- ✅ Performance optimization
- ✅ Observability (metrics, tracing)
- ✅ Documentation
- ✅ Deployment

### Tasks

**Week 7**:
- [ ] Performance profiling and optimization
- [ ] Add Prometheus metrics
- [ ] Add distributed tracing (OpenTelemetry)
- [ ] Load testing (Locust)
- [ ] Optimize Docker images

**Week 8**:
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Architecture documentation
- [ ] Deployment guide
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Kubernetes manifests (if needed)

**Estimated Time**: 2 weeks

---

## 📊 Final Deliverables

### Architecture
- ✅ Clean layered architecture
- ✅ SOLID principles compliance
- ✅ Design patterns implemented
- ✅ Fully testable

### Features
- ✅ Face enrollment
- ✅ Face verification (1:1)
- ✅ Liveness detection (smile)
- ✅ Quality assessment
- ✅ Persistent storage (PostgreSQL)

### Code Quality
- ✅ 80%+ test coverage
- ✅ Type hints
- ✅ Formatted code
- ✅ Linting passed
- ✅ No security vulnerabilities

### Production Ready
- ✅ Structured logging
- ✅ Metrics
- ✅ Error handling
- ✅ Rate limiting
- ✅ API documentation
- ✅ Deployment automation

---

## 🎯 Success Metrics

| Metric | Target | Status |
|--------|--------|--------|
| Test Coverage | >80% | ⏸️ |
| Type Coverage | 100% | ⏸️ |
| API Response Time (p95) | <500ms | ⏸️ |
| Enrollment Time (p95) | <2s | ⏸️ |
| Code Duplication | <5% | ⏸️ |
| Security Score | A+ | ⏸️ |

---

## 📝 Notes

- All sprints are flexible and can be adjusted based on progress
- MVP can be delivered after Sprint 3 (5 weeks)
- Full production readiness after Sprint 5 (8 weeks)
- Each sprint includes buffer for unexpected issues

---

**Status**: ✅ READY TO START
**Next Action**: Begin Sprint 1, Day 1 - Create domain interfaces
