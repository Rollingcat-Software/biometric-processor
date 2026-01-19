# Biometric Processor - Hexagonal Architecture Documentation

## Table of Contents

1. [Overview](#overview)
2. [Architectural Principles](#architectural-principles)
3. [Layer Structure](#layer-structure)
4. [Design Patterns](#design-patterns)
5. [SOLID Principles Compliance](#solid-principles-compliance)
6. [Domain-Driven Design](#domain-driven-design)
7. [Event-Driven Architecture](#event-driven-architecture)
8. [CQRS Pattern](#cqrs-pattern)
9. [Dependency Injection](#dependency-injection)
10. [Testing Strategy](#testing-strategy)
11. [Deployment Architecture](#deployment-architecture)

---

## Overview

The Biometric Processor API follows **Hexagonal Architecture** (also known as Ports and Adapters Architecture), which ensures:

- **Business logic independence**: Core domain logic is isolated from technical concerns
- **Testability**: Easy to test with mock implementations
- **Flexibility**: Easy to swap implementations (database, ML models, etc.)
- **Maintainability**: Clear separation of concerns

### Hexagonal Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     API Layer (Adapters)                     │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   FastAPI   │  │  WebSocket   │  │   CLI Tool   │       │
│  │  REST API   │  │   Handler    │  │              │       │
│  └──────┬──────┘  └──────┬───────┘  └──────┬───────┘       │
└─────────┼─────────────────┼──────────────────┼──────────────┘
          │                 │                  │
          ▼                 ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│              Application Layer (Use Cases)                   │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │  EnrollFaceUse   │  │  VerifyFaceUse   │  ...           │
│  │      Case        │  │      Case        │                 │
│  └────────┬─────────┘  └────────┬─────────┘                │
└───────────┼──────────────────────┼──────────────────────────┘
            │                      │
            ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│           Domain Layer (Business Logic - CORE)               │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Entities   │  │  Interfaces  │  │   Services   │       │
│  │             │  │   (Ports)    │  │              │       │
│  └─────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
            ▲                      ▲
            │                      │
┌───────────┴──────────────────────┴──────────────────────────┐
│         Infrastructure Layer (Adapters)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  PostgreSQL  │  │   DeepFace   │  │    Redis     │      │
│  │   pgvector   │  │  ML Models   │  │  Event Bus   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## Architectural Principles

### 1. Dependency Rule

**Dependencies always point inward toward the domain core.**

```
API → Application → Domain ← Infrastructure
```

- **Domain Layer**: Has NO dependencies on other layers
- **Application Layer**: Depends only on Domain interfaces
- **API Layer**: Depends on Application layer
- **Infrastructure Layer**: Implements Domain interfaces

### 2. Ports and Adapters

#### Ports (Interfaces)
Define contracts for communication with external systems:
- Located in `app/domain/interfaces/`
- Examples: `IFaceDetector`, `IEmbeddingRepository`, `IEventBus`

#### Adapters (Implementations)
Implement the ports for specific technologies:
- Located in `app/infrastructure/`
- Examples: `DeepFaceDetector`, `PgVectorEmbeddingRepository`, `RedisEventBus`

### 3. Technology Independence

The domain layer is completely independent of:
- Web frameworks (FastAPI)
- Databases (PostgreSQL)
- ML libraries (DeepFace, TensorFlow)
- Message brokers (Redis)

This allows us to:
- Replace FastAPI with another framework
- Switch from PostgreSQL to MongoDB
- Use different ML models
- Change caching/messaging systems

---

## Layer Structure

### Domain Layer (`app/domain/`)

**Purpose**: Contains pure business logic with no technical concerns.

```
app/domain/
├── entities/           # Domain entities (business objects)
│   ├── face_embedding.py
│   ├── proctor_session.py
│   └── face_detection.py
├── interfaces/         # Ports (contracts for adapters)
│   ├── face_detector.py
│   ├── embedding_repository.py
│   ├── liveness_detector.py
│   └── ... (23 interfaces)
├── services/           # Domain services (complex business logic)
│   └── embedding_fusion_service.py
├── events/            # Domain events
│   ├── base.py
│   └── biometric_events.py
└── exceptions/        # Domain-specific exceptions
    └── face_errors.py
```

**Key Characteristics**:
- No framework dependencies
- No database dependencies
- No ML library dependencies
- Pure Python with business logic only
- Uses Protocol for interface definitions

**Example Entity**:
```python
@dataclass
class FaceEmbedding:
    user_id: str
    vector: np.ndarray
    quality_score: float
    tenant_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
```

**Example Interface (Port)**:
```python
class IFaceDetector(Protocol):
    async def detect(self, image: np.ndarray) -> FaceDetectionResult:
        """Detect faces in an image."""
        ...
```

### Application Layer (`app/application/`)

**Purpose**: Orchestrates use cases by coordinating domain objects and services.

```
app/application/
├── use_cases/          # Application use cases (orchestration)
│   ├── enroll_face.py
│   ├── verify_face.py
│   ├── search_face.py
│   └── ... (17 use cases)
├── commands/          # Command pattern for CQRS
│   ├── base.py
│   └── enrollment_commands.py
├── queries/           # Query objects for read operations
└── services/          # Application services (cross-cutting concerns)
    └── event_publisher.py
```

**Key Characteristics**:
- Depends only on domain interfaces (not implementations)
- Orchestrates multiple domain operations
- Handles transaction boundaries
- Publishes domain events
- No HTTP/API concerns

**Example Use Case**:
```python
class EnrollFaceUseCase:
    def __init__(
        self,
        detector: IFaceDetector,           # Port (interface)
        extractor: IEmbeddingExtractor,    # Port
        repository: IEmbeddingRepository,  # Port
    ):
        self._detector = detector
        self._extractor = extractor
        self._repository = repository

    async def execute(self, user_id: str, image_path: str) -> FaceEmbedding:
        # Orchestrate domain operations
        detection = await self._detector.detect(image)
        embedding = await self._extractor.extract(face_region)
        await self._repository.save(user_id, embedding)
        return FaceEmbedding(user_id, embedding)
```

### Infrastructure Layer (`app/infrastructure/`)

**Purpose**: Implements domain interfaces using specific technologies.

```
app/infrastructure/
├── ml/                 # ML model adapters
│   ├── detectors/      # Face detection implementations
│   ├── extractors/     # Embedding extraction implementations
│   ├── liveness/       # Liveness detection implementations
│   └── factories/      # Factory pattern for ML components
├── persistence/        # Database adapters
│   └── repositories/
│       ├── pgvector_embedding_repository.py
│       └── postgres_session_repository.py
├── messaging/         # Event bus adapters
│   └── redis_event_bus.py
├── caching/          # Cache adapters
│   └── redis_cache.py
└── storage/          # File storage adapters
    └── local_file_storage.py
```

**Key Characteristics**:
- Implements domain interfaces (ports)
- Contains all technical/framework code
- Can be easily swapped/replaced
- Depends on domain layer (interfaces)

**Example Adapter**:
```python
class PgVectorEmbeddingRepository(IEmbeddingRepository):
    """PostgreSQL adapter implementing IEmbeddingRepository port."""

    def __init__(self, database_url: str):
        self._database_url = database_url

    async def save(self, user_id: str, embedding: np.ndarray, ...) -> None:
        # PostgreSQL-specific implementation
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO face_embeddings ...",
                user_id, embedding.tolist(), ...
            )
```

### API Layer (`app/api/`)

**Purpose**: HTTP/WebSocket adapters that expose use cases via REST API.

```
app/api/
├── routes/            # API endpoints (22 modules)
│   ├── enrollment.py
│   ├── verification.py
│   └── ... (20 more)
├── schemas/           # Pydantic request/response models
│   ├── enrollment.py
│   └── verification.py
├── middleware/        # Cross-cutting concerns
│   ├── error_handler.py
│   ├── rate_limit.py
│   └── security_headers.py
├── dependencies/      # FastAPI dependency injection
└── validators/        # Input validation
```

**Key Characteristics**:
- HTTP-specific concerns only
- Transforms HTTP requests to use case inputs
- Transforms use case outputs to HTTP responses
- Depends on application layer (use cases)

**Example API Route**:
```python
@router.post("/enroll")
async def enroll_face(
    user_id: str = Form(...),
    file: UploadFile = File(...),
    use_case: EnrollFaceUseCase = Depends(get_enroll_face_use_case),
) -> EnrollmentResponse:
    # API concerns: validation, file handling
    image_path = await storage.save_temp(file)

    # Delegate to use case (application layer)
    result = await use_case.execute(user_id, image_path)

    # Transform to API response
    return EnrollmentResponse(
        success=True,
        user_id=result.user_id,
        quality_score=result.quality_score,
    )
```

---

## Design Patterns

### 1. Repository Pattern
**Purpose**: Abstract data access logic

```python
# Port (interface)
class IEmbeddingRepository(Protocol):
    async def save(self, user_id: str, embedding: np.ndarray) -> None: ...
    async def find_by_user_id(self, user_id: str) -> Optional[np.ndarray]: ...

# Adapters (implementations)
class PgVectorEmbeddingRepository(IEmbeddingRepository): ...
class InMemoryEmbeddingRepository(IEmbeddingRepository): ...
```

### 2. Factory Pattern
**Purpose**: Create complex objects without exposing creation logic

```python
class FaceDetectorFactory:
    @staticmethod
    def create(detector_type: str) -> IFaceDetector:
        if detector_type == "retinaface":
            return RetinaFaceDetector()
        elif detector_type == "mtcnn":
            return MTCNNDetector()
        # ...
```

### 3. Strategy Pattern
**Purpose**: Select algorithm at runtime

```python
# Different liveness detection strategies
class PassiveLivenessDetector(ILivenessDetector): ...
class ActiveLivenessDetector(ILivenessDetector): ...
class CombinedLivenessDetector(ILivenessDetector): ...
```

### 4. Observer Pattern (Domain Events)
**Purpose**: Decouple event producers from consumers

```python
# Publish event
event = FaceEnrolledEvent(user_id="123", quality_score=95.5)
await event_publisher.publish(event)

# Multiple handlers can observe
class SendEmailHandler(DomainEventHandler[FaceEnrolledEvent]): ...
class UpdateAnalyticsHandler(DomainEventHandler[FaceEnrolledEvent]): ...
```

### 5. Command Pattern (CQRS)
**Purpose**: Separate read and write operations

```python
# Write operation (Command)
command = EnrollFaceCommand(user_id="123", image_path="/path")
result = await command_bus.execute(command)

# Read operation (Query)
query = GetUserEmbeddingQuery(user_id="123")
embedding = await query_handler.execute(query)
```

### 6. Decorator Pattern
**Purpose**: Add responsibilities to objects dynamically

```python
# Caching decorator
class CachedEmbeddingRepository(IEmbeddingRepository):
    def __init__(self, repository: IEmbeddingRepository, cache: ICache):
        self._repository = repository
        self._cache = cache

    async def find_by_user_id(self, user_id: str) -> Optional[np.ndarray]:
        # Check cache first
        cached = await self._cache.get(user_id)
        if cached:
            return cached

        # Fallback to repository
        embedding = await self._repository.find_by_user_id(user_id)
        await self._cache.set(user_id, embedding)
        return embedding
```

---

## SOLID Principles Compliance

### Single Responsibility Principle (SRP)
✅ **Each class has one reason to change**

- `EnrollFaceUseCase`: Only handles enrollment orchestration
- `FaceDetector`: Only detects faces
- `EmbeddingExtractor`: Only extracts embeddings
- `EmbeddingRepository`: Only persists embeddings

### Open/Closed Principle (OCP)
✅ **Open for extension, closed for modification**

- Add new face detection models without changing existing code (Factory)
- Add new event handlers without modifying event publisher
- Add new API routes without modifying existing routes

### Liskov Substitution Principle (LSP)
✅ **Subtypes must be substitutable for their base types**

- Any `IFaceDetector` implementation can replace another
- Any `IEmbeddingRepository` implementation can replace another
- Interface contracts are strictly followed

### Interface Segregation Principle (ISP)
✅ **No client should depend on methods it doesn't use**

- Small, focused interfaces: `IFaceDetector`, `IEmbeddingExtractor`
- Separate interfaces for different concerns
- 23 small interfaces vs 1 large interface

### Dependency Inversion Principle (DIP)
✅ **Depend on abstractions, not concretions**

- Use cases depend on `IFaceDetector`, not `DeepFaceDetector`
- Application layer depends on interfaces, not implementations
- All dependencies point inward toward domain

---

## Domain-Driven Design

### Entities
**Objects with identity that persist over time**

```python
@dataclass
class FaceEmbedding:
    """Entity representing a biometric template"""
    user_id: str  # Identity
    vector: np.ndarray
    quality_score: float
```

### Value Objects
**Immutable objects defined by their attributes**

```python
@dataclass(frozen=True)
class FaceDetectionResult:
    """Value object representing detection result"""
    bounding_box: BoundingBox
    confidence: float
    landmarks: List[Point]
```

### Aggregates
**Cluster of entities treated as a single unit**

```python
class ProctorSession:
    """Aggregate root for proctoring"""
    def __init__(self, session_id: str, user_id: str):
        self._session_id = session_id
        self._user_id = user_id
        self._incidents = []  # Aggregate entities

    def add_incident(self, incident: ProctorIncident):
        # Business rule enforcement
        self._incidents.append(incident)
        self._update_risk_score()
```

### Domain Services
**Operations that don't naturally fit into entities**

```python
class EmbeddingFusionService:
    """Domain service for combining multiple embeddings"""
    def fuse_embeddings(
        self,
        embeddings: List[np.ndarray],
        quality_scores: List[float],
    ) -> np.ndarray:
        # Complex business logic
        return quality_weighted_average(embeddings, quality_scores)
```

---

## Event-Driven Architecture

### Domain Events

Events represent facts about things that have happened:

```python
@dataclass(frozen=True)
class FaceEnrolledEvent(DomainEvent):
    user_id: str
    quality_score: float
    occurred_at: datetime = field(default_factory=datetime.utcnow)
```

### Event Flow

```
1. Use Case executes business logic
   ↓
2. Domain event is created
   ↓
3. Event is published to EventBus
   ↓
4. Multiple handlers process event independently
   ↓
5. Side effects: emails, webhooks, analytics, etc.
```

### Benefits

- **Loose Coupling**: Producers don't know about consumers
- **Scalability**: Handlers can run asynchronously
- **Extensibility**: Add new handlers without changing existing code
- **Audit Trail**: Events provide complete history

---

## CQRS Pattern

### Commands (Write Operations)

```python
@dataclass(frozen=True)
class EnrollFaceCommand(Command):
    user_id: str
    image_path: str
    tenant_id: Optional[str] = None

class EnrollFaceCommandHandler(CommandHandler[EnrollFaceCommand, FaceEmbedding]):
    async def handle(self, command: EnrollFaceCommand) -> FaceEmbedding:
        # Execute write operation
        ...
```

### Queries (Read Operations)

```python
@dataclass(frozen=True)
class GetUserEmbeddingQuery(Query):
    user_id: str
    tenant_id: Optional[str] = None

class GetUserEmbeddingQueryHandler(QueryHandler[GetUserEmbeddingQuery, FaceEmbedding]):
    async def handle(self, query: GetUserEmbeddingQuery) -> FaceEmbedding:
        # Execute read operation
        ...
```

### Benefits

- **Separation of Concerns**: Read and write models can evolve independently
- **Performance Optimization**: Optimize reads and writes separately
- **Scalability**: Scale read and write sides independently
- **Clarity**: Clear distinction between commands and queries

---

## Dependency Injection

### Container (`app/core/container.py`)

Central registry for dependency creation:

```python
@lru_cache()
def get_face_detector() -> IFaceDetector:
    return FaceDetectorFactory.create(
        detector_type=settings.FACE_DETECTION_BACKEND
    )

@lru_cache()
def get_embedding_repository() -> IEmbeddingRepository:
    return PgVectorEmbeddingRepository(
        database_url=settings.DATABASE_URL
    )

def get_enroll_face_use_case() -> EnrollFaceUseCase:
    return EnrollFaceUseCase(
        detector=get_face_detector(),
        extractor=get_embedding_extractor(),
        repository=get_embedding_repository(),
    )
```

### Benefits

- **Testability**: Easy to swap real implementations with mocks
- **Flexibility**: Change implementations via configuration
- **Lifetime Management**: Singletons via `@lru_cache()`
- **Decoupling**: No hard dependencies on concrete classes

---

## Testing Strategy

### Unit Tests (Domain Layer)

Test business logic in isolation:

```python
def test_face_embedding_creation():
    embedding = FaceEmbedding.create_new(
        user_id="123",
        vector=np.random.rand(512),
        quality_score=95.5,
    )
    assert embedding.user_id == "123"
    assert embedding.get_embedding_dimension() == 512
```

### Integration Tests (Application Layer)

Test use cases with mock dependencies:

```python
async def test_enroll_face_use_case():
    # Arrange
    mock_detector = Mock(spec=IFaceDetector)
    mock_repository = Mock(spec=IEmbeddingRepository)
    use_case = EnrollFaceUseCase(
        detector=mock_detector,
        repository=mock_repository,
    )

    # Act
    result = await use_case.execute("123", "/path/to/image.jpg")

    # Assert
    mock_detector.detect.assert_called_once()
    mock_repository.save.assert_called_once()
```

### End-to-End Tests (API Layer)

Test complete API flows:

```python
async def test_enrollment_api(test_client):
    response = await test_client.post(
        "/api/v1/enroll",
        data={"user_id": "123"},
        files={"file": open("test.jpg", "rb")},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
```

---

## Deployment Architecture

### Docker Compose Services

```yaml
services:
  postgres:    # Database with pgvector
  redis:       # Cache and event bus
  api:         # Main application
  prometheus:  # Metrics collection
  grafana:     # Metrics visualization
```

### Kubernetes Deployment

```
┌─────────────────────────────────────────────┐
│            Ingress (Load Balancer)          │
└────────────────┬────────────────────────────┘
                 │
        ┌────────▼────────┐
        │   API Service   │
        └────────┬────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
┌───▼───┐   ┌───▼───┐   ┌───▼───┐
│ Pod 1 │   │ Pod 2 │   │ Pod 3 │  (HPA: 1-10 replicas)
└───┬───┘   └───┬───┘   └───┬───┘
    │            │            │
    └────────────┼────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
┌───▼────────┐  │  ┌─────────▼───┐
│ PostgreSQL │  │  │    Redis    │
│ (Stateful) │  │  │  (Stateful) │
└────────────┘  │  └─────────────┘
                │
        ┌───────▼────────┐
        │  Prometheus    │
        │  (Monitoring)  │
        └────────────────┘
```

---

## Conclusion

This architecture ensures:

✅ **Maintainability**: Clear separation of concerns
✅ **Testability**: Easy to test with mocks
✅ **Flexibility**: Easy to swap implementations
✅ **Scalability**: Horizontally scalable
✅ **Security**: Layered security at each level
✅ **Performance**: Optimized with caching and async operations

The hexagonal architecture makes the codebase resilient to change and easy to extend with new features.
