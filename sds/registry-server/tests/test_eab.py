import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.agent.model import ApprovalStatus
from app.core.base_exception import BaseException
from app.core.config import settings
from app.core.crypto import sm4_decrypt, sm4_encrypt
from app.core.db_session import get_db
from app.eab import api as eab_api
from app.eab import service as eab_service
from app.eab.exception import EabErrorCode, EabException
from app.eab.model import EabCredential
from app.eab.schema import EabConsumeResponse, EabCredentialResponse
from app.utils import aic
from app.utils.utils import get_beijing_time

TEST_SM4_KEY = "0123456789abcdeffedcba9876543210"


class DummySession:
    def __init__(self):
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


@pytest.fixture(autouse=True)
def _eab_settings(monkeypatch):
    monkeypatch.setattr(settings, "ACPS_EAB_ISSUANCE_ENABLED", True)
    monkeypatch.setattr(settings, "SM4_ENCRYPTION_KEY", TEST_SM4_KEY)
    monkeypatch.setattr(settings, "EAB_CREDENTIAL_EXPIRE_HOURS", 24)
    monkeypatch.setattr(settings, "REGISTRY_SERVICE_TOKEN", "test-registry-token")


def _v21_agent(owner_id=None, **overrides):
    data = {
        "created_by_id": owner_id or uuid.uuid4(),
        "is_active": True,
        "is_deleted": False,
        "is_disabled": False,
        "approval_status": ApprovalStatus.APPROVED,
        "acs": {"protocolVersion": "02.01"},
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_sm4_encrypt_round_trip_and_rejects_invalid_key():
    encrypted = sm4_encrypt("test-mac-key", TEST_SM4_KEY)
    assert encrypted != "test-mac-key"
    assert sm4_decrypt(encrypted, TEST_SM4_KEY) == "test-mac-key"
    with pytest.raises(ValueError):
        sm4_encrypt("test", "not-a-key")


def test_generate_eab_is_disabled_by_default_switch(monkeypatch):
    monkeypatch.setattr(settings, "ACPS_EAB_ISSUANCE_ENABLED", False)
    with pytest.raises(EabException) as exc_info:
        eab_service.generate_eab_credential(DummySession(), uuid.uuid4(), "AIC")
    assert exc_info.value.error_name == EabErrorCode.EAB_DISABLED.value


def test_generate_eab_encrypts_mac_key_and_commits():
    owner_id = uuid.uuid4()
    agent_aic = aic.generate_aic(spec_version=aic.AIC_SPEC_V0201)
    db = DummySession()
    with patch.object(eab_service, "_get_agent_by_aic", return_value=_v21_agent(owner_id)):
        response = eab_service.generate_eab_credential(db, owner_id, agent_aic)

    credential = db.added[0]
    assert db.commits == 1
    assert credential.mac_key_encrypted != response.mac_key
    assert sm4_decrypt(credential.mac_key_encrypted, TEST_SM4_KEY) == response.mac_key
    assert credential.aic == agent_aic
    assert response.expires_at > get_beijing_time()


@pytest.mark.parametrize(
    ("agent", "requester", "expected"),
    [
        (None, uuid.uuid4(), EabErrorCode.AIC_NOT_OWNED),
        (_v21_agent(), uuid.uuid4(), EabErrorCode.AIC_NOT_OWNED),
        (_v21_agent(is_active=False), None, EabErrorCode.AIC_INACTIVE),
        (
            _v21_agent(approval_status=ApprovalStatus.PENDING),
            None,
            EabErrorCode.AIC_NOT_APPROVED,
        ),
        (
            _v21_agent(acs={"protocolVersion": "02.00"}),
            None,
            EabErrorCode.AIC_PROTOCOL_UNSUPPORTED,
        ),
    ],
)
def test_generate_eab_enforces_owner_status_and_protocol(agent, requester, expected):
    if agent is not None and requester is None:
        requester = agent.created_by_id
    agent_aic = (
        aic.generate_aic(spec_version=aic.AIC_SPEC_V0201)
        if expected != EabErrorCode.AIC_PROTOCOL_UNSUPPORTED
        else aic.generate_aic(spec_version=aic.AIC_SPEC_V0200)
    )
    with (
        patch.object(eab_service, "_get_agent_by_aic", return_value=agent),
        pytest.raises(EabException) as exc_info,
    ):
        eab_service.generate_eab_credential(DummySession(), requester, agent_aic)
    assert exc_info.value.error_name == expected.value


def _credential(**overrides):
    data = {
        "key_id": "key-1",
        "mac_key_encrypted": sm4_encrypt("plain-mac", TEST_SM4_KEY),
        "aic": "AIC-1",
        "user_id": uuid.uuid4(),
        "expires_at": get_beijing_time() + timedelta(hours=1),
        "is_consumed": False,
        "consumed_at": None,
    }
    data.update(overrides)
    return EabCredential(**data)


def test_consume_eab_marks_record_consumed_and_commits():
    db = DummySession()
    credential = _credential()
    with patch.object(eab_service, "_get_credential_for_update", return_value=credential):
        response = eab_service.consume_eab_credential(db, "key-1")
    assert response == EabConsumeResponse(mac_key="plain-mac", aic="AIC-1")
    assert credential.is_consumed is True
    assert credential.consumed_at is not None
    assert db.commits == 1


@pytest.mark.parametrize(
    ("credential", "expected"),
    [
        (None, EabErrorCode.EAB_NOT_FOUND),
        (_credential(is_consumed=True), EabErrorCode.EAB_ALREADY_CONSUMED),
        (
            _credential(expires_at=get_beijing_time() - timedelta(seconds=1)),
            EabErrorCode.EAB_EXPIRED,
        ),
    ],
)
def test_consume_eab_rejects_invalid_lifecycle(credential, expected):
    db = DummySession()
    with (
        patch.object(eab_service, "_get_credential_for_update", return_value=credential),
        pytest.raises(EabException) as exc_info,
    ):
        eab_service.consume_eab_credential(db, "key-1")
    assert exc_info.value.error_name == expected.value
    assert db.rollbacks == 1


def _test_app():
    app = FastAPI()
    app.include_router(eab_api.router_atr, prefix="/acps-atr-v2")
    app.include_router(eab_api.router_internal)
    app.dependency_overrides[get_db] = lambda: DummySession()
    app.dependency_overrides[eab_api.require_client_user] = lambda: SimpleNamespace(
        id=uuid.uuid4()
    )

    @app.exception_handler(BaseException)
    async def _handle_base_exception(request: Request, exc: BaseException):
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    return app


def test_eab_api_uses_aliases_and_internal_service_token(monkeypatch):
    app = _test_app()
    expires_at = get_beijing_time() + timedelta(hours=1)
    monkeypatch.setattr(
        eab_api,
        "generate_eab_credential",
        lambda db, user_id, agent_aic: EabCredentialResponse(
            key_id="kid", mac_key="mac", aic=agent_aic, expires_at=expires_at
        ),
    )
    monkeypatch.setattr(
        eab_api,
        "consume_eab_credential",
        lambda db, key_id: EabConsumeResponse(mac_key="mac", aic="AIC-1"),
    )

    client = TestClient(app)
    issued = client.post("/acps-atr-v2/eab/AIC-1")
    assert issued.status_code == 201
    assert issued.json()["keyId"] == "kid"
    assert issued.json()["macKey"] == "mac"
    assert "expiresAt" in issued.json()

    assert client.post("/internal/eab/consume", json={"keyId": "kid"}).status_code == 401
    assert (
        client.post(
            "/internal/eab/consume",
            headers={"Authorization": "Bearer wrong"},
            json={"keyId": "kid"},
        ).status_code
        == 403
    )
    consumed = client.post(
        "/internal/eab/consume",
        headers={"Authorization": "Bearer test-registry-token"},
        json={"keyId": "kid"},
    )
    assert consumed.status_code == 200
    assert consumed.json() == {"macKey": "mac", "aic": "AIC-1"}
