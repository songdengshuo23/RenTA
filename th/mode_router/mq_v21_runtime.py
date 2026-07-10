from __future__ import annotations

import os
import ssl
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


def truthy(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off", "disabled"}
    return bool(value)


def _pick(payload: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in payload and payload.get(key) is not None:
            return payload.get(key)
    return default


def create_client_ssl_context(
    *,
    cert_file: str,
    key_file: str,
    ca_file: str,
    check_hostname: bool = False,
) -> ssl.SSLContext:
    for label, value in (
        ("client certificate", cert_file),
        ("client key", key_file),
        ("CA certificate", ca_file),
    ):
        if not value or not Path(value).is_file():
            raise FileNotFoundError(f"MQ Inbox {label} is missing: {value or '<unset>'}")
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=ca_file)
    context.load_cert_chain(certfile=cert_file, keyfile=key_file)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.check_hostname = check_hostname
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def partner_tls_paths(cert_dir: str, aic: str) -> tuple[str, str]:
    directory = Path(cert_dir)
    return str(directory / f"{aic}.pem"), str(directory / f"{aic}.key")


@dataclass(frozen=True)
class MQV21Settings:
    enabled: bool = False
    fallback_enabled: bool = True
    leader_aic: str = "1.2.156.3088.1.1.34C2.478BDF.3GF546.0JU4"
    host: str = "127.0.0.1"
    port: int = 5671
    vhost: str = "acps"
    auth_service_url: str = "https://127.0.0.1:9007"
    cert_file: str = ""
    key_file: str = ""
    ca_file: str = ""
    check_hostname: bool = False
    invitation_timeout_seconds: int = 30

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any] | None = None) -> "MQV21Settings":
        payload = payload or {}
        raw = _pick(payload, "mq_inbox", "mqInbox", default={}) or {}
        config = raw if isinstance(raw, Mapping) else {}
        enabled = truthy(
            _pick(
                config,
                "enabled",
                default=_pick(
                    payload,
                    "mq_inbox_enabled",
                    "mqInboxEnabled",
                    default=os.getenv("ACPS_MQ_INBOX_ENABLED"),
                ),
            ),
            False,
        )
        fallback_enabled = truthy(
            _pick(
                config,
                "fallback_enabled",
                "fallbackEnabled",
                default=_pick(
                    payload,
                    "mq_legacy_fallback_enabled",
                    "mqLegacyFallbackEnabled",
                    default=os.getenv("ACPS_MQ_LEGACY_FALLBACK_ENABLED"),
                ),
            ),
            True,
        )
        return cls(
            enabled=enabled,
            fallback_enabled=fallback_enabled,
            leader_aic=str(
                _pick(config, "leader_aic", "leaderAic", default=os.getenv("ACPS_MQ_LEADER_AIC", cls.leader_aic))
            ),
            host=str(_pick(config, "host", default=os.getenv("ACPS_MQ_HOST", cls.host))),
            port=int(_pick(config, "port", default=os.getenv("ACPS_MQ_PORT", cls.port))),
            vhost=str(_pick(config, "vhost", default=os.getenv("ACPS_MQ_VHOST", cls.vhost))),
            auth_service_url=str(
                _pick(
                    config,
                    "auth_service_url",
                    "authServiceUrl",
                    default=os.getenv("ACPS_MQ_AUTH_URL", cls.auth_service_url),
                )
            ).rstrip("/"),
            cert_file=str(
                _pick(config, "cert_file", "certFile", default=os.getenv("ACPS_MQ_TLS_CERT_FILE", ""))
            ),
            key_file=str(
                _pick(config, "key_file", "keyFile", default=os.getenv("ACPS_MQ_TLS_KEY_FILE", ""))
            ),
            ca_file=str(
                _pick(config, "ca_file", "caFile", default=os.getenv("ACPS_MQ_TLS_CA_FILE", ""))
            ),
            check_hostname=truthy(
                _pick(
                    config,
                    "check_hostname",
                    "checkHostname",
                    default=os.getenv("ACPS_MQ_TLS_CHECK_HOSTNAME"),
                ),
                False,
            ),
            invitation_timeout_seconds=int(
                _pick(
                    config,
                    "invitation_timeout_seconds",
                    "invitationTimeoutSeconds",
                    default=os.getenv("ACPS_MQ_INVITATION_TIMEOUT_SECONDS", cls.invitation_timeout_seconds),
                )
            ),
        )

    def validate(self) -> None:
        if not self.enabled:
            return
        if self.port != 5671:
            raise ValueError("ACPs v2.1 MQ Inbox requires AMQPS port 5671")
        if self.vhost != "acps":
            raise ValueError("ACPs v2.1 MQ Inbox requires the shared 'acps' vhost")
        if not self.auth_service_url.startswith("https://"):
            raise ValueError("ACPs v2.1 MQ Auth Group API must use HTTPS")
        if not self.leader_aic:
            raise ValueError("ACPs v2.1 MQ Inbox requires a Leader AIC")
        for label, value in (
            ("client certificate", self.cert_file),
            ("client key", self.key_file),
            ("CA certificate", self.ca_file),
        ):
            if not value or not Path(value).is_file():
                raise FileNotFoundError(f"MQ Inbox {label} is missing: {value or '<unset>'}")

    def create_ssl_context(self) -> ssl.SSLContext:
        self.validate()
        return create_client_ssl_context(
            cert_file=self.cert_file,
            key_file=self.key_file,
            ca_file=self.ca_file,
            check_hostname=self.check_hostname,
        )

    def rabbitmq_config(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "vhost": self.vhost,
            "user": None,
            "password": None,
            "auth_service_url": self.auth_service_url,
        }
