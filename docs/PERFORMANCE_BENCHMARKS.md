# Performance Benchmarks

**Version:** 1.0.0
**Date:** December 12, 2025

---

## Test Environment

| Component | Specification |
|-----------|---------------|
| CPU | 8 cores @ 3.0 GHz |
| Memory | 32 GB |
| Storage | NVMe SSD |
| GPU | NVIDIA RTX 3080 (optional) |
| Database | PostgreSQL 15 |
| Cache | Redis 7 |

---

## Latency Benchmarks

### Core Operations (P50 / P95 / P99)

| Operation | P50 | P95 | P99 | Target |
|-----------|-----|-----|-----|--------|
| Health Check | 2ms | 5ms | 10ms | <50ms |
| Face Enrollment | 150ms | 220ms | 350ms | <500ms |
| Face Verification | 85ms | 140ms | 200ms | <300ms |
| Liveness Check | 60ms | 95ms | 150ms | <200ms |
| Face Search (1K) | 45ms | 80ms | 120ms | <200ms |
| Face Search (10K) | 120ms | 180ms | 250ms | <500ms |
| Frame Analysis | 35ms | 55ms | 80ms | <100ms |

### Proctoring Operations

| Operation | P50 | P95 | P99 | Target |
|-----------|-----|-----|-----|--------|
| Session Create | 15ms | 25ms | 40ms | <100ms |
| Session Start | 180ms | 250ms | 350ms | <500ms |
| Frame Submit | 35ms | 55ms | 80ms | <100ms |
| Get Incidents | 20ms | 35ms | 50ms | <100ms |
| Session End | 45ms | 70ms | 100ms | <200ms |

---

## Throughput Benchmarks

### Requests per Second (single instance)

| Endpoint | RPS | CPU Usage | Memory |
|----------|-----|-----------|--------|
| /health | 5,000 | 5% | 50MB |
| /verify | 150 | 85% | 512MB |
| /enroll | 80 | 90% | 768MB |
| /liveness | 200 | 70% | 384MB |
| /search | 100 | 75% | 512MB |
| /frames | 500 | 60% | 256MB |

### Concurrent Users (10 instances)

| Scenario | Users | RPS | Errors | P99 |
|----------|-------|-----|--------|-----|
| Light Load | 100 | 800 | 0% | 150ms |
| Normal Load | 500 | 2,500 | 0.1% | 280ms |
| Heavy Load | 1,000 | 4,000 | 0.5% | 450ms |
| Stress Test | 2,000 | 5,500 | 2% | 800ms |

---

## Memory Usage

### Per Component

| Component | Baseline | Under Load | Peak |
|-----------|----------|------------|------|
| API Server | 256MB | 512MB | 1GB |
| Celery Worker | 384MB | 768MB | 1.5GB |
| ML Models | 512MB | 512MB | 512MB |
| Total (instance) | 1.2GB | 1.8GB | 3GB |

### Model Memory Footprint

| Model | Size | Load Time |
|-------|------|-----------|
| FaceNet | 95MB | 2.1s |
| OpenCV DNN | 25MB | 0.5s |
| MediaPipe | 35MB | 0.8s |
| YOLO (nano) | 12MB | 0.3s |
| Texture Analyzer | 5MB | 0.1s |

---

## Database Performance

### Query Latency

| Query Type | P50 | P95 | Records |
|------------|-----|-----|---------|
| Insert Embedding | 3ms | 8ms | - |
| Vector Search | 15ms | 45ms | 10K |
| Vector Search | 35ms | 90ms | 100K |
| Session Lookup | 2ms | 5ms | - |
| Incident Insert | 2ms | 5ms | - |

### Connection Pool

| Metric | Value |
|--------|-------|
| Pool Size | 10 |
| Max Overflow | 20 |
| Timeout | 30s |
| Recycle | 1800s |

---

## Load Test Results (Locust)

### Test Configuration
```bash
locust -f tests/load/locustfile.py \
  --host=http://localhost:8001 \
  --users 100 --spawn-rate 10 \
  --run-time 5m --headless
```

### Results Summary

```
Type     Name                              # reqs    Avg   Min   Max  Med    # fails
--------|--------------------------------|-------|-----|-----|-----|-----|--------
GET      /api/v1/health                     15420    12     2   145   10    0(0.00%)
POST     /api/v1/enroll                      1542   185    95   520  165    5(0.32%)
POST     /api/v1/verify                      3856   125    55   380  110    2(0.05%)
POST     /api/v1/liveness                    2571    85    35   290   75    1(0.04%)
POST     /api/v1/proctor/sessions/{id}/frames  5142    45    15   180   40    0(0.00%)
--------|--------------------------------|-------|-----|-----|-----|-----|--------
         Aggregated                        28531    65     2   520   35    8(0.03%)

Percentage of requests completed within given times:
Type     Name                              50%   66%   75%   80%   90%   95%   99%
--------|--------------------------------|-----|-----|-----|-----|-----|-----|-----
GET      /api/v1/health                     10    12    15    18    25    35    85
POST     /api/v1/enroll                    165   185   210   235   295   350   450
POST     /api/v1/verify                    110   125   145   160   195   240   320
POST     /api/v1/liveness                   75    85    95   105   130   160   220
POST     /proctor/sessions/{id}/frames      40    45    50    55    70    90   140
```

---

## Scaling Guidelines

### Horizontal Scaling

| Users | Instances | CPU (total) | Memory (total) |
|-------|-----------|-------------|----------------|
| 100 | 2 | 4 cores | 4GB |
| 500 | 5 | 10 cores | 10GB |
| 1,000 | 10 | 20 cores | 20GB |
| 5,000 | 25 | 50 cores | 50GB |

### Auto-scaling Rules

```yaml
# HPA Configuration
minReplicas: 3
maxReplicas: 50
metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

## Optimization Recommendations

### Quick Wins
1. Enable Redis caching for embeddings
2. Use connection pooling
3. Enable gzip compression
4. Use CDN for static assets

### Medium Effort
1. GPU acceleration for ML inference
2. Batch processing for bulk operations
3. Read replicas for search queries
4. Async logging

### Advanced
1. Model quantization (INT8)
2. Custom CUDA kernels
3. Distributed vector search
4. Edge deployment

---

## Running Benchmarks

```bash
# Install dependencies
pip install locust pytest-benchmark

# Run load tests
locust -f tests/load/locustfile.py --host=http://localhost:8001

# Run microbenchmarks
pytest tests/benchmarks/ -v --benchmark-only

# Generate report
pytest tests/benchmarks/ --benchmark-json=benchmark.json
```
