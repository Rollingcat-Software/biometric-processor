"""Admin dashboard for biometric processor.

Provides web-based monitoring and management interface.
"""

from app.admin.router import admin_router
from app.admin.api import admin_api_router

__all__ = [
    "admin_router",
    "admin_api_router",
]
