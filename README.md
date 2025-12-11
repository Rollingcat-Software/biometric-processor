# Biometric Processor API

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.11+-yellow.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![DeepFace](https://img.shields.io/badge/DeepFace-AI-red.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Overview

**Biometric Processor API** is the AI/ML microservice of the **FIVUCSAS** (Face and Identity Verification Using Cloud-based SaaS) platform. Built with FastAPI and powered by DeepFace deep learning models, this service handles biometric operations including face enrollment, verification, search, liveness detection, and document card type detection.

This microservice is part of a larger biometric authentication ecosystem developed as an Engineering Project at Marmara University's Computer Engineering Department.

## Features

### Core Biometric Capabilities

| Feature | Status | Description |
|---------|--------|-------------|
| Face Enrollment | ✅ Complete | Register face embeddings with quality assessment |
| Face Verification (1:1) | ✅ Complete | Verify if two faces belong to the same person |
| Face Search (1:N) | ✅ Complete | Identify a person from enrolled faces |
| Batch Processing | ✅ Complete | Process multiple enrollment/verification requests |
| Liveness Detection | ✅ Complete | Passive texture-based anti-spoofing detection |
| Card Type Detection | ✅ Complete | YOLO-based document classification |
| Quality Assessment | ✅ Complete | Face image quality scoring and validation |

### Technical Features

- **Clean Architecture**: Domain-driven design with clear separation of concerns
- **Dependency Injection**: Fully injectable components for testability
- **Multiple Face Models**: Support for VGG-Face, Facenet, ArcFace, and more
- **Async Processing**: Non-blocking I/O for high throughput
- **Configurable Thresholds**: Environment-based configuration
- **Comprehensive Error Handling**: Domain-specific exceptions with proper HTTP mapping

## Architecture

The project follows **Clean Architecture** principles with four distinct layers:

```
biometric-processor/
├── app/
│   ├── main.py                    # FastAPI application entry point
│   ├── domain/                    # Domain Layer (Business Logic)
│   │   ├── entities/              # Domain entities
│   │   │   ├── face_embedding.py
│   │   │   ├── face_detection.py
│   │   │   ├── verification_result.py
│   │   │   ├── liveness_result.py
│   │   │   ├── quality_assessment.py
│   │   │   └── card_type_result.py
│   │   ├── interfaces/            # Abstract interfaces (ports)
│   │   │   ├── face_detector.py
│   │   │   ├── embedding_extractor.py
│   │   │   ├── liveness_detector.py
│   │   │   ├── quality_assessor.py
│   │   │   ├── similarity_calculator.py
│   │   │   ├── embedding_repository.py
│   │   │   └── file_storage.py
│   │   └── exceptions/            # Domain exceptions
│   ├── application/               # Application Layer (Use Cases)
│   │   └── use_cases/
│   │       ├── enroll_face.py
│   │       ├── verify_face.py
│   │       ├── search_face.py
│   │       ├── check_liveness.py
│   │       ├── batch_process.py
│   │       └── detect_card_type.py
│   ├── infrastructure/            # Infrastructure Layer (Implementations)
│   │   ├── ml/
│   │   │   ├── detectors/         # Face detection (DeepFace)
│   │   │   ├── extractors/        # Embedding extraction (DeepFace)
│   │   │   ├── liveness/          # Liveness detection (Texture-based)
│   │   │   ├── quality/           # Quality assessment
│   │   │   ├── similarity/        # Cosine similarity
│   │   │   └── factories/         # Factory patterns
│   │   ├── persistence/           # Data repositories
│   │   │   └── repositories/      # In-memory embedding storage
│   │   └── storage/               # File storage
│   ├── api/                       # API Layer (Controllers)
│   │   ├── routes/                # API endpoints
│   │   │   ├── health.py
│   │   │   ├── enrollment.py
│   │   │   ├── verification.py
│   │   │   ├── search.py
│   │   │   ├── liveness.py
│   │   │   ├── batch.py
│   │   │   └── card_type_router.py
│   │   ├── schemas/               # Pydantic request/response models
│   │   └── middleware/            # Error handling
│   └── core/                      # Core Configuration
│       ├── config.py              # Pydantic settings
│       └── container.py           # Dependency injection container
├── tests/
│   ├── unit/                      # Unit tests
│   ├── integration/               # Integration tests
│   └── e2e/                       # End-to-end tests
├── requirements.txt
├── pyproject.toml
└── pytest.ini
```

## Technology Stack

| Category | Technology | Purpose |
|----------|------------|---------|
| Framework | FastAPI 0.104+ | Async web framework |
| ML Library | DeepFace 0.0.79+ | Face detection & recognition |
| ML Backend | tf-keras 2.15+ | Deep learning backend |
| Computer Vision | OpenCV 4.8+ | Image processing |
| Object Detection | Ultralytics YOLO | Card type detection |
| Validation | Pydantic 2.5+ | Data validation & settings |
| Server | Uvicorn | ASGI server |
| Image Processing | Pillow 10.3+ | Image manipulation |

## Prerequisites

- **Python 3.11** or higher
- **pip** package manager
- **4GB+ RAM** (8GB recommended)
- **GPU** (optional, for faster inference)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Rollingcat-Software/biometric-processor.git
cd biometric-processor
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Application
APP_NAME=FIVUCSAS Biometric Processor
VERSION=1.0.0
ENVIRONMENT=development

# Server
API_HOST=0.0.0.0
API_PORT=8001

# Face Recognition
FACE_DETECTION_BACKEND=opencv
FACE_RECOGNITION_MODEL=Facenet
VERIFICATION_THRESHOLD=0.6

# Liveness Detection
LIVENESS_THRESHOLD=80.0

# Quality Assessment
QUALITY_THRESHOLD=70.0
MIN_FACE_SIZE=80
BLUR_THRESHOLD=100.0

# Logging
LOG_LEVEL=INFO
```

## Running the Application

### Development Mode

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4
```

The API will be available at: `http://localhost:8001`

- **API Documentation**: `http://localhost:8001/docs`
- **ReDoc**: `http://localhost:8001/redoc`

## API Reference

### Base URL

```
http://localhost:8001/api/v1
```

### Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/enroll` | POST | Enroll a face |
| `/api/v1/verify` | POST | Verify face (1:1) |
| `/api/v1/search` | POST | Search face (1:N) |
| `/api/v1/liveness` | POST | Liveness detection |
| `/api/v1/batch/enroll` | POST | Batch enrollment |
| `/api/v1/batch/verify` | POST | Batch verification |
| `/api/v1/card-type/detect-live` | POST | Card type detection |

---

### Health Check

```bash
GET /api/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "FIVUCSAS Biometric Processor",
  "version": "1.0.0"
}
```

---

### Face Enrollment

Enroll a face with quality assessment.

```bash
POST /api/v1/enroll
Content-Type: multipart/form-data
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | file | Yes | Face image (JPEG/PNG) |
| `user_id` | string | Yes | Unique user identifier |
| `tenant_id` | string | No | Tenant identifier (default: "default") |

**Response:**
```json
{
  "success": true,
  "user_id": "user123",
  "quality_score": 85.5,
  "message": "Face enrolled successfully",
  "embedding_dimension": 128
}
```

**Example:**
```bash
curl -X POST "http://localhost:8001/api/v1/enroll" \
  -F "file=@face.jpg" \
  -F "user_id=user123"
```

---

### Face Verification (1:1)

Verify if a face matches an enrolled user.

```bash
POST /api/v1/verify
Content-Type: multipart/form-data
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | file | Yes | Face image to verify |
| `user_id` | string | Yes | User ID to verify against |
| `tenant_id` | string | No | Tenant identifier |

**Response:**
```json
{
  "verified": true,
  "confidence": 0.87,
  "distance": 0.13,
  "threshold": 0.6,
  "message": "Face verified successfully"
}
```

**Example:**
```bash
curl -X POST "http://localhost:8001/api/v1/verify" \
  -F "file=@test_face.jpg" \
  -F "user_id=user123"
```

---

### Face Search (1:N)

Search for matching faces among all enrolled users.

```bash
POST /api/v1/search
Content-Type: multipart/form-data
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | file | Yes | Face image to search |
| `tenant_id` | string | No | Tenant identifier |
| `max_results` | int | No | Maximum results (default: 5) |

**Response:**
```json
{
  "found": true,
  "matches": [
    {"user_id": "user123", "distance": 0.15, "confidence": 0.85},
    {"user_id": "user456", "distance": 0.25, "confidence": 0.75}
  ],
  "total_searched": 100,
  "threshold": 0.6,
  "best_match": {"user_id": "user123", "distance": 0.15, "confidence": 0.85},
  "message": "Found 2 matches"
}
```

---

### Liveness Detection

Passive texture-based liveness detection to prevent spoofing attacks.

```bash
POST /api/v1/liveness
Content-Type: multipart/form-data
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | file | Yes | Face image to check |

**Response:**
```json
{
  "is_live": true,
  "liveness_score": 92.5,
  "challenge": "texture_analysis",
  "challenge_completed": true,
  "message": "Liveness check passed"
}
```

**Detection Methods:**
The liveness detector uses multiple heuristics with weighted scoring:

| Method | Weight | Description |
|--------|--------|-------------|
| Texture Analysis | 35% | Laplacian variance for texture variation |
| Color Distribution | 25% | HSV color naturalness analysis |
| Frequency Analysis | 25% | FFT-based frequency pattern detection |
| Moiré Detection | 15% | Gabor filter screen pattern detection |

**Threshold:** Score ≥ 60.0 = Live

---

### Batch Enrollment

Enroll multiple faces in a single request.

```bash
POST /api/v1/batch/enroll
Content-Type: multipart/form-data
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `files` | file[] | Yes | Multiple face images |
| `user_ids` | string | Yes | Comma-separated user IDs |

---

### Batch Verification

Verify multiple faces in a single request.

```bash
POST /api/v1/batch/verify
Content-Type: multipart/form-data
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `files` | file[] | Yes | Multiple face images |
| `user_ids` | string | Yes | Comma-separated user IDs |

---

### Card Type Detection

Detect document card type using YOLO object detection.

```bash
POST /api/v1/card-type/detect-live
Content-Type: multipart/form-data
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `file` | file | Yes | Card/document image |

**Response:**
```json
{
  "detected": true,
  "class_id": 0,
  "class_name": "tc_kimlik",
  "confidence": 0.95
}
```

**Supported Card Types:**
| Class ID | Class Name | Description |
|----------|------------|-------------|
| 0 | tc_kimlik | Turkish ID Card |
| 1 | ehliyet | Driver's License |
| 2 | pasaport | Passport |
| 3 | ogrenci_karti | Student Card |

---

## Face Recognition Models

The service supports multiple face recognition models via DeepFace:

| Model | Embedding Size | Best For |
|-------|---------------|----------|
| Facenet (default) | 128 | Balanced accuracy/speed |
| Facenet512 | 512 | Higher accuracy |
| VGG-Face | 2622 | High accuracy, more memory |
| ArcFace | 512 | State-of-the-art accuracy |
| OpenFace | 128 | Lightweight |
| DeepFace | 4096 | Legacy support |
| DeepID | 160 | Lightweight |
| Dlib | 128 | CPU-optimized |
| SFace | 128 | Lightweight |

Configure via `FACE_RECOGNITION_MODEL` environment variable.

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | FIVUCSAS Biometric Processor | Application name |
| `VERSION` | 1.0.0 | Application version |
| `ENVIRONMENT` | development | Environment (development/staging/production) |
| `API_HOST` | 0.0.0.0 | API host |
| `API_PORT` | 8001 | API port |
| `FACE_DETECTION_BACKEND` | opencv | Face detector (opencv/ssd/mtcnn/retinaface) |
| `FACE_RECOGNITION_MODEL` | Facenet | Recognition model |
| `VERIFICATION_THRESHOLD` | 0.6 | Verification distance threshold |
| `LIVENESS_THRESHOLD` | 80.0 | Liveness score threshold (0-100) |
| `QUALITY_THRESHOLD` | 70.0 | Quality score threshold (0-100) |
| `MIN_FACE_SIZE` | 80 | Minimum face size in pixels |
| `BLUR_THRESHOLD` | 100.0 | Blur detection threshold |
| `LOG_LEVEL` | INFO | Logging level |

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/unit/test_enrollment.py -v

# Run E2E tests
pytest tests/e2e/ -v
```

## Development

### Code Quality Tools

```bash
# Format code
black app/ tests/

# Sort imports
isort app/ tests/

# Type checking
mypy app/

# Linting
pylint app/
```

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
```

## Current Limitations

- **In-Memory Storage**: Face embeddings are stored in memory and lost on restart
- **No Database**: PostgreSQL integration planned for Sprint 4
- **No Redis**: Caching/queue integration planned for Sprint 5
- **Passive Liveness Only**: Active challenge-response liveness not yet implemented

## Roadmap

| Sprint | Feature | Status |
|--------|---------|--------|
| Sprint 1-2 | Core API & Face Operations | ✅ Complete |
| Sprint 3 | Liveness & Batch Processing | ✅ Complete |
| Sprint 4 | PostgreSQL + pgvector | 🔜 Planned |
| Sprint 5 | Docker, Redis, CI/CD | 🔜 Planned |

## License

This project is part of the **FIVUCSAS** platform developed as an Engineering Project at Marmara University.

Copyright © 2025 FIVUCSAS Team. All rights reserved.

Licensed under the MIT License.

## Acknowledgments

- [DeepFace](https://github.com/serengil/deepface) by Sefik Ilkin Serengil
- [Ultralytics YOLO](https://github.com/ultralytics/ultralytics) for object detection
- [FastAPI](https://fastapi.tiangolo.com/) for the web framework
- Marmara University Computer Engineering Department

---

**FIVUCSAS Team © 2025**
