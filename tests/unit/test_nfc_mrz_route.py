"""Unit tests for the /api/v1/nfc/mrz route.

Uses the canonical ICAO 9303 example MRZs (UTOPIAN passport + ID card) to
prove the round-trip from JSON request to structured response and verifies
the corrupted-checksum failure path. The route is mounted on a minimal
FastAPI app to avoid the global ``app.main`` import path, which pulls in
ML/model wiring not relevant to pure-string MRZ parsing.
"""

from __future__ import annotations

import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.nfc import router as nfc_router


# Canonical ICAO 9303 TD3 (passport) — both check digits valid, used as
# the example in the spec itself.
TD3_LINE1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
TD3_LINE2 = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"
TD3_VALID_MRZ = f"{TD3_LINE1}\n{TD3_LINE2}"

# Canonical ICAO 9303 TD1 (ID card) — both check digits valid.
TD1_LINE1 = "I<UTOD231458907<<<<<<<<<<<<<<<"
TD1_LINE2 = "7408122F1204159UTO<<<<<<<<<<<6"
TD1_LINE3 = "ERIKSSON<<ANNA<MARIA<<<<<<<<<<"
TD1_VALID_MRZ = f"{TD1_LINE1}\n{TD1_LINE2}\n{TD1_LINE3}"


@pytest.fixture
def client() -> TestClient:
    """Build a minimal FastAPI app that includes only the NFC router."""
    app = FastAPI()
    app.include_router(nfc_router, prefix="/api/v1")
    return TestClient(app)


# ----------------------------------------------------------------------------
# Happy path
# ----------------------------------------------------------------------------


def test_parse_valid_td3_passport(client: TestClient) -> None:
    response = client.post(
        "/api/v1/nfc/mrz",
        json={"mrz_text": TD3_VALID_MRZ},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["mrz_format"] == "TD3"
    assert body["document_type"] == "P"
    assert body["issuing_country"] == "UTO"
    assert body["surname"] == "ERIKSSON"
    assert body["given_names"] == "ANNA MARIA"
    assert body["document_number"] == "L898902C3"
    assert body["nationality"] == "UTO"
    # parser converts YYMMDD -> YYYY-MM-DD; YY < 30 means 20YY
    assert body["date_of_birth"] == "1974-08-12"
    assert body["sex"] == "F"
    assert body["date_of_expiry"] == "2012-04-15"
    assert body["checksum_valid"] is True
    assert body["checksum_failures"] == []


def test_parse_valid_td1_id_card(client: TestClient) -> None:
    response = client.post(
        "/api/v1/nfc/mrz",
        json={"mrz_text": TD1_VALID_MRZ},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["mrz_format"] == "TD1"
    assert body["document_type"] == "I"
    assert body["issuing_country"] == "UTO"
    assert body["surname"] == "ERIKSSON"
    assert body["given_names"] == "ANNA MARIA"
    assert body["document_number"] == "D23145890"
    assert body["date_of_birth"] == "1974-08-12"
    assert body["sex"] == "F"
    assert body["checksum_valid"] is True
    assert body["checksum_failures"] == []


# ----------------------------------------------------------------------------
# Checksum failures
# ----------------------------------------------------------------------------


def test_corrupted_document_number_checksum_returns_200_with_failures(
    client: TestClient,
) -> None:
    """A single-bit flip in the document number breaks both its own check
    digit and the overall composite check digit. The route returns 200 with
    checksum_valid=False so the API caller can surface a domain-level 400 —
    the parse itself succeeded, only verification failed.
    """
    # Flip "C3" -> "C4" in the document-number block; original check digit
    # was 6 and stays 6 in line 2 col 9, so the doc# check digit fails.
    corrupted_line2 = "L898902C46UTO7408122F1204159ZE184226B<<<<<10"
    corrupted = f"{TD3_LINE1}\n{corrupted_line2}"

    response = client.post("/api/v1/nfc/mrz", json={"mrz_text": corrupted})
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["checksum_valid"] is False
    # We expect at least the document_number to be flagged; the composite
    # check digit may also fail because it incorporates the doc number.
    assert "document_number" in body["checksum_failures"]


def test_completely_corrupted_dob_field(client: TestClient) -> None:
    """Replacing the DOB digits with a different valid-looking value drops
    the DOB check digit, surfacing date_of_birth in failures."""
    # Replace "7408122" (dob + check) with "8001011"; new dob is 800101 and
    # its real check digit isn't 1, so this fails.
    corrupted_line2 = "L898902C36UTO8001011F1204159ZE184226B<<<<<10"
    corrupted = f"{TD3_LINE1}\n{corrupted_line2}"

    response = client.post("/api/v1/nfc/mrz", json={"mrz_text": corrupted})
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["checksum_valid"] is False
    assert "date_of_birth" in body["checksum_failures"]


# ----------------------------------------------------------------------------
# Error contract
# ----------------------------------------------------------------------------


def test_missing_both_inputs_returns_400(client: TestClient) -> None:
    response = client.post("/api/v1/nfc/mrz", json={})
    assert response.status_code == 400
    assert "mrz_text" in response.json()["detail"]


def test_both_inputs_supplied_returns_400(client: TestClient) -> None:
    response = client.post(
        "/api/v1/nfc/mrz",
        json={"mrz_text": TD3_VALID_MRZ, "dg1_bytes_b64": "AAAA"},
    )
    assert response.status_code == 400
    assert "exactly one" in response.json()["detail"].lower()


def test_garbage_mrz_text_returns_400(client: TestClient) -> None:
    response = client.post(
        "/api/v1/nfc/mrz",
        json={"mrz_text": "this is not an MRZ at all"},
    )
    assert response.status_code == 400


def test_invalid_base64_dg1_returns_400(client: TestClient) -> None:
    response = client.post(
        "/api/v1/nfc/mrz",
        # base64 has a strict alphabet; '*' is invalid, and the bytes that
        # come out won't match a parseable MRZ shape either way.
        json={"mrz_text": None, "dg1_bytes_b64": "***not-base64***"},
    )
    # Either base64 validation kicks in or the MRZ-payload search fails;
    # both flow through 400 as designed.
    assert response.status_code == 400


# ----------------------------------------------------------------------------
# DG1 envelope handling
# ----------------------------------------------------------------------------


def test_dg1_envelope_with_td3_payload(client: TestClient) -> None:
    """A minimal DG1 wrapper around the canonical TD3 MRZ should round-trip
    to the same parsed fields as raw MRZ text. We use the standard ICAO
    envelope: outer tag 0x61, length, inner tag 0x5F1F, length, ASCII MRZ.
    """
    raw_mrz = (TD3_LINE1 + TD3_LINE2).encode("ascii")
    # 0x5F1F + length-58 + payload (88 bytes); wrapped in 0x61 + length.
    inner = bytes([0x5F, 0x1F, 0x5C]) + raw_mrz  # 0x5C == 92 placeholder len
    outer = bytes([0x61, len(inner)]) + inner
    dg1_b64 = base64.b64encode(outer).decode("ascii")

    response = client.post(
        "/api/v1/nfc/mrz",
        json={"dg1_bytes_b64": dg1_b64},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mrz_format"] == "TD3"
    assert body["surname"] == "ERIKSSON"
    assert body["checksum_valid"] is True


def test_dg1_envelope_without_mrz_payload_returns_400(client: TestClient) -> None:
    """Random bytes with no contiguous A-Z0-9< run >= 20 chars."""
    dg1_b64 = base64.b64encode(b"\x00\x01\x02\x03\x04random binary noise").decode("ascii")
    response = client.post("/api/v1/nfc/mrz", json={"dg1_bytes_b64": dg1_b64})
    assert response.status_code == 400
