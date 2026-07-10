import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.agent import api_atr
from app.agent.api_atr import router
from app.agent.exception import AtrException, AtrErrorCode
from app.agent.model import ApprovalStatus
from app.core.acps_exception import AcpsException
from app.core.config import settings
from app.core.db_session import get_db
from app.utils import aic


@pytest.fixture
def atr_app():
    settings.REGISTRY_SERVICE_TOKEN = "test-registry-token"
    app = FastAPI()
    app.include_router(router, prefix="/acps-atr-v2")

    @app.exception_handler(AcpsException)
    async def _handle_acps_exception(request, exc: AcpsException):
        return JSONResponse(
            status_code=exc.http_status, content=exc.to_response_payload()
        )

    # Override DB dependency used by ATR routes
    app.dependency_overrides[get_db] = lambda: None
    return app


@pytest.fixture
def atr_client(atr_app):
    return TestClient(atr_app, headers={"Authorization": "Bearer test-registry-token"})


def test_get_agent_invalid_aic_returns_error_payload(atr_client):
    response = atr_client.get("/acps-atr-v2/acs/invalid")
    assert response.status_code == 400
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == AtrErrorCode.INVALID_REQUEST
    assert body["error"]["message"].startswith("Invalid AIC")


def test_get_agent_not_found(monkeypatch, atr_client):
    valid_aic = aic.generate_aic()

    def _fake_get_agent(db, agent_aic, raise_exception=False):
        return None

    monkeypatch.setattr(api_atr, "get_agent_by_aic", _fake_get_agent)

    response = atr_client.get(f"/acps-atr-v2/acs/{valid_aic}")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == AtrErrorCode.AGENT_NOT_FOUND
    assert body["error"]["data"]["agentAic"] == valid_aic


def test_register_entity_propagates_service_exception(monkeypatch, atr_client):
    ontology_aic = aic.generate_ontology_aic()

    def _fake_register_entity(**kwargs: Dict[str, Any]):
        raise AtrException(
            code=AtrErrorCode.ENDPOINT_CONFLICT,
            message="conflict",
            http_status=409,
            data={"conflictingUrl": "https://dup"},
        )

    monkeypatch.setattr(api_atr, "register_entity", _fake_register_entity)

    payload = {"ontologyAic": ontology_aic, "endPoints": []}
    response = atr_client.post(
        "/acps-atr-v2/entity",
        content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == AtrErrorCode.ENDPOINT_CONFLICT
    assert body["error"]["data"]["conflictingUrl"] == "https://dup"


def test_atr_requires_service_token(atr_app):
    response = TestClient(atr_app).get("/acps-atr-v2/acs/invalid")
    assert response.status_code == 401


def _fake_agent(agent_aic: str):
    return SimpleNamespace(
        id=uuid.uuid4(),
        aic=agent_aic,
        name="Passport Agent",
        version="1.0",
        created_by_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        is_active=True,
        is_deleted=False,
        is_disabled=False,
        approval_status=ApprovalStatus.APPROVED,
    )


def _fake_passport(status: str = "VALID", decision: str = "APPROVE"):
    return SimpleNamespace(
        passport_id="passport_review_1",
        review_id="review_1",
        status=status,
        passport_version="1.0",
        acs_hash="hash-1",
        acs_version=1,
        decision=decision,
        risk_level="LOW",
        permission_tier="T2",
        passport_payload={
            "acp": {"protocolVersion": "1.0", "acsHash": "hash-1"},
            "capabilities": {"taskTypes": ["read"], "domains": ["general"]},
            "permissions": {"tier": "T2"},
            "orchestratorHints": {
                "eligibleForAutoDispatch": decision == "APPROVE",
                "allowedTaskClasses": ["read"],
                "blockedTaskClasses": ["payment"],
            },
        },
        issued_at=datetime(2026, 5, 28, tzinfo=timezone.utc),
        expires_at=None,
        review_after=None,
        updated_at=datetime(2026, 5, 28, tzinfo=timezone.utc),
    )


def test_get_passport_dispatch_invalid_aic_returns_error_payload(atr_client):
    response = atr_client.get("/acps-atr-v2/passports/invalid/dispatch")
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == AtrErrorCode.INVALID_REQUEST


def test_get_passport_dispatch_not_found(monkeypatch, atr_client):
    valid_aic = aic.generate_aic()

    def _fake_get_latest_passport(db, agent_aic):
        return _fake_agent(agent_aic), None

    monkeypatch.setattr(
        api_atr, "get_latest_agent_passport_by_aic", _fake_get_latest_passport
    )

    response = atr_client.get(f"/acps-atr-v2/passports/{valid_aic}/dispatch")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == AtrErrorCode.AGENT_PASSPORT_NOT_FOUND
    assert body["error"]["data"]["agentAic"] == valid_aic


def test_get_passport_dispatch_returns_eligible_view(monkeypatch, atr_client):
    valid_aic = aic.generate_aic()
    agent = _fake_agent(valid_aic)
    passport = _fake_passport()

    def _fake_get_latest_passport(db, agent_aic):
        return agent, passport

    monkeypatch.setattr(
        api_atr, "get_latest_agent_passport_by_aic", _fake_get_latest_passport
    )

    response = atr_client.get(f"/acps-atr-v2/passports/{valid_aic}/dispatch")
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["agentAic"] == valid_aic
    assert result["passportId"] == "passport_review_1"
    assert result["status"] == "VALID"
    assert result["eligibleForDispatch"] is False
    assert "runtime_health_unverified" in result["reasons"]
    assert result["permissionTier"] == "T2"
    assert result["orchestratorHints"]["allowedTaskClasses"] == ["read"]
    assert result["acp"]["acsHash"] == "hash-1"
    assert result["runtime"]["status"] == "unknown"
    assert result["runtime"]["healthProbe"]["checked"] is False
    assert result["runtime"]["rpcProbe"]["checked"] is False
    assert result["visibility"]["visibility"] == "public"


def test_get_passport_dispatch_uses_health_probe(monkeypatch, atr_client):
    valid_aic = aic.generate_aic()
    agent = _fake_agent(valid_aic)
    passport = _fake_passport()
    passport.passport_payload["acp"]["endpoints"] = [
        {"url": "http://agent.example/rpc", "healthCheckUrl": "http://agent.example/health"}
    ]

    def _fake_get_latest_passport(db, agent_aic):
        return agent, passport

    class _FakeResponse:
        status_code = 200
        def json(self):
            return {"jsonrpc": "2.0", "result": {"state": "completed", "fallback": False}}

    monkeypatch.setattr(
        api_atr, "get_latest_agent_passport_by_aic", _fake_get_latest_passport
    )
    monkeypatch.setattr("app.agent.service.requests.get", lambda url, timeout: _FakeResponse())
    monkeypatch.setattr("app.agent.service.requests.post", lambda url, json, timeout: _FakeResponse())

    response = atr_client.get(f"/acps-atr-v2/passports/{valid_aic}/dispatch")

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["eligibleForDispatch"] is True
    assert result["runtime"]["status"] == "online"
    assert result["runtime"]["healthProbe"]["checked"] is True
    assert result["runtime"]["rpcProbe"]["checked"] is True
    assert result["runtime"]["rpcProbe"]["ok"] is True
    assert result["runtime"]["healthProbe"]["url"] == "http://agent.example/health"


def test_get_passport_dispatch_blocks_failed_health_probe(monkeypatch, atr_client):
    valid_aic = aic.generate_aic()
    agent = _fake_agent(valid_aic)
    passport = _fake_passport()
    passport.passport_payload["acp"]["endpoints"] = [
        {"url": "http://agent.example/rpc", "healthCheckUrl": "http://agent.example/health"}
    ]

    def _fake_get_latest_passport(db, agent_aic):
        return agent, passport

    class _FakeResponse:
        status_code = 503

    monkeypatch.setattr(
        api_atr, "get_latest_agent_passport_by_aic", _fake_get_latest_passport
    )
    monkeypatch.setattr("app.agent.service.requests.get", lambda url, timeout: _FakeResponse())

    response = atr_client.get(f"/acps-atr-v2/passports/{valid_aic}/dispatch")

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["eligibleForDispatch"] is False
    assert result["runtime"]["status"] == "unhealthy"
    assert "runtime_health_unhealthy" in result["reasons"]


def test_get_passport_dispatch_blocks_rpc_fallback(monkeypatch, atr_client):
    valid_aic = aic.generate_aic()
    agent = _fake_agent(valid_aic)
    passport = _fake_passport()
    passport.passport_payload["acp"]["endpoints"] = [
        {"url": "http://agent.example/rpc", "healthCheckUrl": "http://agent.example/health"}
    ]

    def _fake_get_latest_passport(db, agent_aic):
        return agent, passport

    class _HealthResponse:
        status_code = 200

    class _RpcResponse:
        status_code = 200
        def json(self):
            return {"jsonrpc": "2.0", "result": {"state": "completed", "fallback": True}}

    monkeypatch.setattr(
        api_atr, "get_latest_agent_passport_by_aic", _fake_get_latest_passport
    )
    monkeypatch.setattr("app.agent.service.requests.get", lambda url, timeout: _HealthResponse())
    monkeypatch.setattr("app.agent.service.requests.post", lambda url, json, timeout: _RpcResponse())

    response = atr_client.get(f"/acps-atr-v2/passports/{valid_aic}/dispatch")

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["eligibleForDispatch"] is False
    assert result["runtime"]["rpcProbe"]["fallback"] is True
    assert "runtime_rpc_fallback" in result["reasons"]


def test_get_passport_dispatch_blocks_runtime_and_external_share(monkeypatch, atr_client):
    valid_aic = aic.generate_aic()
    agent = _fake_agent(valid_aic)
    passport = _fake_passport()
    passport.passport_payload["runtimeStatus"] = {
        "status": "offline",
        "currentLoad": 3,
        "maxConcurrentTasks": 3,
    }
    passport.passport_payload["orchestratorHints"]["callableByOthers"] = False

    def _fake_get_latest_passport(db, agent_aic):
        return agent, passport

    monkeypatch.setattr(
        api_atr, "get_latest_agent_passport_by_aic", _fake_get_latest_passport
    )

    response = atr_client.get(f"/acps-atr-v2/passports/{valid_aic}/dispatch")
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["eligibleForDispatch"] is False
    assert "agent_runtime_offline" in result["reasons"]
    assert "agent_overloaded" in result["reasons"]
    assert "agent_sharing_disabled" in result["reasons"]
    assert result["runtime"]["loadRatio"] == 1.0


def test_get_passport_dispatch_allows_owner_for_private_agent(monkeypatch, atr_client):
    valid_aic = aic.generate_aic()
    agent = _fake_agent(valid_aic)
    passport = _fake_passport()
    passport.passport_payload["visibility"] = "private"
    passport.passport_payload["acp"]["endpoints"] = [
        {"url": "http://agent.example/rpc", "healthCheckUrl": "http://agent.example/health"}
    ]

    def _fake_get_latest_passport(db, agent_aic):
        return agent, passport

    monkeypatch.setattr(
        api_atr, "get_latest_agent_passport_by_aic", _fake_get_latest_passport
    )

    class _FakeResponse:
        status_code = 200
        def json(self):
            return {"jsonrpc": "2.0", "result": {"state": "completed", "fallback": False}}

    monkeypatch.setattr("app.agent.service.requests.get", lambda url, timeout: _FakeResponse())
    monkeypatch.setattr("app.agent.service.requests.post", lambda url, json, timeout: _FakeResponse())

    owner_id = str(agent.created_by_id)
    owner_response = atr_client.get(
        f"/acps-atr-v2/passports/{valid_aic}/dispatch?requesterUserId={owner_id}"
    )
    assert owner_response.status_code == 200
    owner_result = owner_response.json()["result"]
    assert owner_result["eligibleForDispatch"] is True
    assert owner_result["visibility"]["requesterIsOwner"] is True

    outsider_response = atr_client.get(f"/acps-atr-v2/passports/{valid_aic}/dispatch")
    outsider_result = outsider_response.json()["result"]
    assert outsider_result["eligibleForDispatch"] is False
    assert "agent_private_to_owner" in outsider_result["reasons"]


def test_get_passport_dispatch_blocks_suspended_passport(monkeypatch, atr_client):
    valid_aic = aic.generate_aic()
    agent = _fake_agent(valid_aic)
    passport = _fake_passport(status="SUSPENDED", decision="REJECT")

    def _fake_get_latest_passport(db, agent_aic):
        return agent, passport

    monkeypatch.setattr(
        api_atr, "get_latest_agent_passport_by_aic", _fake_get_latest_passport
    )

    response = atr_client.get(f"/acps-atr-v2/passports/{valid_aic}/dispatch")
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["eligibleForDispatch"] is False
    assert "passport_status_suspended" in result["reasons"]
    assert "review_decision_reject" in result["reasons"]


def test_get_passport_dispatch_blocks_unapproved_agent(monkeypatch, atr_client):
    valid_aic = aic.generate_aic()
    agent = _fake_agent(valid_aic)
    agent.approval_status = ApprovalStatus.PENDING
    passport = _fake_passport()

    def _fake_get_latest_passport(db, agent_aic):
        return agent, passport

    monkeypatch.setattr(
        api_atr, "get_latest_agent_passport_by_aic", _fake_get_latest_passport
    )

    response = atr_client.get(f"/acps-atr-v2/passports/{valid_aic}/dispatch")
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["eligibleForDispatch"] is False
    assert "agent_not_approved" in result["reasons"]


def test_list_discovery_passports_returns_indexable_items(monkeypatch, atr_client):
    expected_items = [
        {
            "agentAic": aic.generate_aic(),
            "passportId": "passport_review_1",
            "status": "VALID",
            "permissionTier": "T2",
        }
    ]

    def _fake_list_discovery_passports(db, limit=100, requester_user_id=None):
        assert limit == 25
        assert requester_user_id is None
        return expected_items

    monkeypatch.setattr(
        api_atr, "list_discovery_passport_summaries", _fake_list_discovery_passports
    )

    response = atr_client.get("/acps-atr-v2/passports/discovery?limit=25")
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["items"] == expected_items
    assert result["total"] == 1
    assert result["limit"] == 25


def test_schedule_passport_runtime_reviews_calls_scheduler(monkeypatch, atr_client):
    observed = {}

    def _fake_scheduler(db, limit=100, sync_certificates=False):
        observed["limit"] = limit
        observed["sync_certificates"] = sync_certificates
        return {
            "status": "completed",
            "checkedCount": 2,
            "dueCount": 1,
            "updatedCount": 1,
            "certificateSyncCount": 1,
            "items": [{"passportId": "passport_review_1"}],
            "alerts": [],
            "evaluatedAt": "2026-06-03T10:00:00+08:00",
        }

    monkeypatch.setattr(
        api_atr, "run_passport_runtime_review_scheduler", _fake_scheduler
    )

    response = atr_client.post(
        "/acps-atr-v2/passports/runtime-review/schedule?limit=2&syncCertificates=true"
    )

    assert response.status_code == 200
    assert observed == {"limit": 2, "sync_certificates": True}
    result = response.json()["result"]
    assert result["checkedCount"] == 2
    assert result["certificateSyncCount"] == 1
