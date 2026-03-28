"""Fingerprint biometric endpoints -- DISABLED.

Fingerprint biometric processing is not available on the server side.
All endpoints return HTTP 501 Not Implemented with a message directing
callers to use WebAuthn for device-based fingerprint authentication.

The identity-core-api FingerprintAuthHandler already delegates to
WebAuthn (FIDO2) instead of server-side biometric processing.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Fingerprint"])

_NOT_IMPLEMENTED_DETAIL = (
    "Fingerprint biometric processing not available. "
    "Use WebAuthn for device-based fingerprint authentication."
)


def _fingerprint_501() -> JSONResponse:
    """Return a standard 501 response for all fingerprint endpoints."""
    return JSONResponse(
        status_code=501,
        content={
            "success": False,
            "message": _NOT_IMPLEMENTED_DETAIL,
            "modality": "fingerprint",
            "alternative": "WebAuthn (FIDO2)",
        },
    )


@router.post("/fingerprint/enroll")
async def enroll_fingerprint() -> JSONResponse:
    """Fingerprint enrollment -- not implemented (use WebAuthn)."""
    logger.info("Fingerprint enroll requested -- returning 501")
    return _fingerprint_501()


@router.post("/fingerprint/verify")
async def verify_fingerprint() -> JSONResponse:
    """Fingerprint verification -- not implemented (use WebAuthn)."""
    logger.info("Fingerprint verify requested -- returning 501")
    return _fingerprint_501()


@router.delete("/fingerprint/{user_id}")
async def delete_fingerprint(user_id: str) -> JSONResponse:
    """Fingerprint deletion -- not implemented (use WebAuthn)."""
    logger.info(f"Fingerprint delete requested for user_id={user_id} -- returning 501")
    return _fingerprint_501()
