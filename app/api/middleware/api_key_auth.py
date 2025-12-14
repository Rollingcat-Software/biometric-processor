"""API key authentication middleware."""

import logging
from typing import Callable, List, Optional

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.domain.entities.api_key import APIKey, APIKeyContext
from app.domain.interfaces.api_key_repository import IAPIKeyRepository

logger = logging.getLogger(__name__)

# Request state key for storing auth context
AUTH_CONTEXT_KEY = "api_key_context"


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """API key authentication middleware.

    Validates API keys from the X-API-Key header and provides
    authentication context to downstream handlers.

    Features:
    - SHA-256 key hashing (never stores plaintext)
    - Scope-based authorization
    - Tier extraction for rate limiting
    - Expiration checking
    - Last-used timestamp updates
    """

    def __init__(
        self,
        app,
        repository: IAPIKeyRepository,
        exclude_paths: Optional[List[str]] = None,
        require_auth: bool = False,
    ):
        """Initialize API key auth middleware.

        Args:
            app: FastAPI/Starlette application
            repository: API key repository
            exclude_paths: Paths to exclude from authentication
            require_auth: If True, reject requests without API key
        """
        super().__init__(app)
        self._repository = repository
        self._exclude_paths = exclude_paths or [
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/",
        ]
        self._require_auth = require_auth
        logger.info(
            f"APIKeyAuthMiddleware initialized (require_auth={require_auth})"
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and validate API key.

        Args:
            request: HTTP request
            call_next: Next middleware/route handler

        Returns:
            HTTP response
        """
        # Skip excluded paths
        path = request.url.path
        if any(path.startswith(excluded) for excluded in self._exclude_paths):
            return await call_next(request)

        # Get API key from header
        api_key = request.headers.get("X-API-Key")

        if not api_key:
            if self._require_auth:
                return self._create_unauthorized_response(
                    "API key required. Provide X-API-Key header."
                )
            # No auth required, continue without context
            return await call_next(request)

        # Validate API key
        auth_result = await self._validate_key(api_key)

        if auth_result is None:
            return self._create_unauthorized_response("Invalid API key.")

        key_entity, context = auth_result

        # Check if key is valid (active and not expired)
        if not key_entity.is_valid():
            if key_entity.is_expired():
                return self._create_unauthorized_response("API key has expired.")
            return self._create_unauthorized_response("API key is inactive.")

        # Store context in request state
        request.state.api_key_context = context

        # Update last used timestamp (fire and forget)
        try:
            await self._repository.update_last_used(key_entity.id)
        except Exception as e:
            logger.warning(f"Failed to update last_used: {e}")

        # Continue with request
        response = await call_next(request)

        return response

    async def _validate_key(
        self, plaintext_key: str
    ) -> Optional[tuple[APIKey, APIKeyContext]]:
        """Validate an API key.

        Args:
            plaintext_key: The API key from the request header

        Returns:
            Tuple of (APIKey, APIKeyContext) if valid, None otherwise
        """
        try:
            # Compute hash
            key_hash = APIKey.hash_key(plaintext_key)

            # Look up by hash
            key_entity = await self._repository.find_by_key_hash(key_hash)

            if key_entity is None:
                logger.warning(
                    f"API key not found (prefix: {plaintext_key[:8] if len(plaintext_key) >= 8 else plaintext_key})"
                )
                return None

            # Create context
            context = APIKeyContext(
                key_id=key_entity.id,
                tenant_id=key_entity.tenant_id,
                scopes=key_entity.scopes,
                tier=key_entity.tier,
                name=key_entity.name,
            )

            return key_entity, context

        except Exception as e:
            logger.error(f"API key validation error: {e}")
            return None

    def _create_unauthorized_response(self, message: str) -> JSONResponse:
        """Create HTTP 401 Unauthorized response.

        Args:
            message: Error message

        Returns:
            JSONResponse with 401 status
        """
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error_code": "UNAUTHORIZED",
                "message": message,
            },
            headers={"WWW-Authenticate": "ApiKey"},
        )


def get_api_key_context(request: Request) -> Optional[APIKeyContext]:
    """Get API key context from request.

    Helper function for route handlers to access auth context.

    Args:
        request: HTTP request

    Returns:
        APIKeyContext if authenticated, None otherwise
    """
    return getattr(request.state, AUTH_CONTEXT_KEY, None)


def require_scope(scope: str):
    """Decorator to require a specific scope for a route.

    Usage:
        @router.get("/admin/users")
        @require_scope("admin")
        async def list_users(request: Request):
            ...

    Args:
        scope: Required scope

    Returns:
        Decorator function
    """
    from functools import wraps

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            context = get_api_key_context(request)

            if context is None:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "error_code": "UNAUTHORIZED",
                        "message": "Authentication required.",
                    },
                )

            if scope not in context.scopes and "*" not in context.scopes:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "error_code": "FORBIDDEN",
                        "message": f"Scope '{scope}' required.",
                    },
                )

            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


class RequireAPIKey:
    """FastAPI dependency for requiring API key authentication.

    Usage:
        from fastapi import Depends

        @router.get("/protected")
        async def protected_route(
            context: APIKeyContext = Depends(RequireAPIKey())
        ):
            return {"tenant": context.tenant_id}
    """

    def __init__(self, required_scope: Optional[str] = None):
        """Initialize the dependency.

        Args:
            required_scope: Optional scope to require
        """
        self.required_scope = required_scope

    async def __call__(self, request: Request) -> APIKeyContext:
        """Validate API key and return context.

        Args:
            request: HTTP request

        Returns:
            APIKeyContext

        Raises:
            HTTPException: If authentication fails
        """
        from fastapi import HTTPException

        context = get_api_key_context(request)

        if context is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        if self.required_scope:
            if self.required_scope not in context.scopes and "*" not in context.scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Scope '{self.required_scope}' required",
                )

        return context
