# Performance Optimization Guide

**Date:** December 14, 2025
**Version:** 1.0.0
**Status:** Investigation Complete

---

## Executive Summary

After deep analysis of the codebase, I've identified **critical performance bottlenecks** and opportunities for significant performance improvements. The most impactful issues are:

| Priority | Issue | Impact | Effort |
|----------|-------|--------|--------|
| **CRITICAL** | CPU-bound ML ops blocking async loop | 10x latency | Medium |
| **CRITICAL** | Single uvicorn worker in Docker | 4x throughput loss | Low |
| **HIGH** | No Redis caching for embeddings | 50ms+ per lookup | Medium |
| **HIGH** | Merge conflicts in core files | System broken | Low |
| **MEDIUM** | No response compression | 30% bandwidth waste | Low |
| **MEDIUM** | Model loading not optimized | Cold start issues | Medium |

---

## Critical Issues

### 1. CPU-Bound ML Operations Blocking Async Event Loop

**Location:** `app/infrastructure/ml/extractors/deepface_extractor.py:70`

**Problem:**
```python
# CURRENT - BLOCKING
async def extract(self, face_image: np.ndarray) -> np.ndarray:
    # This call BLOCKS the async event loop!
    embedding_objs = DeepFace.represent(
        img_path=face_image,
        model_name=self._model_name,
        ...
    )
```

The `DeepFace.represent()` call is synchronous and CPU-intensive (50-200ms). When called inside an `async` function without offloading, it **blocks the entire event loop**, preventing other requests from being processed.

**Impact:**
- Under load, P99 latency increases dramatically
- Concurrent request handling is effectively serialized
- WebSocket connections may timeout

**Solution:**
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Create a thread pool for ML operations
_ml_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ml_")

async def extract(self, face_image: np.ndarray) -> np.ndarray:
    loop = asyncio.get_event_loop()

    # Offload CPU-bound work to thread pool
    embedding_objs = await loop.run_in_executor(
        _ml_executor,
        lambda: DeepFace.represent(
            img_path=face_image,
            model_name=self._model_name,
            detector_backend=self._detector_backend,
            enforce_detection=self._enforce_detection,
            align=True,
            normalization="base",
        )
    )
    # ... rest of processing
```

**Files to Update:**
- `app/infrastructure/ml/extractors/deepface_extractor.py`
- `app/infrastructure/ml/detectors/deepface_detector.py`
- `app/infrastructure/ml/quality/quality_assessor.py`
- `app/infrastructure/ml/liveness/*.py`
- `app/infrastructure/ml/demographics/deepface_demographics.py`
- `app/infrastructure/ml/landmarks/*.py`
- `app/infrastructure/ml/proctoring/*.py`

**Expected Improvement:** 5-10x better concurrent request handling

---

### 2. Single Uvicorn Worker in Production

**Location:** `Dockerfile:60`

**Problem:**
```dockerfile
# CURRENT - Single worker
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

Running with a single worker limits throughput to what one CPU core can handle.

**Solution:**
```dockerfile
# OPTION 1: Multiple uvicorn workers
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "4"]

# OPTION 2: Gunicorn with uvicorn workers (recommended for production)
CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8001"]
```

**For Kubernetes:** Use single worker per pod and scale horizontally with HPA.

**Expected Improvement:** 2-4x throughput on multi-core systems

---

### 3. Unresolved Merge Conflicts

**Location:**
- `app/core/container.py` (lines 53-69, 196-302, 632-644)
- `requirements.txt` (lines 12-34) - FIXED

**Problem:** Git merge conflicts prevent the application from starting.

**Solution:** Resolve conflicts by combining both upstream changes:

```python
# container.py needs to include BOTH:
# 1. Factory imports (demographics, landmarks, etc.)
# 2. Event bus components (RedisEventBus, EventPublisher, etc.)
```

---

## High Priority Optimizations

### 4. Add Redis Caching for Embeddings

**Problem:** Every verification/search requires database lookup even for recently accessed embeddings.

**Solution:** Add a caching layer:

```python
# app/infrastructure/cache/embedding_cache.py
import redis
import json
import numpy as np
from typing import Optional

class EmbeddingCache:
    def __init__(self, redis_client: redis.Redis, ttl: int = 3600):
        self._redis = redis_client
        self._ttl = ttl

    async def get(self, user_id: str, tenant_id: str = "default") -> Optional[np.ndarray]:
        key = f"embedding:{tenant_id}:{user_id}"
        data = await self._redis.get(key)
        if data:
            return np.frombuffer(data, dtype=np.float32)
        return None

    async def set(self, user_id: str, embedding: np.ndarray, tenant_id: str = "default"):
        key = f"embedding:{tenant_id}:{user_id}"
        await self._redis.setex(key, self._ttl, embedding.tobytes())

    async def invalidate(self, user_id: str, tenant_id: str = "default"):
        key = f"embedding:{tenant_id}:{user_id}"
        await self._redis.delete(key)
```

**Expected Improvement:** 10-50ms saved per cached lookup

---

### 5. Add Response Compression

**Problem:** API responses are uncompressed, wasting bandwidth.

**Solution:** Add GZip middleware:

```python
# app/main.py
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

**Expected Improvement:** 30-70% bandwidth reduction for JSON responses

---

## Medium Priority Optimizations

### 6. Optimize Model Loading

**Current State:** Models are loaded via `lru_cache` singletons at first use.

**Improvements:**

```python
# 1. Add model preloading in lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Preload ALL models in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(get_face_detector),
            executor.submit(get_embedding_extractor),
            executor.submit(get_quality_assessor),
            executor.submit(get_liveness_detector),
        ]
        for future in futures:
            future.result()  # Wait for completion

    yield

# 2. Add health check for model readiness
@app.get("/api/v1/health/ready")
async def readiness():
    models_ready = all([
        get_face_detector.cache_info().hits > 0 or get_face_detector.cache_info().currsize > 0,
        get_embedding_extractor.cache_info().currsize > 0,
    ])
    if not models_ready:
        raise HTTPException(503, "Models not ready")
    return {"status": "ready"}
```

---

### 7. Connection Pool Tuning

**Current Settings:**
```python
DATABASE_POOL_MIN_SIZE = 10
DATABASE_POOL_MAX_SIZE = 20
```

**Recommendations:**
```python
# For high-throughput scenarios
DATABASE_POOL_MIN_SIZE = 20
DATABASE_POOL_MAX_SIZE = 50

# Add connection health checks
pool_recycle = 1800  # Recycle connections every 30 minutes
pool_pre_ping = True  # Verify connection before use
```

---

### 8. Batch Processing with Multiprocessing

**Current:** Batch operations use asyncio but are still single-process.

**Solution for CPU-intensive batches:**
```python
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

# Use process pool for batch ML operations
_batch_executor = ProcessPoolExecutor(
    max_workers=multiprocessing.cpu_count(),
    mp_context=multiprocessing.get_context('spawn')
)
```

---

## Configuration Recommendations

### Production Environment Variables

```bash
# Workers and Concurrency
API_WORKERS=4
UVICORN_WORKERS=4

# Database
DATABASE_POOL_MIN_SIZE=20
DATABASE_POOL_MAX_SIZE=50

# Redis
REDIS_MAX_CONNECTIONS=20

# ML Thread Pool
ML_THREAD_POOL_SIZE=8

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_STORAGE=redis

# Caching
EMBEDDING_CACHE_ENABLED=true
EMBEDDING_CACHE_TTL=3600
```

### Kubernetes Resource Limits

```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "2000m"
```

---

## Performance Testing Commands

```bash
# Load test with Locust
locust -f tests/load/locustfile.py --host=http://localhost:8001 \
  --users 100 --spawn-rate 10 --run-time 5m

# Benchmark specific endpoint
ab -n 1000 -c 10 http://localhost:8001/api/v1/health

# Profile Python code
python -m cProfile -o profile.out -m uvicorn app.main:app
snakeviz profile.out
```

---

## Implementation Priority

### Week 1 (Critical)
1. Fix merge conflicts in `container.py`
2. Add `run_in_executor` for ML operations
3. Increase uvicorn workers

### Week 2 (High)
4. Add Redis embedding cache
5. Add response compression
6. Tune connection pools

### Week 3 (Medium)
7. Optimize model preloading
8. Add batch multiprocessing
9. Performance testing and tuning

---

## Monitoring Checklist

After implementing optimizations, monitor:

- [ ] P50/P95/P99 latency via Prometheus
- [ ] Request throughput (RPS)
- [ ] CPU utilization per worker
- [ ] Memory usage trends
- [ ] Database connection pool utilization
- [ ] Redis cache hit ratio
- [ ] Error rates

---

## Summary

The three most impactful changes are:

1. **Offload ML operations to thread pool** - Unblocks async event loop
2. **Run multiple uvicorn workers** - Utilizes multiple CPU cores
3. **Add Redis caching** - Reduces database load

These changes alone should provide **5-10x improvement** in concurrent request handling and **2-4x improvement** in overall throughput.

---

*Generated by performance analysis on December 14, 2025*
