"""Pytest configuration and shared fixtures.

This module provides:
    - Shared fixtures for all test modules
    - Mock implementations for testing
    - Sample data generators
    - Test configuration
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.api_client import MockAPIClient
from utils.container import (
    DependencyContainer,
    InMemoryCacheManager,
    InMemorySessionManager,
    MockImageProcessor,
)
from utils.protocols import IAPIClient


# ============================================
# API Client Fixtures
# ============================================


@pytest.fixture
def mock_api_client() -> MockAPIClient:
    """Create a mock API client for testing.

    Returns:
        MockAPIClient instance with default responses.
    """
    client = MockAPIClient()

    # Set up default responses
    client.set_response("/api/v1/health", {"status": "healthy", "version": "1.0.0"})
    client.set_response("/api/v1/enroll", {
        "success": True,
        "enrollment_id": "test-enrollment-123",
        "user_id": "test_user",
        "quality_score": 0.95,
        "created_at": "2025-12-12T14:30:00Z",
    })
    client.set_response("/api/v1/verify", {
        "verified": True,
        "confidence": 0.87,
        "distance": 0.13,
        "threshold": 0.6,
    })

    return client


@pytest.fixture
def async_mock_api_client() -> AsyncMock:
    """Create an async mock API client.

    Returns:
        AsyncMock configured as IAPIClient.
    """
    client = AsyncMock(spec=IAPIClient)
    client.base_url = "http://mock-api:8001"
    client.health_check.return_value = True
    return client


# ============================================
# Container Fixtures
# ============================================


@pytest.fixture
def test_container(mock_api_client: MockAPIClient) -> DependencyContainer:
    """Create a test dependency container.

    Args:
        mock_api_client: Mock API client fixture.

    Returns:
        DependencyContainer configured for testing.
    """
    return DependencyContainer(
        api_client=mock_api_client,
        image_processor=MockImageProcessor(),
        session_manager=InMemorySessionManager(),
        cache_manager=InMemoryCacheManager(),
    )


@pytest.fixture
def production_like_container() -> DependencyContainer:
    """Create a container similar to production but with mocks.

    Returns:
        DependencyContainer with mock implementations.
    """
    return DependencyContainer.create_testing()


# ============================================
# Image Fixtures
# ============================================


@pytest.fixture
def sample_face_image() -> bytes:
    """Load or generate a sample face image.

    Returns:
        Image bytes for testing.
    """
    # Check if sample image exists
    sample_path = Path(__file__).parent / "fixtures" / "sample_images" / "valid_face.jpg"

    if sample_path.exists():
        return sample_path.read_bytes()

    # Generate a minimal valid JPEG if no sample exists
    # This is a 1x1 pixel white JPEG
    return bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
        0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
        0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
        0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
        0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
        0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
        0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
        0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
        0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
        0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
        0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
        0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
        0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
        0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
        0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
        0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
        0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD5, 0xDB, 0x20, 0xA8, 0xBA, 0xAB, 0x81,
        0x8A, 0x28, 0x03, 0xFF, 0xD9
    ])


@pytest.fixture
def sample_png_image() -> bytes:
    """Generate a minimal PNG image for testing.

    Returns:
        PNG image bytes.
    """
    # Minimal 1x1 white PNG
    return bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D,
        0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53, 0xDE, 0x00, 0x00, 0x00,
        0x0C, 0x49, 0x44, 0x41, 0x54, 0x08, 0xD7, 0x63, 0xF8, 0xFF, 0xFF, 0x3F,
        0x00, 0x05, 0xFE, 0x02, 0xFE, 0xDC, 0xCC, 0x59, 0xE7, 0x00, 0x00, 0x00,
        0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
    ])


# ============================================
# Mock Response Fixtures
# ============================================


@pytest.fixture
def mock_enrollment_response() -> dict[str, Any]:
    """Get mock enrollment API response.

    Returns:
        Dictionary mimicking enrollment response.
    """
    return {
        "success": True,
        "enrollment_id": "test-enrollment-123",
        "user_id": "test_user",
        "quality_score": 0.95,
        "face_confidence": 0.998,
        "embedding_dimension": 128,
        "created_at": "2025-12-12T14:30:00Z",
    }


@pytest.fixture
def mock_verification_response() -> dict[str, Any]:
    """Get mock verification API response.

    Returns:
        Dictionary mimicking verification response.
    """
    return {
        "verified": True,
        "confidence": 0.87,
        "distance": 0.13,
        "threshold": 0.6,
        "processing_time_ms": 142.5,
    }


@pytest.fixture
def mock_liveness_response() -> dict[str, Any]:
    """Get mock liveness API response.

    Returns:
        Dictionary mimicking liveness response.
    """
    return {
        "is_live": True,
        "liveness_score": 85.0,
        "challenge": "combined",
        "challenge_completed": True,
        "texture_score": 82.0,
        "behavioral_score": 91.0,
    }


@pytest.fixture
def mock_quality_response() -> dict[str, Any]:
    """Get mock quality analysis API response.

    Returns:
        Dictionary mimicking quality response.
    """
    return {
        "overall_score": 89.0,
        "is_acceptable": True,
        "metrics": {
            "blur_score": 150.0,
            "brightness_score": 120.0,
            "face_size_score": 100.0,
            "pose_score": 85.0,
        },
        "issues": [],
        "recommendations": ["Good lighting", "Face well-centered"],
    }


# ============================================
# Utility Fixtures
# ============================================


@pytest.fixture
def temp_session_state() -> dict[str, Any]:
    """Create a temporary session state dictionary.

    Returns:
        Empty dictionary for session state testing.
    """
    return {}


@pytest.fixture
def mock_streamlit(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock Streamlit module for testing.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        MagicMock representing streamlit module.
    """
    mock_st = MagicMock()
    mock_st.session_state = {}
    monkeypatch.setattr("streamlit", mock_st, raising=False)
    return mock_st


# ============================================
# Async Fixtures
# ============================================


@pytest.fixture
def event_loop_policy():
    """Configure event loop for async tests."""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()
