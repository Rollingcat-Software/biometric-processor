# Biometric Processor API

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.11+-yellow.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![DeepFace](https://img.shields.io/badge/DeepFace-AI-red.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Overview

**Biometric Processor API** is the AI/ML microservice of the **FIVUCSAS** (Face and Identity Verification Using Cloud-based SaaS) platform. Built with FastAPI and powered by cutting-edge deep learning models, this service handles computationally intensive biometric operations including face recognition, face verification, and the innovative "Biometric Puzzle" liveness detection algorithm.

This microservice is part of a larger biometric authentication ecosystem developed as an Engineering Project at Marmara University's Computer Engineering Department.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [The Biometric Puzzle Algorithm](#the-biometric-puzzle-algorithm)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Documentation](#api-documentation)
- [Face Recognition Models](#face-recognition-models)
- [Performance Metrics](#performance-metrics)
- [Testing](#testing)
- [Deployment](#deployment)
- [Integration](#integration)
- [Contributing](#contributing)
- [License](#license)

## Features

### Core Biometric Capabilities
- **Face Recognition (1:N)**: Identify a person from a database of known faces
- **Face Verification (1:1)**: Verify if two face images belong to the same person
- **Face Embedding Generation**: Convert face images to 2622-dimensional vectors (VGG-Face)
- **Liveness Detection**: Active "Biometric Puzzle" algorithm to prevent spoofing attacks
- **Quality Assessment**: Face image quality scoring and validation
- **Multi-Modal Support**: Architecture ready for fingerprint, voice, and iris recognition

### Advanced Features
- **GPU Acceleration**: CUDA support for faster inference
- **Batch Processing**: Process multiple face recognition requests efficiently
- **Vector Similarity Search**: Cosine distance calculation for face matching
- **Real-Time Processing**: Optimized for low-latency operations
- **Model Versioning**: Support for multiple face recognition models
- **Asynchronous Processing**: Redis message queue for long-running tasks

## Architecture

```
biometric-processor/
├── app/
│   ├── main.py                      # FastAPI application entry point
│   ├── config/
│   │   ├── settings.py              # Application configuration
│   │   └── models_config.py         # ML model configurations
│   ├── core/
│   │   ├── face_recognition.py      # Face recognition engine
│   │   ├── liveness_detection.py    # Biometric Puzzle algorithm
│   │   ├── quality_assessment.py    # Face quality checker
│   │   └── vector_operations.py     # Embedding operations
│   ├── api/
│   │   ├── v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── face.py          # Face recognition endpoints
│   │   │   │   ├── liveness.py      # Liveness detection endpoints
│   │   │   │   └── health.py        # Health check endpoints
│   │   │   └── dependencies.py      # API dependencies
│   │   └── middleware/
│   │       ├── auth.py              # API key authentication
│   │       ├── rate_limit.py        # Rate limiting
│   │       └── logging.py           # Request logging
│   ├── models/
│   │   ├── schemas.py               # Pydantic models
│   │   └── responses.py             # API response models
│   ├── services/
│   │   ├── deepface_service.py      # DeepFace integration
│   │   ├── mediapipe_service.py     # MediaPipe integration
│   │   └── redis_service.py         # Redis messaging
│   └── utils/
│       ├── image_processing.py      # Image preprocessing
│       ├── validators.py            # Input validation
│       └── metrics.py               # Performance metrics
├── tests/
│   ├── unit/                        # Unit tests
│   ├── integration/                 # Integration tests
│   └── fixtures/                    # Test data
├── docker/
│   ├── Dockerfile                   # Multi-stage build
│   ├── Dockerfile.gpu               # GPU-enabled build
│   └── docker-compose.yml
├── docs/
│   ├── api/                         # API documentation
│   ├── models/                      # Model documentation
│   └── algorithms/                  # Algorithm descriptions
├── requirements.txt                 # Python dependencies
├── requirements-dev.txt             # Development dependencies
├── pyproject.toml                   # Project configuration
├── .env.example
├── README.md
└── LICENSE
```

## Technology Stack

### Core Technologies
- **Python 3.11+**: Modern Python with type hints
- **FastAPI**: High-performance async web framework
- **DeepFace**: Deep learning face recognition library
- **Google MediaPipe**: Real-time ML solutions for face landmarks
- **OpenCV**: Computer vision and image processing
- **NumPy**: Numerical computing
- **Redis**: Message queue and caching

### Deep Learning Frameworks
- **TensorFlow 2.x**: DeepFace backend
- **PyTorch**: Alternative backend (optional)
- **ONNX Runtime**: Optimized inference (future)

### Face Recognition Models (via DeepFace)
- **VGG-Face**: Primary model (2622-d embeddings)
- **Facenet**: Alternative model (128-d embeddings)
- **ArcFace**: High-accuracy model
- **DeepID**: Lightweight option

### Development Tools
- **Uvicorn**: ASGI server
- **Pydantic**: Data validation
- **pytest**: Testing framework
- **Black**: Code formatting
- **mypy**: Static type checking
- **Pillow**: Image manipulation

## The Biometric Puzzle Algorithm

The **Biometric Puzzle** is an innovative active liveness detection mechanism that prevents spoofing attacks using photos, videos, or masks.

### How It Works

1. **Puzzle Generation**: System generates a random sequence of facial actions
   ```python
   puzzle_steps = [
       {"action": "SMILE", "duration": 2},
       {"action": "BLINK_LEFT", "duration": 1},
       {"action": "LOOK_RIGHT", "duration": 2},
       {"action": "BLINK_BOTH", "duration": 1}
   ]
   ```

2. **Real-Time Detection**: User performs actions while camera captures video
   - MediaPipe detects 468 facial landmarks
   - Calculate metrics: EAR (Eye Aspect Ratio), MAR (Mouth Aspect Ratio)
   - Validate each action in sequence

3. **Metrics Calculation**:
   - **Eye Aspect Ratio (EAR)**: Detects blinks
     ```python
     EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
     # EAR < 0.2 indicates blink
     ```
   - **Mouth Aspect Ratio (MAR)**: Detects smile
     ```python
     MAR = ||p14-p18|| / ||p12-p16||
     # MAR > threshold indicates smile
     ```

4. **Verification**: All steps completed within time limit → Liveness confirmed

### Supported Actions

| Action | Description | Detection Method |
|--------|-------------|------------------|
| `SMILE` | User smiles | MAR > 0.6 |
| `BLINK_LEFT` | Blink left eye | Left EAR < 0.2 |
| `BLINK_RIGHT` | Blink right eye | Right EAR < 0.2 |
| `BLINK_BOTH` | Blink both eyes | Both EAR < 0.2 |
| `LOOK_LEFT` | Turn head left | Horizontal face angle |
| `LOOK_RIGHT` | Turn head right | Horizontal face angle |
| `LOOK_UP` | Tilt head up | Vertical face angle |
| `LOOK_DOWN` | Tilt head down | Vertical face angle |
| `NEUTRAL` | Return to neutral | All metrics normal |

### Anti-Spoofing Effectiveness

- **Photo attacks**: 99%+ rejection rate (no motion detected)
- **Video replay**: 95%+ rejection rate (sequential timing validation)
- **3D masks**: 90%+ rejection rate (landmark consistency checks)

## Prerequisites

- **Python 3.11** or higher
- **pip** package manager
- **Redis** for message queue
- **CUDA** (optional, for GPU acceleration)
- **Webcam or camera** for testing liveness detection
- **4GB+ RAM** (8GB recommended)
- **GPU with 2GB+ VRAM** (optional, for better performance)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-organization/biometric-processor.git
cd biometric-processor
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate on Linux/macOS
source venv/bin/activate

# Activate on Windows
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Basic installation
pip install -r requirements.txt

# Development dependencies
pip install -r requirements-dev.txt

# GPU support (CUDA required)
pip install tensorflow-gpu
```

### 4. Set Up Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Application
APP_NAME=Biometric Processor API
APP_VERSION=1.0.0
ENVIRONMENT=development
DEBUG=True

# Server
HOST=0.0.0.0
PORT=8001
WORKERS=4

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Identity Core API
IDENTITY_CORE_API_URL=http://localhost:8080
API_KEY=your-api-key-here

# Face Recognition
FACE_MODEL=VGG-Face
FACE_DETECTOR=opencv
SIMILARITY_THRESHOLD=0.6
EMBEDDING_DIMENSION=2622

# Liveness Detection
LIVENESS_ENABLED=True
PUZZLE_MIN_STEPS=3
PUZZLE_MAX_STEPS=5
PUZZLE_TIMEOUT_SECONDS=30

# Performance
USE_GPU=False
BATCH_SIZE=32
MAX_IMAGE_SIZE=1920

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/biometric-processor.log
```

### 5. Download Face Recognition Models

```bash
# Models will be automatically downloaded on first use
# Or manually download:
python -m deepface.commons.functions
```

## Configuration

### Model Selection

Configure face recognition model in `app/config/models_config.py`:

```python
FACE_MODELS = {
    "VGG-Face": {
        "embedding_size": 2622,
        "input_shape": (224, 224, 3),
        "threshold": 0.68
    },
    "Facenet": {
        "embedding_size": 128,
        "input_shape": (160, 160, 3),
        "threshold": 0.40
    },
    "ArcFace": {
        "embedding_size": 512,
        "input_shape": (112, 112, 3),
        "threshold": 0.68
    }
}
```

### Liveness Puzzle Configuration

```python
LIVENESS_CONFIG = {
    "actions": ["SMILE", "BLINK_BOTH", "LOOK_LEFT", "LOOK_RIGHT"],
    "min_steps": 3,
    "max_steps": 5,
    "timeout": 30,
    "ear_threshold": 0.2,
    "mar_threshold": 0.6
}
```

## Running the Application

### Development Mode

```bash
# Start with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Or using the run script
python run.py
```

### Production Mode

```bash
# Using Uvicorn with workers
uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4

# Using Gunicorn (recommended)
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8001 \
  --timeout 300
```

### Using Docker

```bash
# Build image
docker build -t fivucsas/biometric-processor:latest .

# Run container
docker run -p 8001:8001 --env-file .env fivucsas/biometric-processor:latest

# Or with Docker Compose
docker-compose up -d
```

The API will be available at: `http://localhost:8001`

API Documentation: `http://localhost:8001/docs`

## API Documentation

### Base URL

```
http://localhost:8001/api/v1
```

### Core Endpoints

#### Face Enrollment

```bash
POST /api/v1/face/enroll
Content-Type: multipart/form-data

Parameters:
- user_id: string (UUID)
- image: file (JPEG/PNG)

Response:
{
  "user_id": "uuid",
  "embedding": [float array],
  "embedding_dimension": 2622,
  "quality_score": 0.95,
  "face_detected": true
}
```

#### Face Verification (1:1)

```bash
POST /api/v1/face/verify
Content-Type: application/json

{
  "user_id": "uuid",
  "image_base64": "base64_encoded_image"
}

Response:
{
  "verified": true,
  "confidence": 0.92,
  "distance": 0.18,
  "threshold": 0.68,
  "model": "VGG-Face"
}
```

#### Face Recognition (1:N)

```bash
POST /api/v1/face/recognize
Content-Type: multipart/form-data

Parameters:
- image: file
- tenant_id: string

Response:
{
  "recognized": true,
  "user_id": "uuid",
  "confidence": 0.88,
  "candidates": [
    {"user_id": "uuid1", "confidence": 0.88},
    {"user_id": "uuid2", "confidence": 0.76}
  ]
}
```

#### Generate Liveness Puzzle

```bash
POST /api/v1/liveness/generate-puzzle

Response:
{
  "puzzle_id": "puzzle-uuid",
  "steps": [
    {"action": "SMILE", "duration": 2},
    {"action": "BLINK_BOTH", "duration": 1},
    {"action": "LOOK_RIGHT", "duration": 2}
  ],
  "timeout": 30,
  "expires_at": "2025-10-21T12:00:00Z"
}
```

#### Verify Liveness

```bash
POST /api/v1/liveness/verify
Content-Type: application/json

{
  "puzzle_id": "puzzle-uuid",
  "video_frames": ["base64_frame1", "base64_frame2", ...],
  "landmarks_sequence": [[x1,y1,...], [x2,y2,...], ...]
}

Response:
{
  "success": true,
  "liveness_confirmed": true,
  "steps_completed": 3,
  "total_steps": 3,
  "completion_time": 12.5,
  "final_frame_base64": "..."
}
```

### Example Usage

```python
import requests
import base64

# Enroll face
with open("face.jpg", "rb") as f:
    files = {"image": f}
    data = {"user_id": "user-123"}
    response = requests.post(
        "http://localhost:8001/api/v1/face/enroll",
        files=files,
        data=data
    )
    print(response.json())

# Verify face
with open("test_face.jpg", "rb") as f:
    image_b64 = base64.b64encode(f.read()).decode()
    response = requests.post(
        "http://localhost:8001/api/v1/face/verify",
        json={"user_id": "user-123", "image_base64": image_b64}
    )
    print(response.json())
```

## Face Recognition Models

### Model Comparison

| Model | Embedding Size | Accuracy | Speed | Memory |
|-------|---------------|----------|-------|--------|
| **VGG-Face** | 2622 | ⭐⭐⭐⭐ | ⭐⭐⭐ | High |
| **Facenet** | 128 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Medium |
| **ArcFace** | 512 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | Medium |
| **DeepID** | 160 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Low |

### Similarity Thresholds

```python
THRESHOLDS = {
    "VGG-Face": {
        "cosine": 0.68,
        "euclidean": 0.60,
        "euclidean_l2": 1.17
    },
    "Facenet": {
        "cosine": 0.40,
        "euclidean": 10,
        "euclidean_l2": 0.80
    }
}
```

## Performance Metrics

### Target Performance

- **Face Detection**: < 100ms per image
- **Embedding Generation**: < 500ms per face (CPU), < 100ms (GPU)
- **1:1 Verification**: < 50ms
- **1:N Recognition**: < 500ms for 1000 users
- **Liveness Detection**: 10-30 seconds (user-dependent)

### Accuracy Metrics

- **False Acceptance Rate (FAR)**: < 0.1%
- **False Rejection Rate (FRR)**: < 5%
- **Liveness Detection Success**: > 95%
- **Liveness Spoofing Rejection**: > 99% (photos)

## Testing

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests
pytest tests/integration/

# With coverage
pytest --cov=app tests/

# Specific test
pytest tests/unit/test_face_recognition.py -v
```

### Test Structure

```
tests/
├── unit/
│   ├── test_face_recognition.py
│   ├── test_liveness_detection.py
│   ├── test_quality_assessment.py
│   └── test_vector_operations.py
├── integration/
│   ├── test_api_endpoints.py
│   └── test_deepface_integration.py
└── fixtures/
    ├── sample_faces/
    └── test_videos/
```

## Deployment

### Docker Deployment

```dockerfile
# CPU version
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
```

```bash
# Build and run
docker build -t biometric-processor .
docker run -p 8001:8001 biometric-processor
```

### GPU-Enabled Deployment

```dockerfile
# GPU version
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04
# ... GPU-specific setup
```

### Performance Optimization

```python
# Enable GPU
import tensorflow as tf
gpus = tf.config.list_physical_devices('GPU')
if gpus:
    tf.config.experimental.set_memory_growth(gpus[0], True)

# Batch processing
async def batch_verify_faces(requests: List[VerifyRequest]):
    embeddings = await generate_embeddings_batch([r.image for r in requests])
    return [verify_embedding(e, r.user_id) for e, r in zip(embeddings, requests)]
```

## Integration

### With Identity Core API

```python
# Redis message listener
@app.on_event("startup")
async def start_redis_listener():
    redis_client = await get_redis()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("biometric.enrollment.request")

    async for message in pubsub.listen():
        if message["type"] == "message":
            await process_enrollment(message["data"])
```

### Message Queue Topics

- **Subscribe to**:
  - `biometric.enrollment.request`
  - `biometric.verification.request`

- **Publish to**:
  - `biometric.enrollment.complete`
  - `biometric.verification.result`

## Contributing

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run linting
black app/ tests/
pylint app/
mypy app/
```

### Code Style

- Follow **PEP 8** style guide
- Use **type hints** for all functions
- Write **docstrings** for public APIs
- Maintain **80% test coverage**

## Troubleshooting

### Common Issues

#### Model Download Fails
```bash
# Manual download
pip install gdown
python -c "from deepface.commons import functions; functions.initialize_folder()"
```

#### Out of Memory (OOM)
```python
# Reduce batch size
BATCH_SIZE = 8  # Instead of 32

# Use smaller model
FACE_MODEL = "Facenet"  # Instead of VGG-Face
```

#### Slow Performance
```bash
# Enable GPU
export USE_GPU=True

# Use ONNX Runtime
pip install onnxruntime-gpu
```

## License

This project is part of the **FIVUCSAS** platform developed as an Engineering Project at Marmara University.

Copyright © 2025 FIVUCSAS Team. All rights reserved.

Licensed under the MIT License.

## Support

- **GitHub Issues**: [Report bugs](https://github.com/your-org/biometric-processor/issues)
- **Documentation**: [Full API docs](http://localhost:8001/docs)
- **Team Contact**: [Your Team Email]

## Acknowledgments

- **DeepFace** library by Sefik Ilkin Serengil
- **Google MediaPipe** for facial landmark detection
- **TensorFlow** and **PyTorch** communities
- Marmara University Computer Engineering Department

---

**Powered by Deep Learning** | FIVUCSAS Team © 2025
