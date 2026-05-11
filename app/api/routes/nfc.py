"""NFC document MRZ parsing route.

Exposes the existing ``mrz_parser`` machinery as a first-class endpoint so the
identity-core-api ``NfcController`` can verify Machine-Readable Zones from
chip-read passports / ID cards (DG1) and surface structured fields back to
clients without falling back to the verification-pipeline data-extract route
(which is geared towards manual-KYC document scans).

This route is intentionally narrow:
- Pure string parsing — no OCR, no ML, no DB writes
- Input contract matches the task spec (T2-A, INVESTIGATION 2026-05-07 P1):
  ``{"mrz_text": "...", "dg1_bytes_b64": null}`` (exactly one required)
- Output contract matches the task spec — flat structured fields plus
  ``checksum_valid`` boolean and a ``checksum_failures`` list of field names
  that failed their ICAO 9303 check-digit verification

The legacy ``/verification/data-extract`` endpoint is left untouched.
"""

from __future__ import annotations

import base64
import binascii
import logging
import re
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.domain.services.mrz_parser import (
    MRZData,
    detect_and_parse_mrz,
    format_date,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/nfc",
    tags=["NFC Document"],
)


# ----------------------------------------------------------------------------
# Request / response models
# ----------------------------------------------------------------------------


class MrzParseRequest(BaseModel):
    """Input for ``POST /nfc/mrz``.

    Exactly one of ``mrz_text`` or ``dg1_bytes_b64`` must be supplied:

    - ``mrz_text`` — raw MRZ string (2 lines x 44 chars for TD3 passports,
      3 lines x 30 chars for TD1 ID cards) separated by ``\\n``.
    - ``dg1_bytes_b64`` — base64-encoded ICAO Data Group 1 bytes. DG1 wraps
      the MRZ in a TLV envelope (5F1F tag); this route strips the wrapper
      and parses the remaining ASCII MRZ string.
    """

    mrz_text: Optional[str] = Field(
        default=None,
        description="Raw MRZ string (2-3 lines separated by newline).",
    )
    dg1_bytes_b64: Optional[str] = Field(
        default=None,
        description="Base64-encoded ICAO DG1 bytes (TLV-wrapped MRZ).",
    )


class MrzParseResponse(BaseModel):
    """Output for ``POST /nfc/mrz``.

    Field naming mirrors the T2-A spec exactly so the Java caller can map
    to a record without a translation layer.
    """

    document_type: Optional[str] = None
    issuing_country: Optional[str] = None
    surname: Optional[str] = None
    given_names: Optional[str] = None
    document_number: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[str] = None
    sex: Optional[str] = None
    date_of_expiry: Optional[str] = None
    personal_number: Optional[str] = None
    checksum_valid: bool = False
    checksum_failures: list[str] = Field(default_factory=list)
    mrz_format: Optional[str] = None  # "TD1" or "TD3" — handy for diagnostics


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


# Maps mrz_parser error strings to the canonical field-name tokens that the
# Java caller persists in audit metadata. Keep this list short and stable —
# the upstream parser only ever emits these five error messages.
_CHECKSUM_FAILURE_FIELDS: dict[str, str] = {
    "Document number check digit invalid": "document_number",
    "Date of birth check digit invalid": "date_of_birth",
    "Expiry date check digit invalid": "date_of_expiry",
    "Optional data check digit invalid": "personal_number",
    "Overall composite check digit invalid": "composite",
}


def _decode_dg1_to_mrz_text(dg1_b64: str) -> str:
    """Extract the ASCII MRZ string from a base64-encoded DG1 blob.

    DG1 is TLV-encoded: the outermost tag is 0x61 (Application 1), wrapping a
    0x5F1F tag whose value is the raw MRZ ASCII bytes. Different reader
    libraries produce slightly different envelopes (some prepend extra
    headers, some omit the outer 0x61 wrapper), so we use a permissive
    strategy: decode base64, then locate the first run of contiguous
    MRZ-legal characters (A-Z, 0-9, '<') at least 60 chars long and treat
    that as the MRZ payload, splitting it into 30- or 44-char lines.
    """
    try:
        raw = base64.b64decode(dg1_b64, validate=False)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"dg1_bytes_b64 is not valid base64: {exc}",
        ) from exc

    # MRZ characters are restricted to A-Z, 0-9, '<'. Find the longest
    # contiguous run in the decoded byte string. We tolerate stray spaces
    # but not other binary noise.
    try:
        ascii_text = raw.decode("ascii", errors="ignore")
    except UnicodeDecodeError as exc:  # pragma: no cover — errors="ignore"
        raise HTTPException(
            status_code=400,
            detail=f"DG1 bytes contain unparseable data: {exc}",
        ) from exc

    runs = re.findall(r"[A-Z0-9<]{20,}", ascii_text)
    if not runs:
        raise HTTPException(
            status_code=400,
            detail="No MRZ payload found in DG1 bytes (no A-Z0-9< run >= 20 chars).",
        )

    # Pick the longest run. TD3 = 88 chars total, TD1 = 90 chars total.
    payload = max(runs, key=len)

    if len(payload) >= 88 and len(payload) % 44 == 0:
        # TD3 — 2 lines x 44 chars
        return "\n".join(payload[i:i + 44] for i in range(0, len(payload), 44))
    if len(payload) >= 90 and len(payload) % 30 == 0:
        # TD1 — 3 lines x 30 chars
        return "\n".join(payload[i:i + 30] for i in range(0, len(payload), 30))

    # Fallback: hand the raw run to detect_and_parse_mrz and let it figure
    # out the format. detect_and_parse_mrz auto-splits on newlines so we
    # break on most-likely boundaries.
    if len(payload) >= 88:
        return "\n".join(payload[i:i + 44] for i in range(0, len(payload), 44))
    return "\n".join(payload[i:i + 30] for i in range(0, len(payload), 30))


def _failures_from_errors(errors: list[str]) -> list[str]:
    """Map parser error strings to canonical field tokens.

    Unknown error strings fall through as-is so callers still see a hint
    rather than a silent drop.
    """
    return [_CHECKSUM_FAILURE_FIELDS.get(err, err) for err in errors]


def _to_response(mrz: MRZData) -> MrzParseResponse:
    return MrzParseResponse(
        document_type=mrz.document_type or None,
        issuing_country=mrz.country_code or None,
        surname=mrz.surname or None,
        given_names=mrz.given_names or None,
        document_number=mrz.document_number or None,
        nationality=mrz.nationality or None,
        date_of_birth=format_date(mrz.date_of_birth) if mrz.date_of_birth else None,
        sex=mrz.sex or None,
        date_of_expiry=format_date(mrz.expiry_date) if mrz.expiry_date else None,
        # Personal number lives in optional_data_1 for TD3 (chars 28-42 of
        # line 2). TD1 ID cards put the national identifier there too,
        # though the layout differs.
        personal_number=mrz.optional_data_1 or None,
        checksum_valid=mrz.check_digits_valid,
        checksum_failures=_failures_from_errors(mrz.errors),
        mrz_format=mrz.format,
    )


# ----------------------------------------------------------------------------
# Route
# ----------------------------------------------------------------------------


@router.post(
    "/mrz",
    response_model=MrzParseResponse,
    summary="Parse an NFC document MRZ",
    description=(
        "Parses a Machine-Readable Zone (TD1 ID card or TD3 passport) and "
        "returns structured identity fields plus ICAO 9303 check-digit "
        "validation results. Pure string parsing — no OCR, no DB writes. "
        "Caller must supply exactly one of `mrz_text` or `dg1_bytes_b64`."
    ),
)
async def parse_mrz(payload: MrzParseRequest) -> MrzParseResponse:
    """Parse MRZ supplied either as raw text or as DG1 bytes."""

    if not payload.mrz_text and not payload.dg1_bytes_b64:
        raise HTTPException(
            status_code=400,
            detail="Provide either mrz_text or dg1_bytes_b64.",
        )
    if payload.mrz_text and payload.dg1_bytes_b64:
        raise HTTPException(
            status_code=400,
            detail="Provide exactly one of mrz_text or dg1_bytes_b64, not both.",
        )

    if payload.dg1_bytes_b64:
        mrz_text = _decode_dg1_to_mrz_text(payload.dg1_bytes_b64)
        logger.info("NFC /mrz: parsed DG1 envelope, recovered %d-char MRZ payload",
                    len(mrz_text.replace("\n", "")))
    else:
        mrz_text = payload.mrz_text  # type: ignore[assignment]

    parsed = detect_and_parse_mrz(mrz_text)
    if parsed is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Could not parse MRZ. Expected 2 lines x 44 chars (TD3 passport)"
                " or 3 lines x 30 chars (TD1 ID card)."
            ),
        )

    response = _to_response(parsed)
    logger.info(
        "NFC /mrz: format=%s doc_type=%s country=%s checksum_valid=%s failures=%s",
        response.mrz_format,
        response.document_type,
        response.issuing_country,
        response.checksum_valid,
        response.checksum_failures,
    )
    return response
