"""eMRTD passive authentication (ICAO 9303 Part 11) — CPU-only, pure crypto.

Passive Authentication proves that the Data Groups read from an ePassport /
eID chip are genuine and unmodified, and that they were signed by a legitimate
issuing authority. It is the lightweight, server-side trust check that does NOT
need the physical chip (unlike Active / Chip Authentication), so it runs fine
on a CPU-only box with no GPU and no heavy ML.

The check has three independent parts (ALL must pass for ``is_authentic``):

1. **Data Group integrity.** The Document Security Object (EF.SOD) embeds an
   ``LDSSecurityObject`` listing the expected hash of every Data Group, under a
   named digest algorithm. For each DG the client read, we hash the raw DG
   bytes and compare to the stored value.
2. **SOD signature.** EF.SOD is a CMS ``SignedData`` (RFC 5652). We verify the
   signer's signature over the signed attributes (or directly over the
   ``LDSSecurityObject`` eContent when there are no signed attributes), using
   the Document Signer (DS) certificate embedded in the SOD.
3. **Certificate chain.** The DS certificate must chain to a trusted Country
   Signing CA (CSCA) root from an operator-provided trust store.

This module is deliberately framework-free: it takes bytes and returns a plain
dataclass, so it is trivially unit-testable with a self-signed CSCA/DS/SOD
fixture and carries no FastAPI / DB / ML dependencies.

Dependencies: ``asn1crypto`` (pure-Python ASN.1) + ``cryptography`` (signature
primitives). Both are CPU-only and already part of the pinned requirements.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from asn1crypto import algos, cms, core
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.x509 import load_der_x509_certificate
from cryptography.x509 import Certificate as CryptoCertificate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ASN.1 definitions not shipped by asn1crypto: the ICAO LDS Security Object.
# (ICAO 9303 Part 10, appendix). asn1crypto lets us declare these declaratively.
# ---------------------------------------------------------------------------


class DataGroupNumber(core.Integer):
    """A Data Group number (1..16)."""


class DataGroupHash(core.Sequence):
    """One ``{dataGroupNumber, dataGroupHashValue}`` entry."""

    _fields = [
        ("data_group_number", DataGroupNumber),
        ("data_group_hash_value", core.OctetString),
    ]


class DataGroupHashValues(core.SequenceOf):
    """The list of per-DG hash entries."""

    _child_spec = DataGroupHash


class LDSVersionInfo(core.Sequence):
    _fields = [
        ("lds_version", core.PrintableString),
        ("unicode_version", core.PrintableString),
    ]


class LDSSecurityObject(core.Sequence):
    """The eContent of EF.SOD — the signed manifest of DG hashes."""

    _fields = [
        ("version", core.Integer),
        ("hash_algorithm", algos.DigestAlgorithm),
        ("data_group_hash_values", DataGroupHashValues),
        ("lds_version_info", LDSVersionInfo, {"optional": True}),
    ]


# ICAO assigns this OID to the LDS Security Object eContent type.
_ICAO_LDS_SECURITY_OBJECT_OID = "2.23.136.1.1.1"

# Map asn1crypto digest-algorithm names to hashlib constructors. eMRTD only
# ever uses these; anything else is rejected (fail-closed, not silently weak).
_HASHLIB_BY_NAME: Dict[str, str] = {
    "sha1": "sha1",
    "sha224": "sha224",
    "sha256": "sha256",
    "sha384": "sha384",
    "sha512": "sha512",
}

# Map digest names to cryptography hash instances for signature verification.
_CRYPTO_HASH_BY_NAME = {
    "sha1": hashes.SHA1,
    "sha224": hashes.SHA224,
    "sha256": hashes.SHA256,
    "sha384": hashes.SHA384,
    "sha512": hashes.SHA512,
}


class ReasonCode(str, Enum):
    """Stable, machine-readable verdict codes (mirrors the API contract)."""

    OK = "OK"
    DG_HASH_MISMATCH = "DG_HASH_MISMATCH"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    DS_UNTRUSTED = "DS_UNTRUSTED"
    SOD_PARSE_ERROR = "SOD_PARSE_ERROR"
    NO_TRUST_STORE = "NO_TRUST_STORE"
    MISSING_DG = "MISSING_DG"
    UNSUPPORTED_ALGORITHM = "UNSUPPORTED_ALGORITHM"


@dataclass
class PassiveAuthResult:
    """Authoritative passive-authentication verdict."""

    is_authentic: bool
    reason: str
    reason_code: ReasonCode
    csca_matched: bool = False
    ds_subject: Optional[str] = None
    ds_serial: Optional[str] = None
    sod_hash_algorithm: Optional[str] = None
    dg_hash_results: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "is_authentic": self.is_authentic,
            "reason": self.reason,
            "reason_code": self.reason_code.value,
            "ds_subject": self.ds_subject,
            "ds_serial": self.ds_serial,
            "csca_matched": self.csca_matched,
            "dg_hash_results": self.dg_hash_results,
            "sod_hash_algorithm": self.sod_hash_algorithm,
        }


class EmrtdPassiveAuthService:
    """Stateless verifier for eMRTD passive authentication.

    The CSCA trust anchors are supplied at construction (a list of trusted CSCA
    certificates loaded from the operator trust store). Keeping the service
    stateless-per-request but anchor-injected makes it trivially testable with a
    self-signed CSCA fixture and free of any filesystem coupling.
    """

    def __init__(self, csca_certificates: Optional[list[CryptoCertificate]] = None) -> None:
        self._csca_certs = csca_certificates or []

    # -- public API --------------------------------------------------------

    def verify(
        self,
        sod_der: bytes,
        data_groups: Dict[int, bytes],
    ) -> PassiveAuthResult:
        """Run the full passive-authentication check.

        Args:
            sod_der: Raw DER bytes of EF.SOD (CMS SignedData / ContentInfo).
            data_groups: Mapping of DG number -> raw DG bytes the client read.
                The bytes MUST be the full DG TLV exactly as stored on the chip
                (that is what the issuer hashed when building the SOD).

        Returns:
            PassiveAuthResult — fail-closed: ``is_authentic`` is True only when
            DG integrity, the SOD signature, and the CSCA chain ALL pass.
        """
        # --- parse EF.SOD -> CMS SignedData -> LDSSecurityObject -----------
        try:
            signed_data, lds = self._parse_sod(sod_der)
        except Exception as exc:  # noqa: BLE001 — any parse failure is a reject
            logger.warning("EF.SOD parse failed: %s", exc)
            return PassiveAuthResult(
                is_authentic=False,
                reason=f"Could not parse EF.SOD: {exc}",
                reason_code=ReasonCode.SOD_PARSE_ERROR,
            )

        hash_name = lds["hash_algorithm"]["algorithm"].native
        sod_hash_algorithm = str(hash_name)
        if hash_name not in _HASHLIB_BY_NAME:
            return PassiveAuthResult(
                is_authentic=False,
                reason=f"Unsupported SOD hash algorithm: {hash_name}",
                reason_code=ReasonCode.UNSUPPORTED_ALGORITHM,
                sod_hash_algorithm=sod_hash_algorithm,
            )

        # DS certificate (subject/serial surfaced regardless of outcome).
        ds_cert = self._extract_ds_certificate(signed_data)
        ds_subject = ds_cert.subject.rfc4514_string() if ds_cert is not None else None
        ds_serial = format(ds_cert.serial_number, "X") if ds_cert is not None else None

        # --- (a) Data Group integrity -------------------------------------
        expected_hashes = self._lds_hash_map(lds)
        dg_hash_results: Dict[str, bool] = {}
        all_dg_ok = True
        if not data_groups:
            return PassiveAuthResult(
                is_authentic=False,
                reason="No data groups supplied to verify.",
                reason_code=ReasonCode.MISSING_DG,
                ds_subject=ds_subject,
                ds_serial=ds_serial,
                sod_hash_algorithm=sod_hash_algorithm,
            )
        for dg_number, dg_bytes in data_groups.items():
            expected = expected_hashes.get(dg_number)
            if expected is None:
                # The SOD does not even cover this DG → cannot be trusted.
                dg_hash_results[str(dg_number)] = False
                all_dg_ok = False
                continue
            actual = hashlib.new(
                _HASHLIB_BY_NAME[hash_name], dg_bytes
            ).digest()
            ok = _constant_time_eq(actual, expected)
            dg_hash_results[str(dg_number)] = ok
            all_dg_ok = all_dg_ok and ok

        if not all_dg_ok:
            mismatched = [k for k, v in dg_hash_results.items() if not v]
            return PassiveAuthResult(
                is_authentic=False,
                reason=f"Data group hash mismatch for DG(s): {', '.join(mismatched)}",
                reason_code=ReasonCode.DG_HASH_MISMATCH,
                ds_subject=ds_subject,
                ds_serial=ds_serial,
                sod_hash_algorithm=sod_hash_algorithm,
                dg_hash_results=dg_hash_results,
            )

        # --- (b) SOD signature over the LDS eContent ----------------------
        if ds_cert is None:
            return PassiveAuthResult(
                is_authentic=False,
                reason="EF.SOD carries no Document Signer certificate.",
                reason_code=ReasonCode.SIGNATURE_INVALID,
                sod_hash_algorithm=sod_hash_algorithm,
                dg_hash_results=dg_hash_results,
            )
        try:
            sig_ok = self._verify_sod_signature(signed_data, ds_cert, hash_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("EF.SOD signature verification raised: %s", exc)
            sig_ok = False
        if not sig_ok:
            return PassiveAuthResult(
                is_authentic=False,
                reason="EF.SOD CMS signature did not verify against the Document Signer cert.",
                reason_code=ReasonCode.SIGNATURE_INVALID,
                ds_subject=ds_subject,
                ds_serial=ds_serial,
                sod_hash_algorithm=sod_hash_algorithm,
                dg_hash_results=dg_hash_results,
            )

        # --- (c) DS -> CSCA chain -----------------------------------------
        if not self._csca_certs:
            # No trust anchors configured → we cannot assert authenticity.
            return PassiveAuthResult(
                is_authentic=False,
                reason="No CSCA trust anchors configured; cannot establish document signer trust.",
                reason_code=ReasonCode.NO_TRUST_STORE,
                ds_subject=ds_subject,
                ds_serial=ds_serial,
                sod_hash_algorithm=sod_hash_algorithm,
                dg_hash_results=dg_hash_results,
            )
        csca_matched = self._ds_chains_to_csca(ds_cert)
        if not csca_matched:
            return PassiveAuthResult(
                is_authentic=False,
                reason="Document Signer certificate does not chain to any trusted CSCA root.",
                reason_code=ReasonCode.DS_UNTRUSTED,
                ds_subject=ds_subject,
                ds_serial=ds_serial,
                sod_hash_algorithm=sod_hash_algorithm,
                dg_hash_results=dg_hash_results,
            )

        # All three checks passed.
        return PassiveAuthResult(
            is_authentic=True,
            reason="ok",
            reason_code=ReasonCode.OK,
            csca_matched=True,
            ds_subject=ds_subject,
            ds_serial=ds_serial,
            sod_hash_algorithm=sod_hash_algorithm,
            dg_hash_results=dg_hash_results,
        )

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _parse_sod(sod_der: bytes) -> tuple[cms.SignedData, LDSSecurityObject]:
        """Parse EF.SOD into its CMS SignedData and the inner LDSSecurityObject.

        EF.SOD may be wrapped in an ICAO application tag (0x77) or be a bare
        CMS ContentInfo. We strip a leading application wrapper if present.
        """
        data = sod_der
        # ICAO wraps EF.SOD in tag 0x77 (application 23). asn1crypto's
        # ContentInfo.load expects a plain SEQUENCE, so unwrap if needed.
        if data and data[0] == 0x77:
            data = core.load(data).contents

        content_info = cms.ContentInfo.load(data)
        if content_info["content_type"].native != "signed_data":
            raise ValueError(
                f"EF.SOD is not CMS signed_data (got {content_info['content_type'].native})"
            )
        signed_data: cms.SignedData = content_info["content"]

        encap = signed_data["encap_content_info"]
        econtent = encap["content"]
        if econtent is None:
            raise ValueError("EF.SOD eContent is absent")
        # econtent is an OctetString wrapping the LDSSecurityObject DER.
        lds = LDSSecurityObject.load(_as_octet_bytes(econtent))
        return signed_data, lds

    @staticmethod
    def _lds_hash_map(lds: LDSSecurityObject) -> Dict[int, bytes]:
        out: Dict[int, bytes] = {}
        for entry in lds["data_group_hash_values"]:
            out[int(entry["data_group_number"].native)] = entry["data_group_hash_value"].native
        return out

    @staticmethod
    def _extract_ds_certificate(
        signed_data: cms.SignedData,
    ) -> Optional[CryptoCertificate]:
        """Return the Document Signer cert embedded in the SOD, if any."""
        certs = signed_data["certificates"]
        if certs is None:
            return None
        for choice in certs:
            if choice.name == "certificate":
                der = choice.chosen.dump()
                return load_der_x509_certificate(der)
        return None

    def _verify_sod_signature(
        self,
        signed_data: cms.SignedData,
        ds_cert: CryptoCertificate,
        hash_name: str,
    ) -> bool:
        """Verify the single SignerInfo signature in the SOD.

        Per RFC 5652: when signed attributes are present, the signature is over
        the DER of the signed-attributes SET (re-tagged as a universal SET); the
        ``messageDigest`` attribute inside it must equal the hash of the
        eContent. When absent, the signature is directly over the eContent.
        """
        signer_infos = signed_data["signer_infos"]
        if len(signer_infos) == 0:
            return False
        signer_info = signer_infos[0]

        digest_alg = signer_info["digest_algorithm"]["algorithm"].native
        digest_name = digest_alg if digest_alg in _CRYPTO_HASH_BY_NAME else hash_name

        econtent_bytes = _as_octet_bytes(
            signed_data["encap_content_info"]["content"]
        )

        signed_attrs = signer_info["signed_attrs"]
        if signed_attrs is not None and len(signed_attrs) > 0:
            # messageDigest attr must match hash(eContent).
            md_attr = _find_attr(signed_attrs, "message_digest")
            if md_attr is None:
                return False
            expected_md = md_attr["values"][0].native
            actual_md = hashlib.new(
                _HASHLIB_BY_NAME.get(digest_name, digest_name), econtent_bytes
            ).digest()
            if not _constant_time_eq(actual_md, expected_md):
                return False
            # Signature input = DER of signed attrs re-tagged as universal SET.
            signed_bytes = signed_attrs.untag().dump()
        else:
            signed_bytes = econtent_bytes

        signature = signer_info["signature"].native
        sig_alg = signer_info["signature_algorithm"].signature_algo
        crypto_hash = _CRYPTO_HASH_BY_NAME.get(digest_name, hashes.SHA256)()

        public_key = ds_cert.public_key()
        try:
            if isinstance(public_key, rsa.RSAPublicKey):
                if sig_alg == "rsassa_pss":
                    pss_params = signer_info["signature_algorithm"]["parameters"]
                    salt_len = int(pss_params["salt_length"].native)
                    public_key.verify(
                        signature,
                        signed_bytes,
                        padding.PSS(
                            mgf=padding.MGF1(crypto_hash),
                            salt_length=salt_len,
                        ),
                        crypto_hash,
                    )
                else:
                    public_key.verify(
                        signature, signed_bytes, padding.PKCS1v15(), crypto_hash
                    )
            elif isinstance(public_key, ec.EllipticCurvePublicKey):
                public_key.verify(
                    signature, signed_bytes, ec.ECDSA(crypto_hash)
                )
            else:
                logger.warning(
                    "Unsupported DS public key type for SOD verification: %s",
                    type(public_key).__name__,
                )
                return False
            return True
        except InvalidSignature:
            return False

    def _ds_chains_to_csca(self, ds_cert: CryptoCertificate) -> bool:
        """True if the DS cert's signature verifies under a trusted CSCA key.

        eMRTD chains are short (DS signed directly by a CSCA root), so a direct
        issuer-match + signature check is sufficient and avoids pulling in a
        full path-validation engine. We match candidate CSCAs by subject==issuer
        then cryptographically verify the DS signature under the CSCA key.
        """
        for csca in self._csca_certs:
            if csca.subject != ds_cert.issuer:
                continue
            if _cert_signed_by(ds_cert, csca):
                return True
        return False


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def _constant_time_eq(a: bytes, b: bytes) -> bool:
    import hmac

    return hmac.compare_digest(a, b)


def _as_octet_bytes(value) -> bytes:
    """Return the raw bytes carried by a CMS eContent / OctetString field."""
    if value is None:
        raise ValueError("missing content")
    native = value.native
    if isinstance(native, bytes):
        return native
    # ParsableOctetString: fall back to its DER dump of the parsed child.
    return value.parsed.dump()


def _find_attr(signed_attrs, name: str):
    for attr in signed_attrs:
        if attr["type"].native == name:
            return attr
    return None


def _cert_signed_by(child: CryptoCertificate, issuer: CryptoCertificate) -> bool:
    """Verify ``child``'s signature using ``issuer``'s public key."""
    issuer_key = issuer.public_key()
    try:
        if isinstance(issuer_key, rsa.RSAPublicKey):
            issuer_key.verify(
                child.signature,
                child.tbs_certificate_bytes,
                padding.PKCS1v15(),
                child.signature_hash_algorithm,
            )
        elif isinstance(issuer_key, ec.EllipticCurvePublicKey):
            issuer_key.verify(
                child.signature,
                child.tbs_certificate_bytes,
                ec.ECDSA(child.signature_hash_algorithm),
            )
        else:
            return False
        return True
    except InvalidSignature:
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("CSCA chain check raised: %s", exc)
        return False
