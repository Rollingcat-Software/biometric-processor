"""Error handling middleware for converting domain exceptions to HTTP responses."""

import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.domain.exceptions.base import BiometricProcessorError
from app.domain.exceptions.face_errors import (
    EmbeddingExtractionError,
    FaceNotDetectedError,
    MultipleFacesError,
    PoorImageQualityError,
    SpoofDetectedError,
)
from app.domain.exceptions.feature_errors import DemographicsError, LandmarkError
from app.domain.exceptions.liveness_errors import LivenessCheckError, LivenessCheckFailedError
from app.domain.exceptions.repository_errors import EmbeddingAlreadyExistsError, RepositoryError
from app.domain.exceptions.storage_errors import FileStorageError
from app.domain.exceptions.verification_errors import (
    EmbeddingNotFoundError,
    VerificationFailedError,
)

logger = logging.getLogger(__name__)


def setup_exception_handlers(app) -> None:
    """Setup exception handlers for the FastAPI application.

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(BiometricProcessorError)
    async def biometric_error_handler(
        request: Request, exc: BiometricProcessorError
    ) -> JSONResponse:
        """Handle all domain exceptions.

        Converts domain exceptions to appropriate HTTP responses
        without leaking internal error details.

        Args:
            request: HTTP request
            exc: Domain exception

        Returns:
            JSONResponse with error details
        """
        # Map exception types to HTTP status codes
        status_code_map = {
            FaceNotDetectedError: status.HTTP_400_BAD_REQUEST,
            MultipleFacesError: status.HTTP_400_BAD_REQUEST,
            PoorImageQualityError: status.HTTP_400_BAD_REQUEST,
            SpoofDetectedError: status.HTTP_403_FORBIDDEN,
            DemographicsError: status.HTTP_400_BAD_REQUEST,
            LandmarkError: status.HTTP_400_BAD_REQUEST,
            EmbeddingExtractionError: status.HTTP_500_INTERNAL_SERVER_ERROR,
            EmbeddingNotFoundError: status.HTTP_404_NOT_FOUND,
            VerificationFailedError: status.HTTP_401_UNAUTHORIZED,
            LivenessCheckFailedError: status.HTTP_400_BAD_REQUEST,
            LivenessCheckError: status.HTTP_500_INTERNAL_SERVER_ERROR,
            RepositoryError: status.HTTP_500_INTERNAL_SERVER_ERROR,
            EmbeddingAlreadyExistsError: status.HTTP_409_CONFLICT,
            FileStorageError: status.HTTP_500_INTERNAL_SERVER_ERROR,
        }

        # Get status code (default to 500 for unknown exceptions)
        http_status = status_code_map.get(type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Log error
        log_level = logging.ERROR if http_status >= 500 else logging.WARNING
        logger.log(
            log_level,
            f"Domain exception: {exc.error_code} - {exc.message}",
            extra={
                "error_code": exc.error_code,
                "http_status": http_status,
                "path": str(request.url),
            },
        )

        # Return JSON response
        return JSONResponse(status_code=http_status, content=exc.to_dict())

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """Handle ValueError exceptions.

        Args:
            request: HTTP request
            exc: ValueError exception

        Returns:
            JSONResponse with error details
        """
        logger.warning(f"ValueError: {str(exc)}", extra={"path": str(request.url)})

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error_code": "INVALID_INPUT",
                "message": str(exc),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected exceptions.

        Args:
            request: HTTP request
            exc: Exception

        Returns:
            JSONResponse with generic error message
        """
        logger.error(
            f"Unexpected error: {str(exc)}",
            exc_info=True,
            extra={"path": str(request.url)},
        )

        # Don't leak internal error details in production
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred. Please try again later.",
            },
        )

    logger.info("Exception handlers configured")
