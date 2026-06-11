# CSCA Trust Store (eMRTD Passive Authentication)

This directory holds the **Country Signing CA (CSCA) root certificates** used to
establish trust in the Document Signer (DS) certificate embedded in an ePassport
/ eID `EF.SOD` during passive authentication
(`POST /api/v1/nfc/verify-authenticity`).

## What to drop here (operator deliverable)

- One file per CSCA root certificate.
- Accepted formats: PEM (`.pem`, `.crt`, `.cer`), or DER (`.der`, `.cer`).
- Source the certificates from the **ICAO Public Key Directory (PKD)** master
  list, or directly from the issuing authority (e.g. for Turkish eID, the
  Turkish CSCA root). Validate them out-of-band before installing.

## Behavior

- **Empty store** (only this README): `/nfc/verify-authenticity` returns
  `is_authentic: false` with `reason_code: NO_TRUST_STORE` — fail-closed. No
  document can be marked authentic until at least one trusted CSCA is present.
- The store directory is configurable via the `NFC_CSCA_TRUST_DIR` env var
  (defaults to this directory). Files are loaded at request time, so adding a
  new CSCA root takes effect without a rebuild — only a re-read.

## Security notes

- Treat this directory as a trust anchor: write access to it equals the ability
  to forge document trust. Lock down filesystem permissions accordingly.
- Only CSCA **root** certs belong here. Document Signer (DS) certs are supplied
  per-request inside the SOD; never add a DS cert as a trust anchor.
