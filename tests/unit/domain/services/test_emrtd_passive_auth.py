"""Unit tests for eMRTD passive authentication (ICAO 9303 Part 11).

These tests build a complete self-signed CSCA -> DS -> EF.SOD fixture in-process
(no network, no external certs) and exercise the four authoritative outcomes the
contract guarantees:

- happy path  -> is_authentic=True / OK
- DG tamper   -> is_authentic=False / DG_HASH_MISMATCH
- bad sig     -> is_authentic=False / SIGNATURE_INVALID
- untrusted DS-> is_authentic=False / DS_UNTRUSTED
- no store    -> is_authentic=False / NO_TRUST_STORE  (fail-closed default)

The fixture mirrors a real EF.SOD: a CMS SignedData whose eContent is an ICAO
``LDSSecurityObject`` listing per-DG hashes, signed by a Document Signer cert
that itself is issued by a (test) CSCA root.
"""

from __future__ import annotations

import datetime
import hashlib

import pytest
from asn1crypto import cms, core
from asn1crypto import x509 as a_x509
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.x509.oid import NameOID

from app.domain.services.emrtd_passive_auth import (
    _ICAO_LDS_SECURITY_OBJECT_OID,
    EmrtdPassiveAuthService,
    LDSSecurityObject,
    ReasonCode,
)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _make_cert(
    subject_cn,
    issuer_cn,
    issuer_key,
    subject_pub,
    is_ca,
    sign_hash=None,
    *,
    not_before=None,
    not_after=None,
):
    sign_hash = sign_hash or hashes.SHA256()
    not_before = not_before or datetime.datetime(2020, 1, 1)
    not_after = not_after or datetime.datetime(2035, 1, 1)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, subject_cn),
            x509.NameAttribute(NameOID.COUNTRY_NAME, "TR"),
        ]
    )
    issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, issuer_cn),
            x509.NameAttribute(NameOID.COUNTRY_NAME, "TR"),
        ]
    )
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(subject_pub)
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
    )
    if is_ca:
        builder = builder.add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
    return builder.sign(issuer_key, sign_hash)


def _build_lds(data_groups: dict[int, bytes], hash_name: str = "sha256") -> bytes:
    hashfn = getattr(hashlib, hash_name)
    entries = [
        {"data_group_number": n, "data_group_hash_value": hashfn(b).digest()}
        for n, b in data_groups.items()
    ]
    lds = LDSSecurityObject(
        {
            "version": 0,
            "hash_algorithm": {"algorithm": hash_name},
            "data_group_hash_values": entries,
        }
    )
    return lds.dump()


def _build_sod(
    lds_der: bytes,
    ds_cert: x509.Certificate,
    ds_key,
    *,
    corrupt_signature: bool = False,
    hash_name: str = "sha256",
) -> bytes:
    """Assemble an EF.SOD (CMS ContentInfo/SignedData) over an LDS eContent."""
    crypto_hash = {"sha256": hashes.SHA256, "sha1": hashes.SHA1}[hash_name]()
    md = getattr(hashlib, hash_name)(lds_der).digest()

    signed_attrs = cms.CMSAttributes(
        [
            cms.CMSAttribute(
                {
                    "type": "content_type",
                    "values": [cms.ContentType(_ICAO_LDS_SECURITY_OBJECT_OID)],
                }
            ),
            cms.CMSAttribute(
                {"type": "message_digest", "values": [core.OctetString(md)]}
            ),
        ]
    )
    to_sign = signed_attrs.dump()

    if isinstance(ds_key, ec.EllipticCurvePrivateKey):
        sig = ds_key.sign(to_sign, ec.ECDSA(crypto_hash))
        sig_alg = "ecdsa"
    else:
        sig = ds_key.sign(to_sign, padding.PKCS1v15(), crypto_hash)
        sig_alg = "rsassa_pkcs1v15"

    if corrupt_signature:
        sig = bytes((sig[0] ^ 0xFF,)) + sig[1:]

    ds_a = a_x509.Certificate.load(
        ds_cert.public_bytes(serialization.Encoding.DER)
    )
    signer_info = cms.SignerInfo(
        {
            "version": "v1",
            "sid": cms.SignerIdentifier(
                {
                    "issuer_and_serial_number": cms.IssuerAndSerialNumber(
                        {"issuer": ds_a.issuer, "serial_number": ds_a.serial_number}
                    )
                }
            ),
            "digest_algorithm": {"algorithm": hash_name},
            "signed_attrs": signed_attrs,
            "signature_algorithm": {"algorithm": sig_alg},
            "signature": sig,
        }
    )
    signed_data = cms.SignedData(
        {
            "version": "v3",
            "digest_algorithms": [{"algorithm": hash_name}],
            "encap_content_info": {
                "content_type": _ICAO_LDS_SECURITY_OBJECT_OID,
                "content": lds_der,
            },
            "certificates": [ds_a],
            "signer_infos": [signer_info],
        }
    )
    return cms.ContentInfo(
        {"content_type": "signed_data", "content": signed_data}
    ).dump()


@pytest.fixture
def emrtd_fixture():
    """A coherent CSCA/DS/SOD set plus the data groups it covers."""
    csca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ds_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    csca_cert = _make_cert(
        "Test CSCA Root", "Test CSCA Root", csca_key, csca_key.public_key(), True
    )
    ds_cert = _make_cert(
        "Test Document Signer",
        "Test CSCA Root",
        csca_key,
        ds_key.public_key(),
        False,
    )

    data_groups = {
        1: b"\x61\x10DG1-MRZ-PAYLOAD!",
        2: b"\x75\x20" + b"FAKE_DG2_PORTRAIT_BYTES_32_LONG_",
    }
    lds_der = _build_lds(data_groups)
    sod_der = _build_sod(lds_der, ds_cert, ds_key)

    return {
        "csca_cert": csca_cert,
        "ds_cert": ds_cert,
        "ds_key": ds_key,
        "lds_der": lds_der,
        "sod_der": sod_der,
        "data_groups": data_groups,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEmrtdPassiveAuth:
    def test_happy_path_accepts_authentic_document(self, emrtd_fixture):
        svc = EmrtdPassiveAuthService(csca_certificates=[emrtd_fixture["csca_cert"]])
        result = svc.verify(
            sod_der=emrtd_fixture["sod_der"],
            data_groups=emrtd_fixture["data_groups"],
        )
        assert result.is_authentic is True
        assert result.reason_code == ReasonCode.OK
        assert result.csca_matched is True
        assert result.dg_hash_results == {"1": True, "2": True}
        assert result.sod_hash_algorithm == "sha256"
        assert "Document Signer" in (result.ds_subject or "")
        assert result.ds_serial  # hex serial present

    def test_dg_hash_mismatch_rejects(self, emrtd_fixture):
        svc = EmrtdPassiveAuthService(csca_certificates=[emrtd_fixture["csca_cert"]])
        tampered = dict(emrtd_fixture["data_groups"])
        tampered[2] = tampered[2] + b"TAMPER"  # any change breaks the DG2 hash
        result = svc.verify(sod_der=emrtd_fixture["sod_der"], data_groups=tampered)
        assert result.is_authentic is False
        assert result.reason_code == ReasonCode.DG_HASH_MISMATCH
        assert result.dg_hash_results["1"] is True
        assert result.dg_hash_results["2"] is False

    def test_bad_signature_rejects(self, emrtd_fixture):
        # Re-sign the SOD with a corrupted signature but otherwise-valid DGs,
        # so the verdict must hit the signature check (not the DG check).
        bad_sod = _build_sod(
            emrtd_fixture["lds_der"],
            emrtd_fixture["ds_cert"],
            emrtd_fixture["ds_key"],
            corrupt_signature=True,
        )
        svc = EmrtdPassiveAuthService(csca_certificates=[emrtd_fixture["csca_cert"]])
        result = svc.verify(
            sod_der=bad_sod, data_groups=emrtd_fixture["data_groups"]
        )
        assert result.is_authentic is False
        assert result.reason_code == ReasonCode.SIGNATURE_INVALID

    def test_untrusted_ds_rejects(self, emrtd_fixture):
        # A valid SOD, but the configured trust store holds a DIFFERENT CSCA
        # that did not issue the DS cert -> chain fails.
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_csca = _make_cert(
            "Other CSCA", "Other CSCA", other_key, other_key.public_key(), True
        )
        svc = EmrtdPassiveAuthService(csca_certificates=[other_csca])
        result = svc.verify(
            sod_der=emrtd_fixture["sod_der"],
            data_groups=emrtd_fixture["data_groups"],
        )
        assert result.is_authentic is False
        assert result.reason_code == ReasonCode.DS_UNTRUSTED

    def test_empty_trust_store_fails_closed(self, emrtd_fixture):
        # No CSCA anchors at all -> cannot assert trust (fail-closed default).
        svc = EmrtdPassiveAuthService(csca_certificates=[])
        result = svc.verify(
            sod_der=emrtd_fixture["sod_der"],
            data_groups=emrtd_fixture["data_groups"],
        )
        assert result.is_authentic is False
        assert result.reason_code == ReasonCode.NO_TRUST_STORE
        # DG integrity still computed + surfaced even when trust store is empty.
        assert result.dg_hash_results == {"1": True, "2": True}

    def test_unparseable_sod_fails_closed(self, emrtd_fixture):
        svc = EmrtdPassiveAuthService(csca_certificates=[emrtd_fixture["csca_cert"]])
        result = svc.verify(
            sod_der=b"not a real SOD", data_groups=emrtd_fixture["data_groups"]
        )
        assert result.is_authentic is False
        assert result.reason_code == ReasonCode.SOD_PARSE_ERROR

    def test_missing_data_groups_rejects(self, emrtd_fixture):
        svc = EmrtdPassiveAuthService(csca_certificates=[emrtd_fixture["csca_cert"]])
        result = svc.verify(sod_der=emrtd_fixture["sod_der"], data_groups={})
        assert result.is_authentic is False
        assert result.reason_code == ReasonCode.MISSING_DG

    def test_dg_not_covered_by_sod_rejects(self, emrtd_fixture):
        # Client presents a DG the SOD never signed (DG7). Must reject, not
        # silently accept the DGs that DO match.
        svc = EmrtdPassiveAuthService(csca_certificates=[emrtd_fixture["csca_cert"]])
        dgs = dict(emrtd_fixture["data_groups"])
        dgs[7] = b"\x67\x05EXTRA"
        result = svc.verify(sod_der=emrtd_fixture["sod_der"], data_groups=dgs)
        assert result.is_authentic is False
        assert result.reason_code == ReasonCode.DG_HASH_MISMATCH
        assert result.dg_hash_results["7"] is False

    def test_ecdsa_document_signer_happy_path(self):
        # eMRTD DS keys are often ECDSA (P-256). Prove the EC verification path.
        csca_key = ec.generate_private_key(ec.SECP256R1())
        ds_key = ec.generate_private_key(ec.SECP256R1())
        csca_cert = _make_cert(
            "EC CSCA", "EC CSCA", csca_key, csca_key.public_key(), True
        )
        ds_cert = _make_cert(
            "EC Document Signer", "EC CSCA", csca_key, ds_key.public_key(), False
        )
        data_groups = {1: b"\x61\x08EC-DG1!!"}
        lds_der = _build_lds(data_groups)
        sod_der = _build_sod(lds_der, ds_cert, ds_key)

        svc = EmrtdPassiveAuthService(csca_certificates=[csca_cert])
        result = svc.verify(sod_der=sod_der, data_groups=data_groups)
        assert result.is_authentic is True
        assert result.reason_code == ReasonCode.OK

    def test_expired_document_signer_rejects(self):
        """BIO-M2: an EXPIRED DS cert must NOT yield is_authentic=true.

        The SOD signature still verifies cryptographically (the key is fine),
        but the Document Signer cert is past its not_after, so passive auth must
        fail-closed with DS_CERT_EXPIRED rather than trusting the document.
        """
        csca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        ds_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        csca_cert = _make_cert(
            "Expiry CSCA", "Expiry CSCA", csca_key, csca_key.public_key(), True
        )
        # DS cert that expired in the past (valid 2010-01-01 .. 2012-01-01).
        ds_cert = _make_cert(
            "Expired Document Signer",
            "Expiry CSCA",
            csca_key,
            ds_key.public_key(),
            False,
            not_before=datetime.datetime(2010, 1, 1),
            not_after=datetime.datetime(2012, 1, 1),
        )
        data_groups = {1: b"\x61\x08DG1-EXP!"}
        lds_der = _build_lds(data_groups)
        sod_der = _build_sod(lds_der, ds_cert, ds_key)

        svc = EmrtdPassiveAuthService(csca_certificates=[csca_cert])
        result = svc.verify(sod_der=sod_der, data_groups=data_groups)
        assert result.is_authentic is False
        assert result.reason_code == ReasonCode.DS_CERT_EXPIRED
        # DG integrity + signature were fine; only the validity window failed.
        assert result.dg_hash_results == {"1": True}

    def test_not_yet_valid_document_signer_rejects(self):
        """A DS cert whose not_before is in the FUTURE is also rejected."""
        csca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        ds_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        csca_cert = _make_cert(
            "Future CSCA", "Future CSCA", csca_key, csca_key.public_key(), True
        )
        ds_cert = _make_cert(
            "Future Document Signer",
            "Future CSCA",
            csca_key,
            ds_key.public_key(),
            False,
            not_before=datetime.datetime(2099, 1, 1),
            not_after=datetime.datetime(2100, 1, 1),
        )
        data_groups = {1: b"\x61\x08DG1-FUT!"}
        lds_der = _build_lds(data_groups)
        sod_der = _build_sod(lds_der, ds_cert, ds_key)

        svc = EmrtdPassiveAuthService(csca_certificates=[csca_cert])
        result = svc.verify(sod_der=sod_der, data_groups=data_groups)
        assert result.is_authentic is False
        assert result.reason_code == ReasonCode.DS_CERT_EXPIRED

    def test_expired_csca_root_rejects(self):
        """An in-validity DS that chains to an EXPIRED CSCA root is rejected.

        The DS is current and its signature verifies, but the trusted anchor it
        chains to is itself past its validity window, so it can no longer vouch
        for the signer → CSCA_CERT_EXPIRED (fail-closed).
        """
        csca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        ds_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        # Expired CSCA root (valid 2000-01-01 .. 2005-01-01).
        csca_cert = _make_cert(
            "Old CSCA",
            "Old CSCA",
            csca_key,
            csca_key.public_key(),
            True,
            not_before=datetime.datetime(2000, 1, 1),
            not_after=datetime.datetime(2005, 1, 1),
        )
        # Current DS cert (defaults to 2020 .. 2035).
        ds_cert = _make_cert(
            "Current Document Signer",
            "Old CSCA",
            csca_key,
            ds_key.public_key(),
            False,
        )
        data_groups = {1: b"\x61\x08DG1-CSC!"}
        lds_der = _build_lds(data_groups)
        sod_der = _build_sod(lds_der, ds_cert, ds_key)

        svc = EmrtdPassiveAuthService(csca_certificates=[csca_cert])
        result = svc.verify(sod_der=sod_der, data_groups=data_groups)
        assert result.is_authentic is False
        assert result.reason_code == ReasonCode.CSCA_CERT_EXPIRED
