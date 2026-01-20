# Biometric Processor - Complete Implementation Plan

## Overview

| Attribute | Value |
|-----------|-------|
| **Module** | Biometric Processor |
| **Technology** | FastAPI, Python 3.11+ |
| **Architecture** | Clean Architecture (Domain/Application/Infrastructure/API) |
| **Current Completion** | 85% |
| **Target Completion** | 100% |
| **Port** | 8001 |

## Purpose

AI/ML microservice for biometric authentication. Provides:
- Face enrollment and verification
- Face search (1:N identification)
- Liveness detection (passive + active)
- Quality assessment
- Demographics analysis
- Facial landmarks detection
- Document/card type detection
- Real-time proctoring with WebSocket

---

## External Dependencies

### Services This Module Needs
| Service | URL | Purpose |
|---------|-----|---------|
| PostgreSQL | `localhost:5432` | Store face embeddings (pgvector) |
| Redis | `localhost:6379` | Cache, rate limiting, event bus |

### Services That Call This Module
| Client | Endpoints Used |
|--------|----------------|
| Identity Core API | `/api/v1/enroll`, `/api/v1/verify`, `/api/v1/liveness` |
| Mobile Apps (direct) | `/api/v1/enroll`, `/api/v1/verify`, `/api/v1/liveness` |

---

## Current Architecture

```
app/
├── domain/                      # Business logic (NO dependencies)
│   ├── entities/               # 18 domain models
│   ├── interfaces/             # 22 port interfaces
│   ├── exceptions/             # Sealed error hierarchy
│   └── services/               # Domain services
├── application/                 # Use cases
│   ├── use_cases/              # 18+ use case implementations
│   └── services/               # Application services
├── infrastructure/              # External adapters
│   ├── ml/                     # ML model implementations
│   ├── persistence/            # PostgreSQL + pgvector
│   ├── caching/                # LRU + Redis cache
│   ├── async_execution/        # Thread pool for ML
│   ├── messaging/              # Redis event bus
│   └── rate_limit/             # Rate limiting storage
├── api/                         # API layer
│   ├── routes/                 # 15+ endpoint routers
│   ├── schemas/                # Pydantic models
│   ├── middleware/             # Auth, CORS, errors, metrics
│   └── websocket/              # Real-time streaming
└── core/                        # Configuration
    ├── config.py               # Pydantic settings
    ├── container.py            # DI factory
    └── metrics/                # Prometheus
```

---

## API Endpoints

### Core Biometric
```
POST /api/v1/enroll              # Face enrollment
POST /api/v1/verify              # Face verification (1:1)
POST /api/v1/search              # Face search (1:N)
POST /api/v1/liveness            # Liveness detection
GET  /api/v1/enrollments/{id}    # Get enrollment
DELETE /api/v1/enrollments/{id}  # Delete enrollment
```

### Analysis
```
POST /api/v1/quality/analyze     # Image quality assessment
POST /api/v1/demographics        # Age/gender/emotion
POST /api/v1/landmarks           # 468-point facial landmarks
POST /api/v1/faces/detect-all    # Detect all faces in image
```

### Card Detection
```
POST /api/v1/card-type/detect-live  # Detect card type (YOLO)
```

### Batch Operations
```
POST /api/v1/batch/enroll        # Batch enrollment
POST /api/v1/batch/verify        # Batch verification
```

### Proctoring
```
POST /api/v1/proctoring/sessions           # Create session
GET  /api/v1/proctoring/sessions/{id}      # Get session
POST /api/v1/proctoring/sessions/{id}/start # Start session
POST /api/v1/proctoring/sessions/{id}/end   # End session
POST /api/v1/proctoring/sessions/{id}/frame # Submit frame
GET  /api/v1/proctoring/sessions/{id}/incidents # Get incidents
WS   /ws/proctoring/{session_id}           # WebSocket streaming
```

### Admin
```
GET  /api/v1/embeddings/export   # Export embeddings
POST /api/v1/embeddings/import   # Import embeddings
GET  /api/v1/similarity-matrix   # NxN comparison
```

### Webhooks
```
POST /api/v1/webhooks            # Register webhook
GET  /api/v1/webhooks            # List webhooks
DELETE /api/v1/webhooks/{id}     # Delete webhook
```

### Health & Metrics
```
GET /health                      # Health check
GET /metrics                     # Prometheus metrics
GET /docs                        # Swagger UI
```

---

## Implementation Phases

### PHASE 1: GPU Support (Priority: HIGH)

#### Task 1.1: Create GPU-enabled Dockerfile
**File**: `Dockerfile.gpu`

```dockerfile
# GPU-enabled Dockerfile
FROM nvidia/cuda:12.2-cudnn8-runtime-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.11 as default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

WORKDIR /app

# Install Python dependencies
COPY requirements-gpu.txt .
RUN pip3 install --no-cache-dir -r requirements-gpu.txt

# Copy application
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY pyproject.toml .

# Environment
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility
ENV TF_FORCE_GPU_ALLOW_GROWTH=true
ENV CUDA_VISIBLE_DEVICES=0
ENV USE_GPU=true

EXPOSE 8001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "4"]
```

#### Task 1.2: Create GPU Requirements
**File**: `requirements-gpu.txt`

```txt
# Core
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3
pydantic-settings==2.1.0

# ML - GPU versions
tensorflow==2.15.0
# tensorflow will auto-detect CUDA
torch==2.1.0+cu121
torchvision==0.16.0+cu121
--extra-index-url https://download.pytorch.org/whl/cu121

# Face Recognition
deepface==0.0.79
opencv-python-headless==4.9.0.80
mediapipe==0.10.9

# ONNX with GPU
onnxruntime-gpu==1.16.3

# Database
asyncpg==0.29.0
sqlalchemy[asyncio]==2.0.25
pgvector==0.2.4
alembic==1.13.1

# Redis
redis==5.0.1

# Utils
python-multipart==0.0.6
aiofiles==23.2.1
pillow==10.2.0
numpy==1.26.3

# Monitoring
prometheus-client==0.19.0
structlog==24.1.0

# Security
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
```

#### Task 1.3: Create GPU Configuration Module
**File**: `app/core/gpu_config.py`

```python
"""GPU configuration and detection module."""
import os
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GPUInfo:
    """GPU information container."""
    available: bool
    device_count: int
    device_names: list[str]
    memory_total: list[int]  # MB per device
    cuda_version: Optional[str]


def detect_gpu() -> GPUInfo:
    """Detect available GPU devices."""
    try:
        import torch

        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            device_names = [torch.cuda.get_device_name(i) for i in range(device_count)]
            memory_total = [
                torch.cuda.get_device_properties(i).total_memory // (1024 * 1024)
                for i in range(device_count)
            ]
            cuda_version = torch.version.cuda

            logger.info(f"GPU detected: {device_count} device(s)")
            for i, name in enumerate(device_names):
                logger.info(f"  GPU {i}: {name} ({memory_total[i]} MB)")

            return GPUInfo(
                available=True,
                device_count=device_count,
                device_names=device_names,
                memory_total=memory_total,
                cuda_version=cuda_version
            )
    except ImportError:
        logger.warning("PyTorch not installed, GPU detection skipped")
    except Exception as e:
        logger.error(f"GPU detection failed: {e}")

    return GPUInfo(
        available=False,
        device_count=0,
        device_names=[],
        memory_total=[],
        cuda_version=None
    )


def configure_tensorflow_gpu():
    """Configure TensorFlow for GPU usage."""
    try:
        import tensorflow as tf

        gpus = tf.config.list_physical_devices('GPU')
        if gpus:
            for gpu in gpus:
                # Enable memory growth to avoid allocating all GPU memory
                tf.config.experimental.set_memory_growth(gpu, True)
            logger.info(f"TensorFlow configured for {len(gpus)} GPU(s)")
            return True
    except Exception as e:
        logger.error(f"TensorFlow GPU configuration failed: {e}")

    return False


def get_torch_device() -> str:
    """Get the best available PyTorch device."""
    import torch

    if torch.cuda.is_available():
        return "cuda:0"
    elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        return "mps"  # Apple Silicon
    return "cpu"


# Environment configuration
USE_GPU = os.getenv("USE_GPU", "true").lower() == "true"

# Initialize on import
GPU_INFO: Optional[GPUInfo] = None
TORCH_DEVICE: str = "cpu"

if USE_GPU:
    GPU_INFO = detect_gpu()
    if GPU_INFO.available:
        configure_tensorflow_gpu()
        TORCH_DEVICE = get_torch_device()
    else:
        logger.warning("GPU requested but not available, falling back to CPU")
else:
    logger.info("GPU disabled by configuration, using CPU")
```

#### Task 1.4: Update ML Implementations for GPU
**File**: `app/infrastructure/ml/deepface_extractor.py` (update)

```python
"""DeepFace embedding extractor with GPU support."""
import numpy as np
from typing import Optional
from deepface import DeepFace

from app.domain.interfaces import IEmbeddingExtractor
from app.domain.entities import FaceEmbedding
from app.core.gpu_config import GPU_INFO, TORCH_DEVICE


class DeepFaceEmbeddingExtractor(IEmbeddingExtractor):
    """Extract face embeddings using DeepFace with GPU acceleration."""

    def __init__(
        self,
        model_name: str = "Facenet512",
        detector_backend: str = "retinaface"
    ):
        self.model_name = model_name
        self.detector_backend = detector_backend
        self._model_loaded = False

        # Log device info
        if GPU_INFO and GPU_INFO.available:
            print(f"DeepFace using GPU: {GPU_INFO.device_names[0]}")
        else:
            print("DeepFace using CPU")

    def _warm_up(self):
        """Pre-load model to GPU memory."""
        if not self._model_loaded:
            # Create dummy image to trigger model loading
            dummy = np.zeros((224, 224, 3), dtype=np.uint8)
            try:
                DeepFace.represent(
                    dummy,
                    model_name=self.model_name,
                    detector_backend=self.detector_backend,
                    enforce_detection=False
                )
                self._model_loaded = True
            except Exception:
                pass

    async def extract(self, image: np.ndarray) -> FaceEmbedding:
        """Extract face embedding from image."""
        self._warm_up()

        result = DeepFace.represent(
            image,
            model_name=self.model_name,
            detector_backend=self.detector_backend,
            enforce_detection=True
        )

        if not result:
            raise ValueError("No face detected in image")

        embedding = np.array(result[0]["embedding"], dtype=np.float32)

        return FaceEmbedding(
            vector=embedding,
            model_name=self.model_name,
            dimension=len(embedding)
        )

    async def extract_batch(self, images: list[np.ndarray]) -> list[FaceEmbedding]:
        """Extract embeddings from multiple images (batch processing)."""
        # DeepFace doesn't support native batching, process sequentially
        # but leverage GPU parallelism within each extraction
        embeddings = []
        for image in images:
            embedding = await self.extract(image)
            embeddings.append(embedding)
        return embeddings
```

#### Task 1.5: Add GPU Metrics
**File**: `app/core/metrics/gpu_metrics.py`

```python
"""GPU metrics collection for Prometheus."""
import subprocess
from prometheus_client import Gauge, Info

# Metrics
gpu_memory_used = Gauge(
    'biometric_gpu_memory_used_bytes',
    'GPU memory currently used',
    ['gpu_id', 'gpu_name']
)

gpu_memory_total = Gauge(
    'biometric_gpu_memory_total_bytes',
    'Total GPU memory',
    ['gpu_id', 'gpu_name']
)

gpu_utilization = Gauge(
    'biometric_gpu_utilization_percent',
    'GPU compute utilization',
    ['gpu_id', 'gpu_name']
)

gpu_temperature = Gauge(
    'biometric_gpu_temperature_celsius',
    'GPU temperature',
    ['gpu_id', 'gpu_name']
)

gpu_info = Info('biometric_gpu', 'GPU information')


def collect_gpu_metrics():
    """Collect NVIDIA GPU metrics using nvidia-smi."""
    try:
        result = subprocess.run(
            [
                'nvidia-smi',
                '--query-gpu=index,name,memory.used,memory.total,utilization.gpu,temperature.gpu',
                '--format=csv,noheader,nounits'
            ],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            return

        for line in result.stdout.strip().split('\n'):
            if not line:
                continue

            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 6:
                continue

            idx, name, mem_used, mem_total, util, temp = parts

            gpu_memory_used.labels(gpu_id=idx, gpu_name=name).set(
                int(mem_used) * 1024 * 1024  # Convert MB to bytes
            )
            gpu_memory_total.labels(gpu_id=idx, gpu_name=name).set(
                int(mem_total) * 1024 * 1024
            )
            gpu_utilization.labels(gpu_id=idx, gpu_name=name).set(float(util))
            gpu_temperature.labels(gpu_id=idx, gpu_name=name).set(float(temp))

    except FileNotFoundError:
        pass  # nvidia-smi not available
    except subprocess.TimeoutExpired:
        pass
    except Exception as e:
        print(f"GPU metrics collection failed: {e}")


def setup_gpu_info():
    """Set static GPU information."""
    from app.core.gpu_config import GPU_INFO

    if GPU_INFO and GPU_INFO.available:
        gpu_info.info({
            'cuda_version': GPU_INFO.cuda_version or 'unknown',
            'device_count': str(GPU_INFO.device_count),
            'devices': ', '.join(GPU_INFO.device_names)
        })
```

---

### PHASE 2: JWT Authentication Integration (Priority: HIGH)

#### Task 2.1: Create JWT Authentication Middleware
**File**: `app/api/middleware/jwt_auth.py`

```python
"""JWT authentication middleware for Identity Core API integration."""
from typing import Optional
from datetime import datetime
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from app.core.config import settings


security = HTTPBearer(auto_error=False)


class JWTPayload:
    """Decoded JWT payload."""

    def __init__(self, payload: dict):
        self.user_id: str = payload.get("sub", "")
        self.email: str = payload.get("email", "")
        self.tenant_id: str = payload.get("tenant_id", "")
        self.roles: list[str] = payload.get("roles", [])
        self.permissions: list[str] = payload.get("permissions", [])
        self.exp: int = payload.get("exp", 0)
        self.iat: int = payload.get("iat", 0)

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow().timestamp() > self.exp

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def is_admin(self) -> bool:
        return self.has_role("ADMIN") or self.has_role("SUPER_ADMIN")


class AuthContext:
    """Authentication context for the current request."""

    def __init__(
        self,
        authenticated: bool = False,
        auth_type: str = "none",
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        email: Optional[str] = None,
        roles: list[str] = None,
        permissions: list[str] = None,
        api_key_id: Optional[str] = None
    ):
        self.authenticated = authenticated
        self.auth_type = auth_type  # "jwt", "api_key", or "none"
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.email = email
        self.roles = roles or []
        self.permissions = permissions or []
        self.api_key_id = api_key_id

    def require_permission(self, permission: str):
        """Raise 403 if user doesn't have permission."""
        if permission not in self.permissions and "SUPER_ADMIN" not in self.roles:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {permission} required"
            )

    def require_role(self, role: str):
        """Raise 403 if user doesn't have role."""
        if role not in self.roles and "SUPER_ADMIN" not in self.roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role required: {role}"
            )


async def get_auth_context(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> AuthContext:
    """
    Extract authentication context from request.

    Supports:
    - JWT Bearer token (from Identity Core API)
    - API Key (X-API-Key header)
    - No authentication (for public endpoints)
    """
    # Check for API key first
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return await _validate_api_key(api_key)

    # Check for JWT token
    if credentials:
        return await _validate_jwt(credentials.credentials)

    # No authentication
    return AuthContext(authenticated=False)


async def _validate_jwt(token: str) -> AuthContext:
    """Validate JWT token from Identity Core API."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )

        jwt_payload = JWTPayload(payload)

        if jwt_payload.is_expired:
            raise HTTPException(status_code=401, detail="Token expired")

        return AuthContext(
            authenticated=True,
            auth_type="jwt",
            user_id=jwt_payload.user_id,
            tenant_id=jwt_payload.tenant_id,
            email=jwt_payload.email,
            roles=jwt_payload.roles,
            permissions=jwt_payload.permissions
        )

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


async def _validate_api_key(api_key: str) -> AuthContext:
    """Validate API key."""
    from app.infrastructure.persistence.api_key_repository import ApiKeyRepository

    repo = ApiKeyRepository()
    api_key_data = await repo.validate_key(api_key)

    if not api_key_data:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if api_key_data.is_expired:
        raise HTTPException(status_code=401, detail="API key expired")

    return AuthContext(
        authenticated=True,
        auth_type="api_key",
        tenant_id=str(api_key_data.tenant_id),
        permissions=api_key_data.scopes,
        api_key_id=str(api_key_data.id)
    )


def require_auth(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    """Dependency that requires authentication."""
    if not auth.authenticated:
        raise HTTPException(status_code=401, detail="Authentication required")
    return auth


def require_permission(permission: str):
    """Dependency factory that requires specific permission."""
    def _require(auth: AuthContext = Depends(require_auth)) -> AuthContext:
        auth.require_permission(permission)
        return auth
    return _require


def require_role(role: str):
    """Dependency factory that requires specific role."""
    def _require(auth: AuthContext = Depends(require_auth)) -> AuthContext:
        auth.require_role(role)
        return auth
    return _require
```

#### Task 2.2: Update Settings for JWT
**File**: `app/core/config.py` (add to existing)

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # JWT Configuration (must match Identity Core API)
    JWT_SECRET: str = Field(default="", description="JWT secret key")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    JWT_ENABLED: bool = Field(default=True, description="Enable JWT authentication")

    # API Key Configuration
    API_KEY_ENABLED: bool = Field(default=True, description="Enable API key authentication")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

#### Task 2.3: Apply Auth to Routes
**File**: `app/api/routes/enrollment.py` (example update)

```python
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from app.api.middleware.jwt_auth import (
    AuthContext, require_auth, require_permission, get_auth_context
)

router = APIRouter(prefix="/api/v1", tags=["enrollment"])


@router.post("/enroll")
async def enroll_face(
    user_id: str = Form(...),
    image: UploadFile = File(...),
    auth: AuthContext = Depends(require_auth)
):
    """
    Enroll a face for a user.

    Requires authentication.
    Users can only enroll themselves unless they have 'biometric:enroll' permission.
    """
    # Authorization check
    if auth.auth_type == "jwt":
        # JWT users can only enroll themselves unless admin
        if user_id != auth.user_id and not auth.has_permission("biometric:enroll"):
            raise HTTPException(
                status_code=403,
                detail="Cannot enroll other users without permission"
            )

    # Use tenant from auth context
    tenant_id = auth.tenant_id

    # Proceed with enrollment...
    image_bytes = await image.read()

    result = await enrollment_use_case.execute(
        user_id=user_id,
        tenant_id=tenant_id,
        image_data=image_bytes
    )

    return result


@router.post("/verify")
async def verify_face(
    user_id: str = Form(...),
    image: UploadFile = File(...),
    auth: AuthContext = Depends(require_permission("biometric:verify"))
):
    """
    Verify a face against enrolled data.

    Requires 'biometric:verify' permission.
    """
    image_bytes = await image.read()

    result = await verification_use_case.execute(
        user_id=user_id,
        tenant_id=auth.tenant_id,
        image_data=image_bytes
    )

    return result


@router.delete("/enrollments/{user_id}")
async def delete_enrollment(
    user_id: str,
    auth: AuthContext = Depends(require_auth)
):
    """
    Delete a user's biometric enrollment.

    Users can delete their own enrollment.
    Admins can delete any enrollment with 'biometric:delete' permission.
    """
    if auth.auth_type == "jwt":
        if user_id != auth.user_id and not auth.has_permission("biometric:delete"):
            raise HTTPException(
                status_code=403,
                detail="Cannot delete other users' enrollments"
            )

    await enrollment_repository.delete(user_id, auth.tenant_id)

    return {"message": "Enrollment deleted successfully"}
```

---

### PHASE 3: Distributed Redis Caching (Priority: HIGH)

#### Task 3.1: Create Redis Embedding Cache
**File**: `app/infrastructure/caching/redis_embedding_cache.py`

```python
"""Redis-based distributed cache for face embeddings."""
import json
import hashlib
from typing import Optional
import numpy as np
import redis.asyncio as redis

from app.core.config import settings


class RedisEmbeddingCache:
    """
    Distributed cache for face embeddings using Redis.

    Features:
    - Image hash-based caching
    - TTL-based expiration
    - Async operations
    - Serialization of numpy arrays
    """

    def __init__(
        self,
        redis_url: str = None,
        embedding_ttl: int = 3600,      # 1 hour for embeddings
        verification_ttl: int = 60,      # 1 minute for verification results
        prefix: str = "biometric"
    ):
        self.redis_url = redis_url or settings.REDIS_URL
        self.embedding_ttl = embedding_ttl
        self.verification_ttl = verification_ttl
        self.prefix = prefix
        self._redis: Optional[redis.Redis] = None

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False  # We need bytes for numpy
            )
        return self._redis

    @staticmethod
    def hash_image(image_data: bytes) -> str:
        """Generate SHA-256 hash of image bytes."""
        return hashlib.sha256(image_data).hexdigest()

    def _embedding_key(self, image_hash: str, model: str) -> str:
        """Generate cache key for embedding."""
        return f"{self.prefix}:embedding:{model}:{image_hash}"

    def _verification_key(self, user_id: str, image_hash: str) -> str:
        """Generate cache key for verification result."""
        return f"{self.prefix}:verify:{user_id}:{image_hash}"

    def _serialize_embedding(self, embedding: np.ndarray) -> bytes:
        """Serialize numpy array to bytes."""
        return json.dumps(embedding.tolist()).encode('utf-8')

    def _deserialize_embedding(self, data: bytes) -> np.ndarray:
        """Deserialize bytes to numpy array."""
        return np.array(json.loads(data.decode('utf-8')), dtype=np.float32)

    async def get_embedding(
        self,
        image_hash: str,
        model: str = "Facenet512"
    ) -> Optional[np.ndarray]:
        """
        Retrieve cached embedding by image hash.

        Returns None if not found or expired.
        """
        r = await self._get_redis()
        key = self._embedding_key(image_hash, model)

        data = await r.get(key)
        if data:
            return self._deserialize_embedding(data)
        return None

    async def set_embedding(
        self,
        image_hash: str,
        embedding: np.ndarray,
        model: str = "Facenet512",
        ttl: int = None
    ):
        """Cache embedding with TTL."""
        r = await self._get_redis()
        key = self._embedding_key(image_hash, model)
        ttl = ttl or self.embedding_ttl

        data = self._serialize_embedding(embedding)
        await r.setex(key, ttl, data)

    async def get_verification_result(
        self,
        user_id: str,
        image_hash: str
    ) -> Optional[dict]:
        """Retrieve cached verification result."""
        r = await self._get_redis()
        key = self._verification_key(user_id, image_hash)

        data = await r.get(key)
        if data:
            return json.loads(data.decode('utf-8'))
        return None

    async def set_verification_result(
        self,
        user_id: str,
        image_hash: str,
        result: dict,
        ttl: int = None
    ):
        """Cache verification result with short TTL."""
        r = await self._get_redis()
        key = self._verification_key(user_id, image_hash)
        ttl = ttl or self.verification_ttl

        data = json.dumps(result).encode('utf-8')
        await r.setex(key, ttl, data)

    async def invalidate_user_cache(self, user_id: str):
        """Invalidate all cache entries for a user."""
        r = await self._get_redis()
        pattern = f"{self.prefix}:verify:{user_id}:*"

        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match=pattern, count=100)
            if keys:
                await r.delete(*keys)
            if cursor == 0:
                break

    async def get_stats(self) -> dict:
        """Get cache statistics."""
        r = await self._get_redis()
        info = await r.info("stats")

        return {
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0),
            "hit_rate": (
                info.get("keyspace_hits", 0) /
                max(1, info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0))
            )
        }

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None


# Global cache instance
_cache: Optional[RedisEmbeddingCache] = None


def get_embedding_cache() -> RedisEmbeddingCache:
    """Get global cache instance."""
    global _cache
    if _cache is None:
        _cache = RedisEmbeddingCache()
    return _cache
```

#### Task 3.2: Integrate Cache into Use Cases
**File**: `app/application/use_cases/verify_face_use_case.py` (update)

```python
"""Face verification use case with caching."""
from typing import Optional
import numpy as np

from app.domain.interfaces import (
    IEmbeddingExtractor,
    IEmbeddingRepository,
    ISimilarityCalculator
)
from app.domain.entities import VerificationResult
from app.infrastructure.caching.redis_embedding_cache import (
    RedisEmbeddingCache,
    get_embedding_cache
)


class VerifyFaceUseCase:
    """
    Verify a face against enrolled data.

    Uses caching to avoid redundant:
    - Embedding extraction for the same image
    - Verification for the same user/image pair
    """

    def __init__(
        self,
        embedding_extractor: IEmbeddingExtractor,
        embedding_repository: IEmbeddingRepository,
        similarity_calculator: ISimilarityCalculator,
        cache: Optional[RedisEmbeddingCache] = None
    ):
        self.extractor = embedding_extractor
        self.repository = embedding_repository
        self.similarity = similarity_calculator
        self.cache = cache or get_embedding_cache()

    async def execute(
        self,
        user_id: str,
        tenant_id: str,
        image_data: bytes,
        threshold: float = 0.7
    ) -> VerificationResult:
        """
        Verify face against enrolled embedding.

        Args:
            user_id: User to verify against
            tenant_id: Tenant ID for multi-tenancy
            image_data: Face image bytes
            threshold: Similarity threshold (0-1)

        Returns:
            VerificationResult with verified status and confidence
        """
        # Hash image for caching
        image_hash = self.cache.hash_image(image_data)

        # Check for cached verification result
        cached_result = await self.cache.get_verification_result(user_id, image_hash)
        if cached_result:
            return VerificationResult(**cached_result)

        # Try to get cached embedding
        probe_embedding = await self.cache.get_embedding(image_hash)

        if probe_embedding is None:
            # Extract embedding from image
            image = self._decode_image(image_data)
            embedding_result = await self.extractor.extract(image)
            probe_embedding = embedding_result.vector

            # Cache the embedding
            await self.cache.set_embedding(image_hash, probe_embedding)

        # Get enrolled embedding from database
        enrolled = await self.repository.get_by_user_id(user_id, tenant_id)

        if enrolled is None:
            result = VerificationResult(
                verified=False,
                confidence=0.0,
                user_id=user_id,
                message="User not enrolled"
            )
        else:
            # Calculate similarity
            similarity = await self.similarity.calculate(
                probe_embedding,
                enrolled.embedding
            )

            result = VerificationResult(
                verified=similarity >= threshold,
                confidence=float(similarity),
                user_id=user_id,
                message="Verification successful" if similarity >= threshold else "Face not matched"
            )

        # Cache the result
        await self.cache.set_verification_result(
            user_id,
            image_hash,
            result.dict()
        )

        return result

    def _decode_image(self, image_data: bytes) -> np.ndarray:
        """Decode image bytes to numpy array."""
        import cv2
        import numpy as np

        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            raise ValueError("Failed to decode image")

        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
```

---

### PHASE 4: Model Quantization (Priority: MEDIUM)

#### Task 4.1: Create Quantization Utilities
**File**: `app/infrastructure/ml/quantization.py`

```python
"""Model quantization utilities for faster inference."""
import os
from pathlib import Path
from typing import List, Optional
import numpy as np

import tensorflow as tf
import onnxruntime as ort


class ModelQuantizer:
    """
    Quantize TensorFlow and ONNX models to INT8 for faster inference.

    INT8 quantization provides:
    - 3-4x faster inference on CPU
    - 2x faster inference on GPU
    - 4x smaller model size
    """

    def __init__(self, models_dir: Path):
        self.models_dir = models_dir
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def quantize_tensorflow_model(
        self,
        model_path: str,
        output_name: str,
        calibration_data: List[np.ndarray],
        input_shape: tuple = (1, 224, 224, 3)
    ) -> Path:
        """
        Quantize a TensorFlow SavedModel to INT8 TFLite.

        Args:
            model_path: Path to SavedModel directory
            output_name: Name for output file
            calibration_data: Representative dataset for quantization
            input_shape: Model input shape

        Returns:
            Path to quantized model
        """
        # Load the model
        converter = tf.lite.TFLiteConverter.from_saved_model(model_path)

        # Enable quantization
        converter.optimizations = [tf.lite.Optimize.DEFAULT]

        # Set representative dataset for calibration
        def representative_dataset():
            for data in calibration_data[:100]:  # Use max 100 samples
                # Ensure correct shape and type
                sample = data.astype(np.float32)
                if len(sample.shape) == 3:
                    sample = np.expand_dims(sample, axis=0)
                yield [sample]

        converter.representative_dataset = representative_dataset

        # Full integer quantization
        converter.target_spec.supported_ops = [
            tf.lite.OpsSet.TFLITE_BUILTINS_INT8
        ]
        converter.inference_input_type = tf.int8
        converter.inference_output_type = tf.int8

        # Convert
        quantized_model = converter.convert()

        # Save
        output_path = self.models_dir / f"{output_name}_int8.tflite"
        output_path.write_bytes(quantized_model)

        print(f"Quantized model saved to {output_path}")
        print(f"Original size: {os.path.getsize(model_path) / 1024 / 1024:.2f} MB")
        print(f"Quantized size: {len(quantized_model) / 1024 / 1024:.2f} MB")

        return output_path

    def load_quantized_tflite(self, model_path: Path) -> tf.lite.Interpreter:
        """Load a quantized TFLite model."""
        interpreter = tf.lite.Interpreter(model_path=str(model_path))
        interpreter.allocate_tensors()
        return interpreter

    def quantize_onnx_model(
        self,
        model_path: str,
        output_name: str,
        calibration_data: List[np.ndarray]
    ) -> Path:
        """
        Quantize an ONNX model to INT8.

        Uses ONNX Runtime quantization.
        """
        from onnxruntime.quantization import quantize_dynamic, QuantType

        output_path = self.models_dir / f"{output_name}_int8.onnx"

        quantize_dynamic(
            model_path,
            str(output_path),
            weight_type=QuantType.QInt8
        )

        return output_path

    def load_quantized_onnx(
        self,
        model_path: Path,
        use_gpu: bool = True
    ) -> ort.InferenceSession:
        """Load a quantized ONNX model with optimizations."""
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )
        sess_options.intra_op_num_threads = 4

        providers = []
        if use_gpu:
            providers.append('CUDAExecutionProvider')
        providers.append('CPUExecutionProvider')

        return ort.InferenceSession(
            str(model_path),
            sess_options=sess_options,
            providers=providers
        )


class QuantizedEmbeddingExtractor:
    """Embedding extractor using quantized models."""

    def __init__(self, model_path: Path, use_gpu: bool = True):
        self.session = self._load_model(model_path, use_gpu)
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    def _load_model(self, model_path: Path, use_gpu: bool) -> ort.InferenceSession:
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )

        providers = []
        if use_gpu:
            providers.append('CUDAExecutionProvider')
        providers.append('CPUExecutionProvider')

        return ort.InferenceSession(
            str(model_path),
            sess_options=sess_options,
            providers=providers
        )

    def extract(self, image: np.ndarray) -> np.ndarray:
        """Extract embedding using quantized model."""
        # Preprocess
        input_data = self._preprocess(image)

        # Run inference
        outputs = self.session.run(
            [self.output_name],
            {self.input_name: input_data}
        )

        return outputs[0].flatten()

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for model input."""
        import cv2

        # Resize
        image = cv2.resize(image, (224, 224))

        # Normalize
        image = image.astype(np.float32) / 255.0

        # Add batch dimension
        return np.expand_dims(image, axis=0)
```

---

### PHASE 5: Batch Processing Optimization (Priority: MEDIUM)

#### Task 5.1: Create Batch Inference Processor
**File**: `app/infrastructure/ml/batch_processor.py`

```python
"""Batch inference processor for efficient ML operations."""
import asyncio
from typing import List, Callable, Awaitable, TypeVar, Generic
from dataclasses import dataclass, field
from collections import deque
import time
import numpy as np

T = TypeVar('T')
R = TypeVar('R')


@dataclass
class BatchRequest(Generic[T]):
    """A request waiting for batch processing."""
    data: T
    future: asyncio.Future = field(default_factory=asyncio.Future)
    timestamp: float = field(default_factory=time.time)


class BatchInferenceProcessor(Generic[T, R]):
    """
    Batches multiple inference requests for efficient processing.

    When multiple requests arrive within the batch window:
    1. Requests are queued
    2. When batch is full OR timeout occurs, process batch together
    3. Results are distributed to waiting requests

    Benefits:
    - Better GPU utilization
    - Reduced per-request overhead
    - Higher throughput
    """

    def __init__(
        self,
        process_batch: Callable[[List[T]], Awaitable[List[R]]],
        max_batch_size: int = 8,
        max_wait_time: float = 0.1,  # 100ms
        name: str = "batch_processor"
    ):
        self.process_batch = process_batch
        self.max_batch_size = max_batch_size
        self.max_wait_time = max_wait_time
        self.name = name

        self._queue: deque[BatchRequest[T]] = deque()
        self._lock = asyncio.Lock()
        self._processing = False
        self._background_task: asyncio.Task = None

    async def start(self):
        """Start the background batch processor."""
        if self._background_task is None:
            self._background_task = asyncio.create_task(self._background_processor())

    async def stop(self):
        """Stop the background batch processor."""
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
            self._background_task = None

    async def process(self, data: T) -> R:
        """
        Submit data for batch processing.

        Returns when the batch containing this request is processed.
        """
        request = BatchRequest(data=data)

        async with self._lock:
            self._queue.append(request)

            # If batch is full, process immediately
            if len(self._queue) >= self.max_batch_size:
                await self._process_batch()

        # Wait for result
        try:
            return await asyncio.wait_for(request.future, timeout=10.0)
        except asyncio.TimeoutError:
            raise RuntimeError(f"Batch processing timeout for {self.name}")

    async def _background_processor(self):
        """Background task that processes batches on timeout."""
        while True:
            await asyncio.sleep(self.max_wait_time)

            async with self._lock:
                if self._queue and not self._processing:
                    await self._process_batch()

    async def _process_batch(self):
        """Process all queued requests as a batch."""
        if self._processing or not self._queue:
            return

        self._processing = True

        try:
            # Collect batch
            batch_requests: List[BatchRequest[T]] = []
            while self._queue and len(batch_requests) < self.max_batch_size:
                batch_requests.append(self._queue.popleft())

            if not batch_requests:
                return

            # Extract data
            batch_data = [req.data for req in batch_requests]

            # Process batch
            try:
                results = await self.process_batch(batch_data)

                # Distribute results
                for request, result in zip(batch_requests, results):
                    if not request.future.done():
                        request.future.set_result(result)

            except Exception as e:
                # Propagate error to all waiting requests
                for request in batch_requests:
                    if not request.future.done():
                        request.future.set_exception(e)

        finally:
            self._processing = False

    def stats(self) -> dict:
        """Get processor statistics."""
        return {
            "queue_size": len(self._queue),
            "max_batch_size": self.max_batch_size,
            "max_wait_time": self.max_wait_time,
            "processing": self._processing
        }


# Example usage for face embedding extraction
class BatchEmbeddingExtractor:
    """Batch-optimized face embedding extractor."""

    def __init__(self, model, max_batch_size: int = 8):
        self.model = model
        self.processor = BatchInferenceProcessor(
            process_batch=self._extract_batch,
            max_batch_size=max_batch_size,
            name="embedding_extractor"
        )

    async def start(self):
        await self.processor.start()

    async def stop(self):
        await self.processor.stop()

    async def extract(self, image: np.ndarray) -> np.ndarray:
        """Extract embedding for single image (batched internally)."""
        return await self.processor.process(image)

    async def _extract_batch(self, images: List[np.ndarray]) -> List[np.ndarray]:
        """Process a batch of images."""
        # Stack images into batch
        batch = np.stack(images, axis=0)

        # Run model inference (single call for entire batch)
        embeddings = self.model.predict(batch)

        # Split back into list
        return [embeddings[i] for i in range(len(images))]
```

---

### PHASE 6: Audit Logging (Priority: MEDIUM)

#### Task 6.1: Create Audit Logger
**File**: `app/infrastructure/audit/audit_logger.py`

```python
"""Structured audit logging for compliance."""
import json
import logging
from datetime import datetime
from typing import Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

import structlog


class AuditAction(str, Enum):
    """Audit action types."""
    # Enrollment
    FACE_ENROLLED = "face_enrolled"
    FACE_ENROLLMENT_FAILED = "face_enrollment_failed"
    ENROLLMENT_DELETED = "enrollment_deleted"

    # Verification
    FACE_VERIFIED = "face_verified"
    FACE_VERIFICATION_FAILED = "face_verification_failed"

    # Search
    FACE_SEARCH = "face_search"
    FACE_SEARCH_MATCH = "face_search_match"

    # Liveness
    LIVENESS_CHECK_PASSED = "liveness_check_passed"
    LIVENESS_CHECK_FAILED = "liveness_check_failed"

    # Admin
    EMBEDDINGS_EXPORTED = "embeddings_exported"
    EMBEDDINGS_IMPORTED = "embeddings_imported"

    # Proctoring
    PROCTORING_SESSION_STARTED = "proctoring_session_started"
    PROCTORING_SESSION_ENDED = "proctoring_session_ended"
    PROCTORING_INCIDENT_DETECTED = "proctoring_incident_detected"


@dataclass
class AuditEntry:
    """Audit log entry."""
    timestamp: str
    action: str
    user_id: Optional[str]
    tenant_id: Optional[str]
    resource_type: str
    resource_id: Optional[str]
    success: bool
    ip_address: Optional[str]
    user_agent: Optional[str]
    request_id: Optional[str]
    details: dict
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class AuditLogger:
    """
    Audit logger for biometric operations.

    Logs to:
    - Structured log output (JSON)
    - Optionally to database or external service
    """

    def __init__(self):
        self.logger = structlog.get_logger("audit")

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
        details: dict = None,
        error_message: Optional[str] = None
    ):
        """Log an audit event."""
        entry = AuditEntry(
            timestamp=datetime.utcnow().isoformat(),
            action=action.value,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            details=details or {},
            error_message=error_message
        )

        log_method = self.logger.info if success else self.logger.warning
        log_method(
            "audit_event",
            **entry.to_dict()
        )

    def log_enrollment(
        self,
        user_id: str,
        tenant_id: str,
        success: bool,
        quality_score: Optional[float] = None,
        error: Optional[str] = None,
        **kwargs
    ):
        """Log face enrollment."""
        action = AuditAction.FACE_ENROLLED if success else AuditAction.FACE_ENROLLMENT_FAILED
        self.log(
            action=action,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type="enrollment",
            resource_id=user_id,
            success=success,
            details={"quality_score": quality_score} if quality_score else {},
            error_message=error,
            **kwargs
        )

    def log_verification(
        self,
        user_id: str,
        tenant_id: str,
        verified: bool,
        confidence: float,
        **kwargs
    ):
        """Log face verification."""
        action = AuditAction.FACE_VERIFIED if verified else AuditAction.FACE_VERIFICATION_FAILED
        self.log(
            action=action,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type="verification",
            resource_id=user_id,
            success=verified,
            details={"confidence": confidence},
            **kwargs
        )

    def log_liveness(
        self,
        user_id: str,
        tenant_id: str,
        is_live: bool,
        confidence: float,
        method: str,
        **kwargs
    ):
        """Log liveness check."""
        action = AuditAction.LIVENESS_CHECK_PASSED if is_live else AuditAction.LIVENESS_CHECK_FAILED
        self.log(
            action=action,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type="liveness",
            success=is_live,
            details={"confidence": confidence, "method": method},
            **kwargs
        )


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
```

---

### PHASE 7: Database Optimization (Priority: MEDIUM)

#### Task 7.1: Add Database Connection Pool Configuration
**File**: `app/infrastructure/persistence/database.py` (update)

```python
"""Database configuration with optimized connection pooling."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

from app.core.config import settings


def create_engine():
    """Create database engine with optimized settings."""

    # Connection pool settings
    pool_settings = {
        "pool_size": settings.DB_POOL_SIZE,           # Default: 20
        "max_overflow": settings.DB_MAX_OVERFLOW,     # Default: 10
        "pool_timeout": settings.DB_POOL_TIMEOUT,     # Default: 30
        "pool_recycle": settings.DB_POOL_RECYCLE,     # Default: 1800 (30 min)
        "pool_pre_ping": True,                        # Verify connections
    }

    # For testing, use NullPool (no connection pooling)
    if settings.TESTING:
        pool_settings = {"poolclass": NullPool}

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DB_ECHO,
        **pool_settings
    )

    return engine


engine = create_engine()

async_session = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_session() -> AsyncSession:
    """Get database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
```

#### Task 7.2: Add Vector Search Optimization
**File**: `app/infrastructure/persistence/embedding_repository.py` (update)

```python
"""Optimized embedding repository with pgvector."""
from typing import List, Optional, Tuple
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.interfaces import IEmbeddingRepository
from app.domain.entities import StoredEmbedding, SearchResult


class EmbeddingRepository(IEmbeddingRepository):
    """
    PostgreSQL + pgvector embedding repository.

    Optimizations:
    - IVFFlat index for approximate nearest neighbor search
    - Cosine similarity for normalized embeddings
    - Batch operations for bulk inserts
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self,
        embedding: list[float],
        tenant_id: str,
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[SearchResult]:
        """
        Search for similar faces using pgvector.

        Uses IVFFlat index for fast approximate search.
        """
        # Convert to pgvector format
        embedding_str = f"[{','.join(map(str, embedding))}]"

        query = text("""
            SELECT
                user_id,
                1 - (embedding <=> :embedding) as similarity,
                quality_score,
                created_at
            FROM face_embeddings
            WHERE tenant_id = :tenant_id
              AND is_active = true
              AND 1 - (embedding <=> :embedding) >= :threshold
            ORDER BY embedding <=> :embedding
            LIMIT :limit
        """)

        result = await self.session.execute(
            query,
            {
                "embedding": embedding_str,
                "tenant_id": tenant_id,
                "threshold": threshold,
                "limit": limit
            }
        )

        return [
            SearchResult(
                user_id=row.user_id,
                similarity=float(row.similarity),
                quality_score=float(row.quality_score),
                enrolled_at=row.created_at
            )
            for row in result.fetchall()
        ]

    async def bulk_insert(
        self,
        embeddings: List[Tuple[str, str, list[float], float]]
    ):
        """
        Bulk insert embeddings for better performance.

        Args:
            embeddings: List of (user_id, tenant_id, embedding, quality_score) tuples
        """
        if not embeddings:
            return

        # Build batch insert query
        values = []
        params = {}

        for i, (user_id, tenant_id, embedding, quality) in enumerate(embeddings):
            values.append(f"(:user_id_{i}, :tenant_id_{i}, :embedding_{i}, :quality_{i})")
            params[f"user_id_{i}"] = user_id
            params[f"tenant_id_{i}"] = tenant_id
            params[f"embedding_{i}"] = f"[{','.join(map(str, embedding))}]"
            params[f"quality_{i}"] = quality

        query = text(f"""
            INSERT INTO face_embeddings (user_id, tenant_id, embedding, quality_score)
            VALUES {', '.join(values)}
            ON CONFLICT (user_id, tenant_id)
            DO UPDATE SET
                embedding = EXCLUDED.embedding,
                quality_score = EXCLUDED.quality_score,
                updated_at = NOW()
        """)

        await self.session.execute(query, params)
        await self.session.commit()
```

#### Task 7.3: Add Database Migration for Indexes
**File**: `alembic/versions/20260120_add_performance_indexes.py`

```python
"""Add performance indexes for face embeddings.

Revision ID: 20260120_perf
Revises: previous_revision
Create Date: 2026-01-20
"""
from alembic import op


revision = '20260120_perf'
down_revision = 'previous_revision'


def upgrade():
    # Create IVFFlat index for vector similarity search
    # Lists = sqrt(num_rows), typically 100-1000 for production
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_embeddings_vector_ivfflat
        ON face_embeddings
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    # Composite index for tenant + user lookups
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_embeddings_tenant_user
        ON face_embeddings (tenant_id, user_id)
        WHERE is_active = true
    """)

    # Index for active embeddings
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_embeddings_active
        ON face_embeddings (tenant_id)
        WHERE is_active = true
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_embeddings_vector_ivfflat")
    op.execute("DROP INDEX IF EXISTS idx_embeddings_tenant_user")
    op.execute("DROP INDEX IF EXISTS idx_embeddings_active")
```

---

## Configuration

### Environment Variables (.env)
```env
# Database
DATABASE_URL=postgresql+asyncpg://fivucsas:password@localhost:5432/fivucsas
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=1800
DB_ECHO=false

# Redis
REDIS_URL=redis://:password@localhost:6379/0

# JWT (must match Identity Core API)
JWT_SECRET=your-256-bit-secret-key
JWT_ALGORITHM=HS256
JWT_ENABLED=true

# GPU
USE_GPU=true
CUDA_VISIBLE_DEVICES=0

# ML Models
MODEL_CACHE_DIR=/app/models
DEFAULT_FACE_MODEL=Facenet512
DEFAULT_DETECTOR=retinaface

# Performance
MAX_BATCH_SIZE=8
MAX_WORKERS=4

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=100

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Docker Compose (GPU)
```yaml
services:
  biometric-processor:
    build:
      context: .
      dockerfile: Dockerfile.gpu
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=postgresql+asyncpg://fivucsas:password@postgres:5432/fivucsas
      - REDIS_URL=redis://:password@redis:6379/0
      - JWT_SECRET=${JWT_SECRET}
      - USE_GPU=true
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    depends_on:
      - postgres
      - redis
```

---

## Completion Checklist

### Phase 1: GPU Support
- [ ] Create Dockerfile.gpu
- [ ] Create requirements-gpu.txt
- [ ] Implement gpu_config.py
- [ ] Update ML implementations for GPU
- [ ] Add GPU metrics collection
- [ ] Test on GPU hardware

### Phase 2: JWT Authentication
- [ ] Create JWT middleware
- [ ] Update settings for JWT
- [ ] Apply auth to all routes
- [ ] Test with Identity Core API tokens

### Phase 3: Redis Caching
- [ ] Create RedisEmbeddingCache
- [ ] Integrate into use cases
- [ ] Add cache invalidation
- [ ] Monitor cache hit rate

### Phase 4: Model Quantization
- [ ] Create quantization utilities
- [ ] Generate calibration dataset
- [ ] Quantize face models
- [ ] Benchmark quantized vs full precision

### Phase 5: Batch Processing
- [ ] Create BatchInferenceProcessor
- [ ] Create BatchEmbeddingExtractor
- [ ] Integrate into enrollment/verification
- [ ] Tune batch size and timeout

### Phase 6: Audit Logging
- [ ] Create AuditLogger
- [ ] Add audit logging to all operations
- [ ] Configure log retention
- [ ] Verify compliance requirements

### Phase 7: Database Optimization
- [ ] Configure connection pooling
- [ ] Add vector search indexes
- [ ] Implement bulk operations
- [ ] Benchmark query performance

---

## Performance Targets

| Metric | Current (CPU) | Target (GPU) |
|--------|---------------|--------------|
| Face detection | 200ms | 20ms |
| Embedding extraction | 500ms | 50ms |
| Verification (1:1) | 700ms | 100ms |
| Search (1:1000) | 800ms | 150ms |
| Liveness detection | 400ms | 80ms |
| **Total verification** | **1.5s** | **200ms** |

---

## Estimated Timeline

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Phase 1: GPU Support | 5 days | NVIDIA drivers, CUDA |
| Phase 2: JWT Auth | 2 days | Identity Core API |
| Phase 3: Redis Caching | 2 days | Redis server |
| Phase 4: Quantization | 3 days | Calibration data |
| Phase 5: Batch Processing | 2 days | None |
| Phase 6: Audit Logging | 2 days | None |
| Phase 7: Database | 2 days | PostgreSQL |
| **Total** | **18 days** | |
