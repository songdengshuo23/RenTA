"""External Account Binding verification for ACPs v2.1 ACME accounts."""

import hashlib
import hmac
from typing import Any, Protocol

from .exception import AcmeError, AcmeException
from .jws_verifier import get_jws_verifier
from .services import JWKService


class EabCredentialProvider(Protocol):
    async def consume_eab_credential(self, key_id: str) -> tuple[str, str] | None:
        """Consume a one-time EAB credential and return ``(mac_key, aic)``."""
        ...


def _compose_jws_string(eab_jws: dict[str, Any]) -> str:
    values = []
    for field in ("protected", "payload", "signature"):
        value = eab_jws.get(field)
        if not isinstance(value, str) or not value:
            raise AcmeException(
                status_code=400,
                error_name=AcmeError.MALFORMED_REQUEST,
                error_msg=f"Missing or invalid EAB JWS field: {field}",
            )
        values.append(value)
    return ".".join(values)


async def verify_eab_binding(
    eab_jws: dict[str, Any],
    account_jwk: dict[str, Any],
    expected_url: str,
    registry_client: EabCredentialProvider,
) -> str:
    """Verify an EAB JWS and return the Registry-confirmed account AIC."""
    if not isinstance(eab_jws, dict):
        raise AcmeException(
            status_code=400,
            error_name=AcmeError.EXTERNAL_ACCOUNT_REQUIRED,
            error_msg="externalAccountBinding is required for new account",
        )

    verifier = get_jws_verifier()
    jws_string = _compose_jws_string(eab_jws)
    protected, payload, signature_b64 = verifier.parse_jws(jws_string)

    if protected.get("alg") != "HS256":
        raise AcmeException(
            status_code=400,
            error_name=AcmeError.UNSUPPORTED_ALGORITHM,
            error_msg="externalAccountBinding must use HS256",
        )
    if protected.get("url") != expected_url:
        raise AcmeException(
            status_code=400,
            error_name=AcmeError.MALFORMED_REQUEST,
            error_msg="externalAccountBinding URL mismatch",
        )

    key_id = protected.get("kid")
    if not isinstance(key_id, str) or not key_id.strip():
        raise AcmeException(
            status_code=400,
            error_name=AcmeError.MALFORMED_REQUEST,
            error_msg="externalAccountBinding missing kid",
        )

    try:
        payload_thumbprint = JWKService.compute_jwk_thumbprint(payload)
        account_thumbprint = JWKService.compute_jwk_thumbprint(account_jwk)
    except (KeyError, TypeError) as exc:
        raise AcmeException(
            status_code=400,
            error_name=AcmeError.MALFORMED_REQUEST,
            error_msg="externalAccountBinding payload is not a valid account JWK",
        ) from exc
    if payload_thumbprint != account_thumbprint:
        raise AcmeException(
            status_code=400,
            error_name=AcmeError.MALFORMED_REQUEST,
            error_msg="externalAccountBinding payload does not match account jwk",
        )

    consume_result = await registry_client.consume_eab_credential(key_id.strip())
    if not consume_result:
        raise AcmeException(
            status_code=400,
            error_name=AcmeError.EXTERNAL_ACCOUNT_REQUIRED,
            error_msg="Failed to consume external account binding credential",
        )

    mac_key, aic = consume_result
    if not isinstance(aic, str) or not aic.strip():
        raise AcmeException(
            status_code=400,
            error_name=AcmeError.EXTERNAL_ACCOUNT_REQUIRED,
            error_msg="Registry returned an invalid EAB binding",
        )

    mac_key_bytes = verifier.base64url_decode(mac_key)
    signing_input = f"{eab_jws['protected']}.{eab_jws['payload']}".encode("ascii")
    expected_signature = hmac.new(
        mac_key_bytes,
        signing_input,
        hashlib.sha256,
    ).digest()
    actual_signature = verifier.base64url_decode(signature_b64)
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise AcmeException(
            status_code=400,
            error_name=AcmeError.BAD_SIGNATURE,
            error_msg="Invalid externalAccountBinding signature",
        )

    return aic.strip().upper()
