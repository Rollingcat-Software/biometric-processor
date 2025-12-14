"""Unit tests for configuration module.

Tests the Settings and Thresholds classes in utils/config.py.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from utils.config import Settings, Thresholds, get_settings, get_thresholds


class TestSettings:
    """Tests for Settings class."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        settings = Settings()

        assert settings.app_name == "Biometric Processor Demo"
        assert settings.app_version == "1.0.0"
        assert settings.debug is False
        assert settings.api_base_url == "http://localhost:8001"
        assert settings.api_timeout == 30
        assert settings.max_image_size_mb == 10
        assert settings.image_quality == 85

    def test_api_url_validation_adds_http(self) -> None:
        """Test that API URL gets http:// prefix if missing."""
        settings = Settings(api_base_url="localhost:8001")
        assert settings.api_base_url == "http://localhost:8001"

    def test_api_url_validation_removes_trailing_slash(self) -> None:
        """Test that trailing slash is removed from API URL."""
        settings = Settings(api_base_url="http://localhost:8001/")
        assert settings.api_base_url == "http://localhost:8001"

    def test_api_url_preserves_https(self) -> None:
        """Test that https:// is preserved."""
        settings = Settings(api_base_url="https://api.example.com")
        assert settings.api_base_url == "https://api.example.com"

    def test_max_image_size_bytes_property(self) -> None:
        """Test max_image_size_bytes calculation."""
        settings = Settings(max_image_size_mb=10)
        assert settings.max_image_size_bytes == 10 * 1024 * 1024

    def test_target_image_size_bytes_property(self) -> None:
        """Test target_image_size_bytes calculation."""
        settings = Settings(target_image_size_kb=500)
        assert settings.target_image_size_bytes == 500 * 1024

    def test_api_version_property(self) -> None:
        """Test API version path."""
        settings = Settings()
        assert settings.api_version == "/api/v1"

    def test_get_api_endpoint(self) -> None:
        """Test API endpoint construction."""
        settings = Settings(api_base_url="http://localhost:8001")

        # Test with leading slash
        endpoint = settings.get_api_endpoint("/health")
        assert endpoint == "http://localhost:8001/api/v1/health"

        # Test without leading slash
        endpoint = settings.get_api_endpoint("health")
        assert endpoint == "http://localhost:8001/api/v1/health"

    def test_environment_variable_override(self) -> None:
        """Test that environment variables override defaults."""
        with patch.dict(os.environ, {"DEMO_DEBUG": "true", "DEMO_API_TIMEOUT": "60"}):
            # Clear cached settings
            get_settings.cache_clear()

            settings = Settings()
            assert settings.debug is True
            assert settings.api_timeout == 60

        # Reset cache
        get_settings.cache_clear()

    def test_validation_constraints(self) -> None:
        """Test that validation constraints are enforced."""
        # Test minimum timeout
        with pytest.raises(ValueError):
            Settings(api_timeout=1)

        # Test maximum timeout
        with pytest.raises(ValueError):
            Settings(api_timeout=1000)

        # Test image quality bounds
        with pytest.raises(ValueError):
            Settings(image_quality=10)

    def test_theme_literal(self) -> None:
        """Test theme validation."""
        settings = Settings(theme="dark")
        assert settings.theme == "dark"

        settings = Settings(theme="light")
        assert settings.theme == "light"

        settings = Settings(theme="auto")
        assert settings.theme == "auto"


class TestThresholds:
    """Tests for Thresholds class."""

    def test_verification_thresholds(self) -> None:
        """Test verification threshold constants."""
        assert Thresholds.VERIFICATION_SIMILARITY == 0.6
        assert Thresholds.HIGH_CONFIDENCE_THRESHOLD == 0.8
        assert Thresholds.LOW_CONFIDENCE_THRESHOLD == 0.5

    def test_quality_thresholds(self) -> None:
        """Test quality threshold constants."""
        assert Thresholds.QUALITY_SCORE_MIN == 70.0
        assert Thresholds.BLUR_VARIANCE_MIN == 100.0

    def test_liveness_thresholds(self) -> None:
        """Test liveness threshold constants."""
        assert Thresholds.LIVENESS_SCORE_MIN == 70.0
        assert Thresholds.EAR_THRESHOLD == 0.25
        assert Thresholds.MAR_THRESHOLD == 0.6

    def test_proctoring_thresholds(self) -> None:
        """Test proctoring threshold constants."""
        assert Thresholds.GAZE_AWAY_SECONDS == 5.0
        assert Thresholds.HEAD_PITCH_DEGREES == 20.0
        assert Thresholds.RISK_SCORE_HIGH == 0.7


class TestGetSettings:
    """Tests for get_settings function."""

    def test_returns_settings_instance(self) -> None:
        """Test that get_settings returns a Settings instance."""
        get_settings.cache_clear()
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_caches_result(self) -> None:
        """Test that get_settings caches the result."""
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2


class TestGetThresholds:
    """Tests for get_thresholds function."""

    def test_returns_thresholds_class(self) -> None:
        """Test that get_thresholds returns Thresholds class."""
        thresholds = get_thresholds()
        assert thresholds is Thresholds

    def test_can_access_constants(self) -> None:
        """Test that constants are accessible."""
        thresholds = get_thresholds()
        assert thresholds.VERIFICATION_SIMILARITY == 0.6
