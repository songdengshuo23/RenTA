import base64
import json
import secrets
import uuid
from datetime import timedelta

from fastapi import status
from sqlalchemy.orm import Session

from app.agent.model import Agent, ApprovalStatus
from app.core.config import settings
from app.core.crypto import sm4_decrypt, sm4_encrypt
from app.eab.exception import EabErrorCode, EabException
from app.eab.model import EabCredential
from app.eab.schema import EabConsumeResponse, EabCredentialResponse
from app.utils.aic import validate_aic_v0201
from app.utils.utils import get_beijing_time


def _require_eab_enabled() -> None:
    if not settings.ACPS_EAB_ISSUANCE_ENABLED:
        raise EabException(
            EabErrorCode.EAB_DISABLED,
            "EAB issuance is disabled",
            status_code=status.HTTP_409_CONFLICT,
        )


def _require_eab_configuration() -> str:
    key = settings.SM4_ENCRYPTION_KEY.strip()
    normalized = key.removeprefix("0x").removeprefix("0X")
    try:
        valid_key = len(normalized) == 32 and len(bytes.fromhex(normalized)) == 16
    except ValueError:
        valid_key = False
    if not valid_key or settings.EAB_CREDENTIAL_EXPIRE_HOURS <= 0:
        raise EabException(
            EabErrorCode.EAB_NOT_CONFIGURED,
            "EAB encryption key or expiry is not configured",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return key


def _generate_key_id() -> str:
    return uuid.uuid4().hex


def _generate_mac_key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


def _get_agent_by_aic(db: Session, agent_aic: str) -> Agent | None:
    return db.query(Agent).filter(Agent.aic == agent_aic).first()


def _get_credential_for_update(db: Session, key_id: str) -> EabCredential | None:
    return (
        db.query(EabCredential)
        .filter(EabCredential.key_id == key_id)
        .with_for_update()
        .first()
    )


def _acs_protocol_version(agent: Agent) -> str | None:
    acs = agent.acs
    if isinstance(acs, str):
        try:
            acs = json.loads(acs)
        except json.JSONDecodeError:
            return None
    return acs.get("protocolVersion") if isinstance(acs, dict) else None


def generate_eab_credential(
    db: Session, user_id: uuid.UUID, agent_aic: str
) -> EabCredentialResponse:
    _require_eab_enabled()
    encryption_key = _require_eab_configuration()
    normalized_aic = agent_aic.strip().upper()
    agent = _get_agent_by_aic(db, normalized_aic)

    if agent is None or agent.created_by_id != user_id:
        raise EabException(
            EabErrorCode.AIC_NOT_OWNED,
            "Agent AIC is not owned by the current user",
            status_code=status.HTTP_403_FORBIDDEN,
            input_params={"agent_aic": normalized_aic, "user_id": str(user_id)},
        )
    if not agent.is_active or agent.is_deleted or agent.is_disabled:
        raise EabException(
            EabErrorCode.AIC_INACTIVE,
            "Agent AIC is inactive",
            status_code=status.HTTP_403_FORBIDDEN,
            input_params={"agent_aic": normalized_aic},
        )
    if agent.approval_status != ApprovalStatus.APPROVED:
        raise EabException(
            EabErrorCode.AIC_NOT_APPROVED,
            "Agent AIC is not approved",
            status_code=status.HTTP_403_FORBIDDEN,
            input_params={"agent_aic": normalized_aic},
        )
    if not validate_aic_v0201(normalized_aic) or _acs_protocol_version(agent) != "02.01":
        raise EabException(
            EabErrorCode.AIC_PROTOCOL_UNSUPPORTED,
            "EAB is available only for ACPs v2.1 Agent AICs",
            status_code=status.HTTP_409_CONFLICT,
            input_params={"agent_aic": normalized_aic},
        )

    key_id = _generate_key_id()
    mac_key = _generate_mac_key()
    expires_at = get_beijing_time() + timedelta(
        hours=settings.EAB_CREDENTIAL_EXPIRE_HOURS
    )
    credential = EabCredential(
        key_id=key_id,
        mac_key_encrypted=sm4_encrypt(mac_key, encryption_key),
        aic=normalized_aic,
        user_id=user_id,
        expires_at=expires_at,
    )
    try:
        db.add(credential)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return EabCredentialResponse(
        key_id=key_id,
        mac_key=mac_key,
        aic=normalized_aic,
        expires_at=expires_at,
    )


def consume_eab_credential(db: Session, key_id: str) -> EabConsumeResponse:
    _require_eab_enabled()
    encryption_key = _require_eab_configuration()
    normalized_key_id = key_id.strip()

    try:
        credential = _get_credential_for_update(db, normalized_key_id)
        if credential is None:
            raise EabException(
                EabErrorCode.EAB_NOT_FOUND,
                "EAB credential not found",
                status_code=status.HTTP_404_NOT_FOUND,
                input_params={"key_id": normalized_key_id},
            )
        if credential.is_consumed:
            raise EabException(
                EabErrorCode.EAB_ALREADY_CONSUMED,
                "EAB credential has already been consumed",
                input_params={"key_id": normalized_key_id},
            )
        if credential.expires_at <= get_beijing_time():
            raise EabException(
                EabErrorCode.EAB_EXPIRED,
                "EAB credential has expired",
                input_params={"key_id": normalized_key_id},
            )

        mac_key = sm4_decrypt(credential.mac_key_encrypted, encryption_key)
        credential.is_consumed = True
        credential.consumed_at = get_beijing_time()
        db.add(credential)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return EabConsumeResponse(mac_key=mac_key, aic=credential.aic)
