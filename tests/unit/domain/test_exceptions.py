"""Unit tests for domain exceptions."""

import pytest

from app.domain.exceptions.base import BiometricProcessorError
from app.domain.exceptions.face_errors import (
    FaceNotDetectedError,
    MultipleFacesError,
    PoorImageQualityError,
    EmbeddingExtractionError,
)
from app.domain.exceptions.verification_errors import (
    EmbeddingNotFoundError,
    VerificationFailedError,
)
from app.domain.exceptions.liveness_errors import (
    LivenessCheckFailedError,
    LivenessCheckError,
)
from app.domain.exceptions.repository_errors import (
    RepositoryError,
    EmbeddingAlreadyExistsError,
)
from app.domain.exceptions.storage_errors import FileStorageError


# ============================================================================
# Base Exception Tests
# ============================================================================


class TestBiometricProcessorError:
    """Test base exception class."""

    def test_create_base_exception(self):
        """Test creating base exception."""
        error = BiometricProcessorError(message="Test error", error_code="TEST_ERROR")

        assert error.message == "Test error"
        assert error.error_code == "TEST_ERROR"
        assert str(error) == "[TEST_ERROR] Test error"

    def test_exception_str_representation(self):
        """Test string representation includes error code."""
        error = BiometricProcessorError(
            message="Something went wrong", error_code="GENERIC_ERROR"
        )

        assert str(error) == "[GENERIC_ERROR] Something went wrong"

    def test_exception_repr_representation(self):
        """Test repr representation for debugging."""
        error = BiometricProcessorError(message="Test error", error_code="TEST_ERROR")

        repr_str = repr(error)
        assert "BiometricProcessorError" in repr_str
        assert "Test error" in repr_str
        assert "TEST_ERROR" in repr_str

    def test_to_dict(self):
        """Test converting exception to dictionary."""
        error = BiometricProcessorError(message="Test error", error_code="TEST_ERROR")

        result = error.to_dict()

        assert result == {"error_code": "TEST_ERROR", "message": "Test error"}

    def test_inheritance_from_exception(self):
        """Test that base error inherits from Exception."""
        error = BiometricProcessorError(message="Test", error_code="TEST")

        assert isinstance(error, Exception)

    def test_can_be_raised_and_caught(self):
        """Test that exception can be raised and caught."""
        with pytest.raises(BiometricProcessorError) as exc_info:
            raise BiometricProcessorError(message="Test error", error_code="TEST_ERROR")

        assert exc_info.value.error_code == "TEST_ERROR"


# ============================================================================
# Face Error Tests
# ============================================================================


class TestFaceNotDetectedError:
    """Test FaceNotDetectedError."""

    def test_create_error(self):
        """Test creating face not detected error."""
        error = FaceNotDetectedError()

        assert error.error_code == "FACE_NOT_DETECTED"
        assert "No face detected" in error.message
        assert "clear, front-facing photo" in error.message

    def test_inheritance(self):
        """Test inheritance from base exception."""
        error = FaceNotDetectedError()

        assert isinstance(error, BiometricProcessorError)
        assert isinstance(error, Exception)

    def test_to_dict(self):
        """Test converting to dictionary."""
        error = FaceNotDetectedError()

        result = error.to_dict()

        assert result["error_code"] == "FACE_NOT_DETECTED"
        assert "message" in result


class TestMultipleFacesError:
    """Test MultipleFacesError."""

    def test_create_error(self):
        """Test creating multiple faces error."""
        error = MultipleFacesError(count=3)

        assert error.error_code == "MULTIPLE_FACES"
        assert "Multiple faces detected (3)" in error.message
        assert error.face_count == 3

    def test_to_dict_includes_face_count(self):
        """Test that to_dict includes face count."""
        error = MultipleFacesError(count=5)

        result = error.to_dict()

        assert result["error_code"] == "MULTIPLE_FACES"
        assert result["face_count"] == 5
        assert "message" in result

    def test_different_counts(self):
        """Test with different face counts."""
        error2 = MultipleFacesError(count=2)
        error10 = MultipleFacesError(count=10)

        assert error2.face_count == 2
        assert error10.face_count == 10
        assert "2" in error2.message
        assert "10" in error10.message


class TestPoorImageQualityError:
    """Test PoorImageQualityError."""

    def test_create_error_with_defaults(self):
        """Test creating error with default threshold."""
        error = PoorImageQualityError(quality_score=45.0)

        assert error.error_code == "POOR_IMAGE_QUALITY"
        assert error.quality_score == 45.0
        assert error.min_threshold == 70.0
        assert "45" in error.message
        assert "70" in error.message

    def test_create_error_with_custom_threshold(self):
        """Test creating error with custom threshold."""
        error = PoorImageQualityError(quality_score=60.0, min_threshold=80.0)

        assert error.quality_score == 60.0
        assert error.min_threshold == 80.0
        assert "60" in error.message
        assert "80" in error.message

    def test_to_dict_includes_scores(self):
        """Test that to_dict includes quality scores."""
        error = PoorImageQualityError(quality_score=55.0, min_threshold=75.0)

        result = error.to_dict()

        assert result["error_code"] == "POOR_IMAGE_QUALITY"
        assert result["quality_score"] == 55.0
        assert result["min_threshold"] == 75.0
        assert "message" in result

    def test_message_includes_guidance(self):
        """Test that message includes user guidance."""
        error = PoorImageQualityError(quality_score=40.0)

        assert "good lighting" in error.message
        assert "minimal blur" in error.message


class TestEmbeddingExtractionError:
    """Test EmbeddingExtractionError."""

    def test_create_error_with_reason(self):
        """Test creating error with custom reason."""
        error = EmbeddingExtractionError(reason="Model loading failed")

        assert error.error_code == "EMBEDDING_EXTRACTION_FAILED"
        assert error.reason == "Model loading failed"
        assert "Model loading failed" in error.message

    def test_create_error_with_default_reason(self):
        """Test creating error with default reason."""
        error = EmbeddingExtractionError()

        assert error.reason == "Unknown error"
        assert "Unknown error" in error.message

    def test_to_dict_includes_reason(self):
        """Test that to_dict includes failure reason."""
        error = EmbeddingExtractionError(reason="Out of memory")

        result = error.to_dict()

        assert result["error_code"] == "EMBEDDING_EXTRACTION_FAILED"
        assert result["reason"] == "Out of memory"
        assert "message" in result


# ============================================================================
# Verification Error Tests
# ============================================================================


class TestEmbeddingNotFoundError:
    """Test EmbeddingNotFoundError."""

    def test_create_error(self):
        """Test creating embedding not found error."""
        error = EmbeddingNotFoundError(user_id="test_user_123")

        assert error.error_code == "EMBEDDING_NOT_FOUND"
        assert error.user_id == "test_user_123"
        assert "test_user_123" in error.message
        assert "enroll first" in error.message

    def test_to_dict_includes_user_id(self):
        """Test that to_dict includes user_id."""
        error = EmbeddingNotFoundError(user_id="user_456")

        result = error.to_dict()

        assert result["error_code"] == "EMBEDDING_NOT_FOUND"
        assert result["user_id"] == "user_456"
        assert "message" in result


class TestVerificationFailedError:
    """Test VerificationFailedError."""

    def test_create_error(self):
        """Test creating verification failed error."""
        error = VerificationFailedError(confidence=0.45, threshold=0.6)

        assert error.error_code == "VERIFICATION_FAILED"
        assert error.confidence == 0.45
        assert error.threshold == 0.6
        assert "0.45" in error.message
        assert "0.60" in error.message

    def test_to_dict_includes_scores(self):
        """Test that to_dict includes confidence and threshold."""
        error = VerificationFailedError(confidence=0.35, threshold=0.6)

        result = error.to_dict()

        assert result["error_code"] == "VERIFICATION_FAILED"
        assert result["confidence"] == 0.35
        assert result["threshold"] == 0.6
        assert "message" in result

    def test_message_formatting(self):
        """Test that message is properly formatted."""
        error = VerificationFailedError(confidence=0.5, threshold=0.6)

        # Should format with 2 decimal places
        assert "0.50" in error.message
        assert "0.60" in error.message
        assert "below threshold" in error.message


# ============================================================================
# Liveness Error Tests
# ============================================================================


class TestLivenessCheckFailedError:
    """Test LivenessCheckFailedError."""

    def test_create_error_with_defaults(self):
        """Test creating error with default values."""
        error = LivenessCheckFailedError(liveness_score=60.0)

        assert error.error_code == "LIVENESS_CHECK_FAILED"
        assert error.liveness_score == 60.0
        assert error.min_threshold == 80.0
        assert error.challenge == "unknown"

    def test_create_error_with_all_params(self):
        """Test creating error with all parameters."""
        error = LivenessCheckFailedError(
            liveness_score=65.0, min_threshold=85.0, challenge="smile"
        )

        assert error.liveness_score == 65.0
        assert error.min_threshold == 85.0
        assert error.challenge == "smile"
        assert "65" in error.message
        assert "85" in error.message
        assert "smile" in error.message

    def test_to_dict_includes_liveness_details(self):
        """Test that to_dict includes all liveness details."""
        error = LivenessCheckFailedError(
            liveness_score=70.0, min_threshold=80.0, challenge="blink"
        )

        result = error.to_dict()

        assert result["error_code"] == "LIVENESS_CHECK_FAILED"
        assert result["liveness_score"] == 70.0
        assert result["min_threshold"] == 80.0
        assert result["challenge"] == "blink"
        assert "message" in result

    def test_message_includes_guidance(self):
        """Test that message includes user guidance."""
        error = LivenessCheckFailedError(liveness_score=50.0)

        assert "live person" in error.message
        assert "requested action" in error.message


class TestLivenessCheckError:
    """Test LivenessCheckError."""

    def test_create_error_with_reason(self):
        """Test creating error with custom reason."""
        error = LivenessCheckError(reason="Camera initialization failed")

        assert error.error_code == "LIVENESS_CHECK_ERROR"
        assert error.reason == "Camera initialization failed"
        assert "Camera initialization failed" in error.message

    def test_create_error_with_default_reason(self):
        """Test creating error with default reason."""
        error = LivenessCheckError()

        assert error.reason == "Unknown error"
        assert "Unknown error" in error.message

    def test_to_dict_includes_reason(self):
        """Test that to_dict includes failure reason."""
        error = LivenessCheckError(reason="Timeout")

        result = error.to_dict()

        assert result["error_code"] == "LIVENESS_CHECK_ERROR"
        assert result["reason"] == "Timeout"
        assert "message" in result

    def test_different_from_liveness_check_failed(self):
        """Test that this is different from LivenessCheckFailedError."""
        technical_error = LivenessCheckError(reason="System error")
        failed_check = LivenessCheckFailedError(liveness_score=40.0)

        # Different error codes
        assert technical_error.error_code != failed_check.error_code
        assert technical_error.error_code == "LIVENESS_CHECK_ERROR"
        assert failed_check.error_code == "LIVENESS_CHECK_FAILED"


# ============================================================================
# Repository Error Tests
# ============================================================================


class TestRepositoryError:
    """Test RepositoryError."""

    def test_create_error_with_reason(self):
        """Test creating error with operation and reason."""
        error = RepositoryError(operation="save", reason="Database connection failed")

        assert error.error_code == "REPOSITORY_ERROR"
        assert error.operation == "save"
        assert error.reason == "Database connection failed"
        assert "save" in error.message
        assert "Database connection failed" in error.message

    def test_create_error_with_default_reason(self):
        """Test creating error with default reason."""
        error = RepositoryError(operation="find")

        assert error.reason == "Unknown error"
        assert "find" in error.message

    def test_to_dict_includes_operation_and_reason(self):
        """Test that to_dict includes operation and reason."""
        error = RepositoryError(operation="delete", reason="Record not found")

        result = error.to_dict()

        assert result["error_code"] == "REPOSITORY_ERROR"
        assert result["operation"] == "delete"
        assert result["reason"] == "Record not found"
        assert "message" in result

    def test_different_operations(self):
        """Test with different operation types."""
        save_error = RepositoryError(operation="save", reason="Duplicate key")
        find_error = RepositoryError(operation="find", reason="Invalid query")
        delete_error = RepositoryError(operation="delete", reason="Permission denied")

        assert save_error.operation == "save"
        assert find_error.operation == "find"
        assert delete_error.operation == "delete"


class TestEmbeddingAlreadyExistsError:
    """Test EmbeddingAlreadyExistsError."""

    def test_create_error(self):
        """Test creating embedding already exists error."""
        error = EmbeddingAlreadyExistsError(user_id="user_789")

        assert error.error_code == "EMBEDDING_ALREADY_EXISTS"
        assert error.user_id == "user_789"
        assert "user_789" in error.message
        assert "Use update instead" in error.message

    def test_to_dict_includes_user_id(self):
        """Test that to_dict includes user_id."""
        error = EmbeddingAlreadyExistsError(user_id="duplicate_user")

        result = error.to_dict()

        assert result["error_code"] == "EMBEDDING_ALREADY_EXISTS"
        assert result["user_id"] == "duplicate_user"
        assert "message" in result


# ============================================================================
# Storage Error Tests
# ============================================================================


class TestFileStorageError:
    """Test FileStorageError."""

    def test_create_error_with_all_params(self):
        """Test creating error with all parameters."""
        error = FileStorageError(
            operation="save", file_path="/tmp/test.jpg", reason="Disk full"
        )

        assert error.error_code == "FILE_STORAGE_ERROR"
        assert error.operation == "save"
        assert error.file_path == "/tmp/test.jpg"
        assert error.reason == "Disk full"
        assert "save" in error.message
        assert "Disk full" in error.message
        # File path should NOT be in message for security
        assert "/tmp/test.jpg" not in error.message

    def test_create_error_with_defaults(self):
        """Test creating error with default values."""
        error = FileStorageError(operation="read")

        assert error.file_path == ""
        assert error.reason == "Unknown error"

    def test_to_dict_excludes_file_path(self):
        """Test that to_dict excludes file_path for security."""
        error = FileStorageError(
            operation="delete", file_path="/sensitive/path/file.jpg", reason="Not found"
        )

        result = error.to_dict()

        assert result["error_code"] == "FILE_STORAGE_ERROR"
        assert result["operation"] == "delete"
        assert result["reason"] == "Not found"
        # File path should NOT be in response for security
        assert "file_path" not in result
        assert "/sensitive/path" not in str(result)

    def test_different_operations(self):
        """Test with different file operations."""
        save_error = FileStorageError(operation="save", reason="Permission denied")
        read_error = FileStorageError(operation="read", reason="File not found")
        delete_error = FileStorageError(operation="delete", reason="Access denied")

        assert save_error.operation == "save"
        assert read_error.operation == "read"
        assert delete_error.operation == "delete"

    def test_security_file_path_not_exposed(self):
        """Test that sensitive file paths are not exposed in error response."""
        sensitive_path = "/home/user/.secrets/api_keys.txt"
        error = FileStorageError(
            operation="read", file_path=sensitive_path, reason="Permission denied"
        )

        # File path stored internally for logging
        assert error.file_path == sensitive_path

        # But NOT exposed in message or to_dict
        assert sensitive_path not in error.message
        assert "file_path" not in error.to_dict()


# ============================================================================
# Exception Hierarchy Tests
# ============================================================================


class TestExceptionHierarchy:
    """Test exception inheritance hierarchy."""

    def test_all_inherit_from_base(self):
        """Test that all domain exceptions inherit from base."""
        exceptions = [
            FaceNotDetectedError(),
            MultipleFacesError(count=2),
            PoorImageQualityError(quality_score=50.0),
            EmbeddingExtractionError(reason="Test"),
            EmbeddingNotFoundError(user_id="test"),
            VerificationFailedError(confidence=0.5, threshold=0.6),
            LivenessCheckFailedError(liveness_score=50.0),
            LivenessCheckError(reason="Test"),
            RepositoryError(operation="save", reason="Test"),
            EmbeddingAlreadyExistsError(user_id="test"),
            FileStorageError(operation="read", reason="Test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, BiometricProcessorError)
            assert isinstance(exc, Exception)

    def test_can_catch_all_with_base_exception(self):
        """Test that all exceptions can be caught by base exception handler."""
        exceptions_to_test = [
            FaceNotDetectedError(),
            MultipleFacesError(count=3),
            PoorImageQualityError(quality_score=40.0),
        ]

        for exc in exceptions_to_test:
            with pytest.raises(BiometricProcessorError):
                raise exc

    def test_unique_error_codes(self):
        """Test that all exceptions have unique error codes."""
        exceptions = [
            FaceNotDetectedError(),
            MultipleFacesError(count=2),
            PoorImageQualityError(quality_score=50.0),
            EmbeddingExtractionError(),
            EmbeddingNotFoundError(user_id="test"),
            VerificationFailedError(confidence=0.5, threshold=0.6),
            LivenessCheckFailedError(liveness_score=50.0),
            LivenessCheckError(),
            RepositoryError(operation="save"),
            EmbeddingAlreadyExistsError(user_id="test"),
            FileStorageError(operation="read"),
        ]

        error_codes = [exc.error_code for exc in exceptions]

        # All error codes should be unique
        assert len(error_codes) == len(set(error_codes))

    def test_all_have_to_dict_method(self):
        """Test that all exceptions have to_dict method."""
        exceptions = [
            FaceNotDetectedError(),
            MultipleFacesError(count=2),
            PoorImageQualityError(quality_score=50.0),
            EmbeddingExtractionError(),
            EmbeddingNotFoundError(user_id="test"),
            VerificationFailedError(confidence=0.5, threshold=0.6),
            LivenessCheckFailedError(liveness_score=50.0),
            LivenessCheckError(),
            RepositoryError(operation="save"),
            EmbeddingAlreadyExistsError(user_id="test"),
            FileStorageError(operation="read"),
        ]

        for exc in exceptions:
            result = exc.to_dict()
            assert "error_code" in result
            assert "message" in result
            assert isinstance(result, dict)
