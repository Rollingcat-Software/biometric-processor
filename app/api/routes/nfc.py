"""NFC document routes — MRZ parsing + eMRTD passive authentication.

Two first-class endpoints back the identity-core-api ``NfcController`` /
``NfcDocumentAuthHandler`` so chip-read passports / ID cards can be both parsed
and cryptographically trust-verified without the manual-KYC data-extract route:

- ``POST /nfc/mrz`` — pure MRZ string parsing (DG1 / raw MRZ). No OCR, no DB.
- ``POST /nfc/verify-authenticity`` — ICAO 9303 Part 11 **passive
  authentication**: confirm the chip's Data Groups match the signed hashes in
  EF.SOD, the SOD's CMS signature verifies under the Document Signer cert, and
  that DS chains to a trusted CSCA root. Pure Python crypto
  (``asn1crypto`` + ``cryptography``); CPU-only, no GPU, no ML.

The legacy ``/verification/data-extract`` endpoint is left untouched.
"""

from __future__ import annotations

import base64
import binascii
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.domain.services.emrtd_passive_auth import EmrtdPassiveAuthService
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


# ============================================================================
# Passive authentication — POST /nfc/verify-authenticity
# ============================================================================


class VerifyAuthenticityRequest(BaseModel):
    """Input for ``POST /nfc/verify-authenticity``.

    Field names are frozen against the agent-api JSON contract so the Java
    ``NfcDocumentAuthHandler`` (via ``BiometricProcessorClient.postJson``) maps
    without a translation layer.
    """

    sod_b64: str = Field(
        ...,
        description="Base64 (standard) of EF.SOD DER — the CMS SignedData / "
        "Document Security Object read from the chip.",
    )
    data_groups: Dict[str, str] = Field(
        ...,
        description="Map of DG number (as a string, '1'..'16') -> base64 of the "
        "raw DG bytes (full ICAO TLV) the client read from the chip. At least "
        "one entry required.",
    )


class VerifyAuthenticityResponse(BaseModel):
    """Authoritative passive-authentication verdict."""

    is_authentic: bool = False
    reason: str = ""
    reason_code: str = "SOD_PARSE_ERROR"
    ds_subject: Optional[str] = None
    ds_serial: Optional[str] = None
    csca_matched: bool = False
    dg_hash_results: Dict[str, bool] = Field(default_factory=dict)
    sod_hash_algorithm: Optional[str] = None


def _load_csca_trust_store(trust_dir: str) -> list:
    """Load CSCA root certificates from the operator trust-store directory.

    Accepts PEM and DER encodings (``.pem``/``.crt``/``.cer``/``.der``). Files
    that fail to parse are skipped with a warning rather than aborting the
    whole load — a single bad file must not knock out an otherwise-valid store.
    Returns a list of ``cryptography`` Certificate objects (possibly empty).
    """
    from cryptography.x509 import load_der_x509_certificate, load_pem_x509_certificate

    certs: list = []
    base = Path(trust_dir)
    if not base.is_dir():
        logger.warning("CSCA trust dir does not exist: %s", trust_dir)
        return certs

    for path in sorted(base.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {
            ".pem",
            ".crt",
            ".cer",
            ".der",
        }:
            continue
        try:
            raw = path.read_bytes()
        except OSError as exc:  # pragma: no cover — fs error
            logger.warning("Could not read CSCA cert %s: %s", path.name, exc)
            continue
        loaded = False
        # Try PEM first (may contain multiple concatenated certs), then DER.
        try:
            text = raw
            marker = b"-----BEGIN CERTIFICATE-----"
            if marker in text:
                for block in text.split(marker)[1:]:
                    pem = marker + block.split(b"-----END CERTIFICATE-----")[0] + (
                        b"-----END CERTIFICATE-----\n"
                    )
                    certs.append(load_pem_x509_certificate(pem))
                    loaded = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed PEM parse of %s: %s", path.name, exc)
        if not loaded:
            try:
                certs.append(load_der_x509_certificate(raw))
                loaded = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed DER parse of %s: %s", path.name, exc)
        if not loaded:
            logger.warning("Skipped unparseable CSCA cert: %s", path.name)

    logger.info("Loaded %d CSCA trust anchor(s) from %s", len(certs), trust_dir)
    return certs


@lru_cache(maxsize=4)
def _csca_certs_cached(trust_dir: str, mtime_ns: int) -> tuple:
    """Cache trust-store loads keyed by (dir, mtime) so a re-provisioned store
    is picked up automatically (mtime changes) without a process restart."""
    return tuple(_load_csca_trust_store(trust_dir))


def _get_passive_auth_service() -> EmrtdPassiveAuthService:
    """Build the passive-auth service with the current CSCA trust anchors."""
    trust_dir = settings.NFC_CSCA_TRUST_DIR
    try:
        mtime_ns = Path(trust_dir).stat().st_mtime_ns
    except OSError:
        mtime_ns = 0
    certs = list(_csca_certs_cached(trust_dir, mtime_ns))
    return EmrtdPassiveAuthService(csca_certificates=certs)


def _decode_b64(value: str, field_name: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} is not valid base64: {exc}",
        ) from exc


@router.post(
    "/verify-authenticity",
    response_model=VerifyAuthenticityResponse,
    summary="Verify eMRTD chip authenticity (passive authentication)",
    description=(
        "ICAO 9303 Part 11 passive authentication. Accepts the chip's EF.SOD "
        "(Document Security Object) and the Data Groups the client read, then "
        "verifies (a) each DG hash matches the signed value in the SOD's LDS "
        "Security Object, (b) the SOD's CMS signature verifies against the "
        "embedded Document Signer certificate, and (c) that DS certificate "
        "chains to a trusted CSCA root from the operator trust store. "
        "Fail-closed: is_authentic is true only when all three checks pass. "
        "Pure Python crypto — no GPU, no ML."
    ),
)
async def verify_authenticity(
    payload: VerifyAuthenticityRequest,
) -> VerifyAuthenticityResponse:
    """Run passive authentication over a chip-read EF.SOD + Data Groups."""

    if not payload.data_groups:
        raise HTTPException(
            status_code=400,
            detail="data_groups must contain at least one Data Group.",
        )

    sod_der = _decode_b64(payload.sod_b64, "sod_b64")

    decoded_dgs: Dict[int, bytes] = {}
    for key, value in payload.data_groups.items():
        try:
            dg_number = int(key)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"data_groups key '{key}' is not a valid DG number.",
            ) from exc
        decoded_dgs[dg_number] = _decode_b64(value, f"data_groups['{key}']")

    service = _get_passive_auth_service()
    result = service.verify(sod_der=sod_der, data_groups=decoded_dgs)

    logger.info(
        "NFC /verify-authenticity: is_authentic=%s reason_code=%s csca_matched=%s "
        "ds_subject=%s dgs=%s",
        result.is_authentic,
        result.reason_code.value,
        result.csca_matched,
        result.ds_subject,
        sorted(decoded_dgs.keys()),
    )

    return VerifyAuthenticityResponse(**result.to_dict())
