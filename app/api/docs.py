"""OpenAPI documentation configuration and examples."""

from typing import Any, Dict

# API metadata
API_TITLE = "Biometric Processor API"
API_DESCRIPTION = """
# Biometric Processor API

AI/ML microservice for face recognition, verification, and liveness detection.

## Features

### Core Biometric Operations
- **Face Enrollment** - Register face embeddings with quality assessment
- **Face Verification (1:1)** - Verify if two faces belong to the same person
- **Face Search (1:N)** - Identify a person from enrolled faces
- **Liveness Detection** - Anti-spoofing with passive and active challenges

### Advanced Features
- **Quality Analysis** - Detailed image quality feedback
- **Multi-Face Detection** - Detect all faces in an image
- **Demographics** - Age, gender, emotion estimation
- **Face Comparison** - Direct 1:1 comparison without enrollment
- **Similarity Matrix** - NxN face similarity computation

### Production Features
- **Rate Limiting** - Per-tenant/API-key throttling
- **API Key Authentication** - Secure API access
- **Prometheus Metrics** - Observable metrics at `/metrics`
- **Structured Logging** - JSON logging with request context

## Authentication

The API supports optional API key authentication via the `X-API-Key` header:

```
X-API-Key: your-api-key-here
```

## Rate Limiting

Rate limits are enforced based on:
- API Key (if provided)
- Tenant ID (X-Tenant-ID header)
- Client IP (fallback)

Response headers indicate current limits:
- `X-RateLimit-Limit`: Maximum requests
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Unix timestamp for reset

## Error Responses

All errors follow a consistent format:

```json
{
    "error_code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {}
}
```

Common error codes:
- `FACE_NOT_DETECTED` - No face found in image
- `MULTIPLE_FACES` - Multiple faces when one expected
- `POOR_IMAGE_QUALITY` - Image quality below threshold
- `EMBEDDING_NOT_FOUND` - User not enrolled
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `UNAUTHORIZED` - Invalid or missing API key
"""

API_VERSION = "1.0.0"

# Tags for grouping endpoints
TAGS_METADATA = [
    {
        "name": "Health",
        "description": "Health check and status endpoints",
    },
    {
        "name": "Enrollment",
        "description": "Face enrollment operations - register new users",
    },
    {
        "name": "Verification",
        "description": "Face verification (1:1) - verify identity",
    },
    {
        "name": "Liveness",
        "description": "Liveness detection - anti-spoofing checks",
    },
    {
        "name": "Search",
        "description": "Face search (1:N) - identify from enrolled faces",
    },
    {
        "name": "Quality",
        "description": "Image quality analysis and feedback",
    },
    {
        "name": "Detection",
        "description": "Face detection operations",
    },
    {
        "name": "Demographics",
        "description": "Age, gender, emotion analysis",
    },
    {
        "name": "Landmarks",
        "description": "Facial landmark detection",
    },
    {
        "name": "Comparison",
        "description": "Direct face comparison without enrollment",
    },
    {
        "name": "Embeddings",
        "description": "Embedding export and import operations",
    },
    {
        "name": "Webhooks",
        "description": "Webhook event notifications",
    },
    {
        "name": "Batch",
        "description": "Batch processing operations",
    },
    {
        "name": "Monitoring",
        "description": "Metrics and monitoring endpoints",
    },
]

# Example responses
EXAMPLE_RESPONSES: Dict[str, Any] = {
    "health": {
        "status": "healthy",
        "version": "1.0.0",
        "environment": "production",
        "checks": {
            "ml_models": "loaded",
            "redis": "connected",
            "database": "connected"
        }
    },
    "enrollment_success": {
        "success": True,
        "user_id": "user_12345",
        "embedding_id": "emb_abc123",
        "quality_score": 87.5,
        "message": "Face enrolled successfully"
    },
    "verification_success": {
        "verified": True,
        "confidence": 0.92,
        "distance": 0.08,
        "threshold": 0.6,
        "user_id": "user_12345"
    },
    "liveness_success": {
        "is_live": True,
        "liveness_score": 94.2,
        "challenges_completed": ["blink", "smile"],
        "anti_spoofing_checks": {
            "texture_analysis": True,
            "depth_estimation": True,
            "motion_analysis": True
        }
    },
    "quality_analysis": {
        "overall_score": 82.5,
        "is_acceptable": True,
        "metrics": {
            "blur_score": 145.2,
            "lighting_score": 88.0,
            "face_size": 156,
            "face_angle": 5.2
        },
        "recommendations": []
    },
    "face_not_detected": {
        "error_code": "FACE_NOT_DETECTED",
        "message": "No face detected in the provided image",
        "details": {
            "suggestion": "Ensure face is clearly visible and well-lit"
        }
    },
    "rate_limit_exceeded": {
        "error_code": "RATE_LIMIT_EXCEEDED",
        "message": "Too many requests. Please retry later.",
        "retry_after_seconds": 45,
        "tier": "standard"
    }
}

# Request examples
REQUEST_EXAMPLES: Dict[str, Any] = {
    "enrollment": {
        "summary": "Enroll a new user",
        "description": "Register a user's face for future verification",
        "value": {
            "user_id": "user_12345",
            "tenant_id": "tenant_001"
        }
    },
    "verification": {
        "summary": "Verify user identity",
        "description": "Compare a face against enrolled user",
        "value": {
            "user_id": "user_12345"
        }
    }
}


def get_openapi_config() -> Dict[str, Any]:
    """Get OpenAPI configuration.

    Returns:
        OpenAPI configuration dictionary
    """
    return {
        "title": API_TITLE,
        "description": API_DESCRIPTION,
        "version": API_VERSION,
        "openapi_tags": TAGS_METADATA,
        "contact": {
            "name": "Biometric Processor Team",
            "email": "support@example.com",
        },
        "license_info": {
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
    }
