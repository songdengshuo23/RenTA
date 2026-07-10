import base64
import copy
import hashlib
import hmac
import ipaddress
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from sqlmodel import select

from app.acme.agent_registry import AgentInfo, AgentRegistryClient
from app.acme.eab_verifier import verify_eab_binding
from app.acme.exception import AcmeException
from app.acme.models import (
    AcmeAccount,
    AcmeAuthorization,
    AcmeCertificate,
    AcmeChallenge,
    AcmeNonce,
    AcmeOrder,
    AuthorizationStatus,
    OrderStatus,
)
from app.core.config import settings


AIC = "2001010000000000000000000000000000000000000000000000000000000000"
ACME_BASE_URL = "http://testserver/acps-atr-v2/acme"
NEW_ACCOUNT_URL = f"{ACME_BASE_URL}/new-account"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _json_b64(value: dict) -> str:
    return _b64url(
        json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )


def _account_key_and_jwk():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private_key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "n": _b64url(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
        "e": _b64url(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big")),
    }
    return private_key, jwk


def _signed_jws(private_key, protected: dict, payload: dict) -> dict:
    protected_b64 = _json_b64(protected)
    payload_b64 = _json_b64(payload)
    signing_input = f"{protected_b64}.{payload_b64}".encode("ascii")
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return {
        "protected": protected_b64,
        "payload": payload_b64,
        "signature": _b64url(signature),
    }


def _eab_jws(jwk: dict, key_id: str, mac_key: bytes, url=NEW_ACCOUNT_URL) -> dict:
    protected = _json_b64({"alg": "HS256", "kid": key_id, "url": url})
    payload = _json_b64(jwk)
    signature = hmac.new(
        mac_key, f"{protected}.{payload}".encode("ascii"), hashlib.sha256
    ).digest()
    return {
        "protected": protected,
        "payload": payload,
        "signature": _b64url(signature),
    }


class OneTimeCredentialProvider:
    def __init__(self, credentials=None):
        self.credentials = dict(credentials or {})
        self.calls = []

    async def consume_eab_credential(self, key_id: str):
        self.calls.append(key_id)
        return self.credentials.pop(key_id, None)


class FakeRegistry(OneTimeCredentialProvider):
    def __init__(self, credentials=None):
        super().__init__(credentials)
        self.validation_calls = []
        self.registered = []
        self.issued = []

    async def validate_aic_and_get_info(self, aic, require_challenge=True):
        self.validation_calls.append((aic, require_challenge))
        if aic != AIC:
            return None
        return AgentInfo(
            {
                "aic": AIC,
                "active": True,
                "protocolVersion": "02.01",
                "name": "Stage 3 Agent",
                "version": "1.0.0",
                "provider": {
                    "organization": "RenTA",
                    "department": "Platform",
                    "countryCode": "CN",
                },
                "securitySchemes": {
                    "mtls": {
                        "type": "mutualTLS",
                        "x-caChallengeBaseUrl": "https://agent.example/challenge",
                    }
                },
                "certificate": {
                    "altNames": {
                        "dns": ["agent.example"],
                        "ip": ["127.0.0.1"],
                    },
                    "requestedValidity": 30,
                },
            }
        )

    async def verify_agent_ownership(self, _aic, _account_info):
        return True

    async def register_certificate_request(self, aic, order_id):
        self.registered.append((aic, order_id))
        return True

    async def notify_certificate_issued(self, aic, order_id, cert_id):
        self.issued.append((aic, order_id, cert_id))
        return True


@pytest.fixture(autouse=True)
def clean_acme_rows(db_session):
    models = [
        AcmeCertificate,
        AcmeChallenge,
        AcmeAuthorization,
        AcmeOrder,
        AcmeAccount,
        AcmeNonce,
    ]
    for model in models:
        for row in db_session.exec(select(model)).all():
            db_session.delete(row)
    db_session.commit()
    yield
    for model in models:
        for row in db_session.exec(select(model)).all():
            db_session.delete(row)
    db_session.commit()


@pytest.fixture
def ca_feature_flags():
    old_values = (
        settings.acps_ca_eab_enabled,
        settings.acps_challenge_legacy_enabled,
        settings.acme_directory_url,
    )
    settings.acps_ca_eab_enabled = True
    settings.acps_challenge_legacy_enabled = True
    settings.acme_directory_url = ACME_BASE_URL
    yield
    (
        settings.acps_ca_eab_enabled,
        settings.acps_challenge_legacy_enabled,
        settings.acme_directory_url,
    ) = old_values


@pytest.mark.asyncio
async def test_verify_eab_binding_success():
    _, jwk = _account_key_and_jwk()
    mac_key = b"stage3-eab-test-key-32-bytes!!"
    provider = OneTimeCredentialProvider(
        {"kid-1": (_b64url(mac_key), AIC.lower())}
    )

    result = await verify_eab_binding(
        _eab_jws(jwk, "kid-1", mac_key), jwk, NEW_ACCOUNT_URL, provider
    )

    assert result == AIC
    assert provider.calls == ["kid-1"]


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_field", ["protected", "payload", "signature"])
async def test_verify_eab_binding_rejects_missing_jws_fields(missing_field):
    _, jwk = _account_key_and_jwk()
    eab = _eab_jws(jwk, "kid-1", b"test-key")
    del eab[missing_field]

    with pytest.raises(AcmeException):
        await verify_eab_binding(
            eab, jwk, NEW_ACCOUNT_URL, OneTimeCredentialProvider()
        )


@pytest.mark.asyncio
async def test_verify_eab_binding_rejects_alg_url_kid_and_jwk():
    _, jwk = _account_key_and_jwk()
    _, other_jwk = _account_key_and_jwk()
    mac_key = b"test-key"

    invalid_values = []
    for protected_value in (
        {"alg": "HS512", "kid": "kid-1", "url": NEW_ACCOUNT_URL},
        {"alg": "HS256", "kid": "kid-1", "url": "https://wrong.invalid"},
        {"alg": "HS256", "kid": "", "url": NEW_ACCOUNT_URL},
    ):
        eab = _eab_jws(jwk, "kid-1", mac_key)
        eab["protected"] = _json_b64(protected_value)
        invalid_values.append(eab)
    invalid_values.append(_eab_jws(other_jwk, "kid-1", mac_key))

    for eab in invalid_values:
        with pytest.raises(AcmeException):
            await verify_eab_binding(
                eab, jwk, NEW_ACCOUNT_URL, OneTimeCredentialProvider()
            )


@pytest.mark.asyncio
async def test_verify_eab_binding_rejects_bad_hmac_and_replay():
    _, jwk = _account_key_and_jwk()
    mac_key = b"correct-key"
    provider = OneTimeCredentialProvider({"kid-1": (_b64url(mac_key), AIC)})
    eab = _eab_jws(jwk, "kid-1", b"wrong-key")

    with pytest.raises(AcmeException):
        await verify_eab_binding(eab, jwk, NEW_ACCOUNT_URL, provider)
    with pytest.raises(AcmeException):
        await verify_eab_binding(eab, jwk, NEW_ACCOUNT_URL, provider)

    assert provider.calls == ["kid-1", "kid-1"]


@pytest.mark.asyncio
async def test_verify_eab_binding_fails_closed_when_registry_is_unavailable():
    _, jwk = _account_key_and_jwk()
    with pytest.raises(AcmeException):
        await verify_eab_binding(
            _eab_jws(jwk, "missing", b"test-key"),
            jwk,
            NEW_ACCOUNT_URL,
            OneTimeCredentialProvider(),
        )


@pytest.mark.asyncio
async def test_eab_acs_lookup_bypasses_legacy_registry_mock():
    client = AgentRegistryClient()
    client.is_mock_enabled = True
    response = httpx.Response(
        200,
        request=httpx.Request("GET", "http://registry/acps-atr-v2/acs/test"),
        json={
            "aic": AIC,
            "active": True,
            "protocolVersion": "02.01",
            "provider": {"organization": "RenTA", "countryCode": "CN"},
            "certificate": {},
        },
    )

    with patch.object(
        client,
        "_make_request_with_retry",
        new=AsyncMock(return_value=response),
    ) as request_mock:
        result = await client.validate_aic_and_get_info(
            AIC, require_challenge=False
        )

    assert result is not None
    assert result.aic == AIC
    request_mock.assert_awaited_once()


def _nonce(client):
    return client.get(f"{ACME_BASE_URL}/new-nonce").headers["Replay-Nonce"]


def _new_account_request(client, private_key, jwk, eab=None):
    payload = {"termsOfServiceAgreed": True, "contact": ["mailto:test@renta"]}
    if eab is not None:
        payload["externalAccountBinding"] = eab
    return _signed_jws(
        private_key,
        {
            "alg": "RS256",
            "nonce": _nonce(client),
            "url": NEW_ACCOUNT_URL,
            "jwk": jwk,
        },
        payload,
    )


def _account_post(client, private_key, account_url, path, payload):
    url = f"{ACME_BASE_URL}/{path}"
    request_data = _signed_jws(
        private_key,
        {
            "alg": "RS256",
            "nonce": _nonce(client),
            "url": url,
            "kid": account_url,
        },
        payload,
    )
    return client.post(url, json=request_data)


def _v21_csr() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return (
        x509.CertificateSigningRequestBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, AIC)]))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.UniformResourceIdentifier(f"acps://{AIC}"),
                    x509.DNSName("agent.example"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
        .public_bytes(serialization.Encoding.DER)
    )


def test_new_account_requires_eab_when_enabled(client, ca_feature_flags):
    private_key, jwk = _account_key_and_jwk()
    with patch("app.acme.api.get_agent_registry_client", return_value=FakeRegistry()):
        response = client.post(
            NEW_ACCOUNT_URL,
            json=_new_account_request(client, private_key, jwk),
        )

    assert response.status_code == 400
    assert "EXTERNAL_ACCOUNT_REQUIRED" in response.text


def test_eab_account_order_finalize_and_certificate(
    client, db_session, ca_feature_flags
):
    private_key, jwk = _account_key_and_jwk()
    mac_key = b"stage3-integration-eab-key"
    registry = FakeRegistry({"integration-kid": (_b64url(mac_key), AIC)})
    eab = _eab_jws(jwk, "integration-kid", mac_key)

    with patch("app.acme.api.get_agent_registry_client", return_value=registry):
        account_response = client.post(
            NEW_ACCOUNT_URL,
            json=_new_account_request(client, private_key, jwk, eab),
        )
        assert account_response.status_code == 201
        account_url = account_response.headers["Location"]

        account = db_session.exec(select(AcmeAccount)).one()
        assert account.aic == AIC

        order_response = _account_post(
            client,
            private_key,
            account_url,
            "new-order",
            {"identifiers": [{"type": "agent", "value": AIC.lower()}]},
        )
        assert order_response.status_code == 201
        assert order_response.json()["status"] == OrderStatus.READY

        order = db_session.exec(select(AcmeOrder)).one()
        authorization = db_session.exec(select(AcmeAuthorization)).one()
        assert order.status == OrderStatus.READY
        assert authorization.status == AuthorizationStatus.VALID
        assert db_session.exec(select(AcmeChallenge)).all() == []

        finalize_response = _account_post(
            client,
            private_key,
            account_url,
            f"order/{order.order_id}/finalize",
            {"csr": _b64url(_v21_csr())},
        )
        assert finalize_response.status_code == 200
        assert finalize_response.json()["status"] == OrderStatus.VALID

        certificate = db_session.exec(select(AcmeCertificate)).one()
        parsed = x509.load_pem_x509_certificate(certificate.certificate_pem.encode())
        assert parsed.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == AIC
        san = parsed.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value
        assert f"acps://{AIC}" in san.get_values_for_type(
            x509.UniformResourceIdentifier
        )
        assert san.get_values_for_type(x509.DNSName) == ["agent.example"]
        assert san.get_values_for_type(x509.IPAddress) == [
            ipaddress.ip_address("127.0.0.1")
        ]
        validity = parsed.not_valid_after_utc - parsed.not_valid_before_utc
        assert timedelta(days=29) < validity <= timedelta(days=30)

    assert all(require_challenge is False for _, require_challenge in registry.validation_calls)
    assert registry.registered
    assert registry.issued


def test_eab_account_rejects_order_for_other_aic(client, ca_feature_flags):
    private_key, jwk = _account_key_and_jwk()
    mac_key = b"stage3-mismatch-key"
    registry = FakeRegistry({"mismatch-kid": (_b64url(mac_key), AIC)})

    with patch("app.acme.api.get_agent_registry_client", return_value=registry):
        account_response = client.post(
            NEW_ACCOUNT_URL,
            json=_new_account_request(
                client,
                private_key,
                jwk,
                _eab_jws(jwk, "mismatch-kid", mac_key),
            ),
        )
        response = _account_post(
            client,
            private_key,
            account_response.headers["Location"],
            "new-order",
            {"identifiers": [{"type": "agent", "value": "2011" + AIC[4:]}]},
        )

    assert response.status_code == 400
    assert "INVALID_IDENTIFIER" in response.text


def test_feature_off_keeps_legacy_http01_order(client, db_session):
    old_values = (
        settings.acps_ca_eab_enabled,
        settings.acps_challenge_legacy_enabled,
        settings.acme_directory_url,
    )
    settings.acps_ca_eab_enabled = False
    settings.acps_challenge_legacy_enabled = True
    settings.acme_directory_url = ACME_BASE_URL
    private_key, jwk = _account_key_and_jwk()
    registry = FakeRegistry()
    validator = SimpleNamespace(
        pre_validate_agent_endpoint=lambda _agent: None,
    )

    async def pre_validate(_agent):
        return SimpleNamespace(success=True, error=None)

    validator.pre_validate_agent_endpoint = pre_validate
    try:
        with (
            patch("app.acme.api.get_agent_registry_client", return_value=registry),
            patch("app.acme.api.get_http01_validation_service", return_value=validator),
        ):
            account_response = client.post(
                NEW_ACCOUNT_URL,
                json=_new_account_request(client, private_key, jwk),
            )
            assert account_response.status_code == 201
            account = db_session.exec(select(AcmeAccount)).one()
            assert account.aic is None

            order_response = _account_post(
                client,
                private_key,
                account_response.headers["Location"],
                "new-order",
                {"identifiers": [{"type": "agent", "value": AIC}]},
            )
            assert order_response.status_code == 201
            assert order_response.json()["status"] == OrderStatus.PENDING
            assert len(db_session.exec(select(AcmeChallenge)).all()) == 1
    finally:
        (
            settings.acps_ca_eab_enabled,
            settings.acps_challenge_legacy_enabled,
            settings.acme_directory_url,
        ) = old_values
