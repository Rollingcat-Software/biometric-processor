"""JWT authentication middleware for Identity Core API integration.

Provides JWT token validation and API key authentication for securing
biometric API endpoints. Integrates with the Identity Core API for
centralized authentication.
"""

from typing import Optional
from datetime import datetime, timezone
import logging

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


class JWTPayload:
    """Decoded JWT payload container.

    Attributes:
        user_id: Subject identifier (user ID)
        email: User's email address
        tenant_id: Multi-tenant identifier
        roles: List of user roles
        permissions: List of granted permissions
        exp: Token expiration timestamp
        iat: Token issued-at timestamp
    """

    def __init__(self, payload: dict):
        self.user_id: str = payload.get("sub", "")
        self.email: str = payload.get("email", "")
        self.tenant_id: str = payload.get("tenant_id", "")
        self.roles: list[str] = payload.get("roles", [])
        self.permissions: list[str] = payload.get("permissions", [])
        self.exp: int = payload.get("exp", 0)
        self.iat: int = payload.get("iat", 0)
        self.jti: str = payload.get("jti", "")  # JWT ID for tracking

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return datetime.now(timezone.utc).timestamp() > self.exp

    def has_role(self, role: str) -> bool:
        """Check if user has specific role."""
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission."""
        return permission in self.permissions

    def has_any_permission(self, permissions: list[str]) -> bool:
        """Check if user has any of the specified permissions."""
        return any(p in self.permissions for p in permissions)

    def has_all_permissions(self, permissions: list[str]) -> bool:
        """Check if user has all of the specified permissions."""
        return all(p in self.permissions for p in permissions)

    def is_admin(self) -> bool:
        """Check if user has admin privileges."""
        return self.has_role("ADMIN") or self.has_role("SUPER_ADMIN")


class AuthContext:
    """Authentication context for the current request.

    Contains all authentication information extracted from the request,
    regardless of the authentication method used (JWT or API key).
    """

    def __init__(
        self,
        authenticated: bool = False,
        auth_type: str = "none",
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        email: Optional[str] = None,
        roles: Optional[list[str]] = None,
        permissions: Optional[list[str]] = None,
        api_key_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        self.authenticated = authenticated
        self.auth_type = auth_type  # "jwt", "api_key", or "none"
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.email = email
        self.roles = roles or []
        self.permissions = permissions or []
        self.api_key_id = api_key_id
        self.request_id = request_id

    def require_permission(self, permission: str):
        """Raise 403 if user doesn't have required permission.

        Args:
            permission: Permission string to check

        Raises:
            HTTPException: 403 if permission not granted
        """
        if permission not in self.permissions and "SUPER_ADMIN" not in self.roles:
            logger.warning(
                f"Permission denied: {permission} required for user {self.user_id}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {permission} required",
            )

    def require_any_permission(self, permissions: list[str]):
        """Raise 403 if user doesn't have any of the required permissions.

        Args:
            permissions: List of permission strings (any one grants access)

        Raises:
            HTTPException: 403 if none of the permissions are granted
        """
        if "SUPER_ADMIN" in self.roles:
            return

        if not any(p in self.permissions for p in permissions):
            logger.warning(
                f"Permission denied: one of {permissions} required for user {self.user_id}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: one of {permissions} required",
            )

    def require_role(self, role: str):
        """Raise 403 if user doesn't have required role.

        Args:
            role: Role string to check

        Raises:
            HTTPException: 403 if role not assigned
        """
        if role not in self.roles and "SUPER_ADMIN" not in self.roles:
            logger.warning(f"Role denied: {role} required for user {self.user_id}")
            raise HTTPException(
                status_code=403,
                detail=f"Role required: {role}",
            )

    def is_own_resource(self, resource_user_id: str) -> bool:
        """Check if the authenticated user owns the resource.

        Args:
            resource_user_id: User ID of the resource owner

        Returns:
            True if user owns the resource or is admin
        """
        if "SUPER_ADMIN" in self.roles or "ADMIN" in self.roles:
            return True
        return self.user_id == resource_user_id


async def get_auth_context(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> AuthContext:
    """Extract authentication context from request.

    Supports multiple authentication methods:
    - JWT Bearer token (from Identity Core API)
    - API Key (X-API-Key header)
    - No authentication (for public endpoints)

    Args:
        request: FastAPI request object
        credentials: Optional Bearer token from Authorization header

    Returns:
        AuthContext with authentication details
    """
    # Extract request ID for correlation
    request_id = request.headers.get("X-Request-ID")

    # Check for API key first (header-based auth)
    api_key = request.headers.get(settings.API_KEY_HEADER)
    if api_key:
        return await _validate_api_key(api_key, request_id)

    # Check for JWT token
    if credentials:
        return await _validate_jwt(credentials.credentials, request_id)

    # No authentication provided
    return AuthContext(authenticated=False, request_id=request_id)


async def _validate_jwt(token: str, request_id: Optional[str] = None) -> AuthContext:
    """Validate JWT token from Identity Core API.

    Args:
        token: JWT token string
        request_id: Request correlation ID

    Returns:
        AuthContext with validated user information

    Raises:
        HTTPException: 401 if token is invalid or expired
    """
    try:
        # Decode and verify the token
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={
                "verify_exp": True,
                "verify_iat": True,
                "require": ["sub", "exp", "iat"],
            },
        )

        jwt_payload = JWTPayload(payload)

        # Additional expiration check (belt and suspenders)
        if jwt_payload.is_expired:
            raise HTTPException(status_code=401, detail="Token expired")

        logger.debug(f"JWT validated for user {jwt_payload.user_id}")

        return AuthContext(
            authenticated=True,
            auth_type="jwt",
            user_id=jwt_payload.user_id,
            tenant_id=jwt_payload.tenant_id,
            email=jwt_payload.email,
            roles=jwt_payload.roles,
            permissions=jwt_payload.permissions,
            request_id=request_id,
        )

    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


async def _validate_api_key(
    api_key: str, request_id: Optional[str] = None
) -> AuthContext:
    """Validate API key.

    Args:
        api_key: API key string from header
        request_id: Request correlation ID

    Returns:
        AuthContext with API key permissions

    Raises:
        HTTPException: 401 if API key is invalid or expired
    """
    # Import here to avoid circular imports
    from app.infrastructure.persistence.api_key_repository import get_api_key_repository

    repo = get_api_key_repository()
    api_key_data = await repo.validate_key(api_key)

    if not api_key_data:
        logger.warning("Invalid API key attempted")
        raise HTTPException(status_code=401, detail="Invalid API key")

    if api_key_data.is_expired:
        logger.warning(f"Expired API key used: {api_key_data.id}")
        raise HTTPException(status_code=401, detail="API key expired")

    if not api_key_data.is_active:
        logger.warning(f"Inactive API key used: {api_key_data.id}")
        raise HTTPException(status_code=401, detail="API key is inactive")

    logger.debug(f"API key validated: {api_key_data.id}")

    return AuthContext(
        authenticated=True,
        auth_type="api_key",
        tenant_id=str(api_key_data.tenant_id),
        permissions=api_key_data.scopes,
        api_key_id=str(api_key_data.id),
        request_id=request_id,
    )


# =============================================================================
# Dependency Factories
# =============================================================================


def require_auth(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    """Dependency that requires authentication.

    Use this as a dependency for endpoints that require any authentication.

    Returns:
        AuthContext if authenticated

    Raises:
        HTTPException: 401 if not authenticated
    """
    if not auth.authenticated:
        raise HTTPException(status_code=401, detail="Authentication required")
    return auth


def require_permission(permission: str):
    """Dependency factory that requires specific permission.

    Usage:
        @router.post("/admin/action")
        async def admin_action(auth: AuthContext = Depends(require_permission("admin:write"))):
            ...

    Args:
        permission: Permission string required

    Returns:
        Dependency function that validates permission
    """

    def _require(auth: AuthContext = Depends(require_auth)) -> AuthContext:
        auth.require_permission(permission)
        return auth

    return _require


def require_any_permission(permissions: list[str]):
    """Dependency factory that requires any of the specified permissions.

    Args:
        permissions: List of permission strings (any one grants access)

    Returns:
        Dependency function that validates permissions
    """

    def _require(auth: AuthContext = Depends(require_auth)) -> AuthContext:
        auth.require_any_permission(permissions)
        return auth

    return _require


def require_role(role: str):
    """Dependency factory that requires specific role.

    Args:
        role: Role string required

    Returns:
        Dependency function that validates role
    """

    def _require(auth: AuthContext = Depends(require_auth)) -> AuthContext:
        auth.require_role(role)
        return auth

    return _require


def optional_auth(
    auth: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    """Dependency for endpoints where authentication is optional.

    Returns the auth context regardless of authentication status.

    Returns:
        AuthContext (may be unauthenticated)
    """
    return auth


# =============================================================================
# Biometric-Specific Permission Helpers
# =============================================================================

# Permission constants for biometric operations
PERM_BIOMETRIC_ENROLL = "biometric:enroll"
PERM_BIOMETRIC_VERIFY = "biometric:verify"
PERM_BIOMETRIC_SEARCH = "biometric:search"
PERM_BIOMETRIC_DELETE = "biometric:delete"
PERM_BIOMETRIC_LIVENESS = "biometric:liveness"
PERM_BIOMETRIC_ADMIN = "biometric:admin"
PERM_BIOMETRIC_EXPORT = "biometric:export"
PERM_BIOMETRIC_IMPORT = "biometric:import"


def require_biometric_enroll():
    """Require biometric enrollment permission."""
    return require_permission(PERM_BIOMETRIC_ENROLL)


def require_biometric_verify():
    """Require biometric verification permission."""
    return require_permission(PERM_BIOMETRIC_VERIFY)


def require_biometric_search():
    """Require biometric search permission."""
    return require_permission(PERM_BIOMETRIC_SEARCH)


def require_biometric_delete():
    """Require biometric delete permission."""
    return require_permission(PERM_BIOMETRIC_DELETE)


def require_biometric_admin():
    """Require biometric admin permission."""
    return require_any_permission([PERM_BIOMETRIC_ADMIN, "SUPER_ADMIN"])
