import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.agent.exception import AgentException
from app.agent.model import Agent, ApprovalStatus
from app.agent.service import generate_aic_for_agent, update_agent_acs_data
from app.agent.supervisor import (
    _endpoint_checks,
    _endpoint_health_route_check,
    _mutual_tls_checks,
)
from app.utils import acs, aic


FIXTURES = Path(__file__).parent / "fixtures" / "acs"
LEGACY_ACS = Path(__file__).parent.parent / "client" / "amap_data.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestAicDualCompatibility:
    def test_legacy_generation_remains_the_default(self):
        with patch.object(aic.settings, "ACPS_V21_ENABLED", False):
            code = aic.generate_aic()

        parts = code.split(".")
        assert parts[4] == aic.MANAGER_CODE
        assert parts[8] == aic.PROTOCOL_VERSION
        assert aic.validate_aic_v0200(code) is True
        assert aic.validate_aic_v0201(code) is False
        assert aic.get_aic_spec_version(code) == aic.AIC_SPEC_V0200

    def test_v21_generation_moves_the_version_to_segment_five(self):
        code = aic.generate_aic(spec_version=aic.AIC_SPEC_V0201)

        parts = code.split(".")
        assert parts[4] == aic.PROTOCOL_VERSION
        assert parts[5] == aic.MANAGER_CODE
        assert parts[6] == aic.PROVIDER_CODE
        assert aic.get_instance_serial(code) == parts[8]
        assert aic.validate_aic_v0201(code) is True
        assert aic.validate_aic_v0200(code) is False
        assert aic.get_aic_spec_version(code) == aic.AIC_SPEC_V0201

    @pytest.mark.parametrize("spec_version", [aic.AIC_SPEC_V0200, aic.AIC_SPEC_V0201])
    def test_ontology_and_entity_derivation_preserve_the_layout(self, spec_version):
        ontology = aic.generate_ontology_aic(spec_version=spec_version)
        entity = aic.generate_entity_aic_from_ontology(ontology)

        assert entity is not None
        assert aic.get_aic_spec_version(ontology) == spec_version
        assert aic.get_aic_spec_version(entity) == spec_version
        assert aic.is_ontology_aic(ontology) is True
        assert aic.is_entity_aic(entity) is True
        assert aic.get_ontology_aic_from_entity(entity) == ontology

    def test_dual_read_accepts_both_layouts_without_changing_write_default(self):
        legacy = aic.generate_aic(spec_version=aic.AIC_SPEC_V0200)
        current = aic.generate_aic(spec_version=aic.AIC_SPEC_V0201)

        with patch.object(aic.settings, "ACPS_AIC_DUAL_READ_ENABLED", True):
            assert aic.validate_aic(legacy) is True
            assert aic.validate_aic(current) is True

        with (
            patch.object(aic.settings, "ACPS_AIC_DUAL_READ_ENABLED", False),
            patch.object(aic.settings, "ACPS_V21_ENABLED", False),
        ):
            assert aic.validate_aic(legacy) is True
            assert aic.validate_aic(current) is False


class TestAcsDualCompatibility:
    def test_legacy_acs_still_uses_the_legacy_schema_and_challenge_check(self):
        instance = _load_json(LEGACY_ACS)
        for endpoint in instance["endPoints"]:
            endpoint["security"] = [{"mtls": []}]

        with patch("app.utils.acs.check_ca_challenge_base_url", return_value=(True, None)):
            acs.validate(instance)

        assert acs.get_acs_protocol_version(instance) == acs.ACS_PROTOCOL_V0200

    def test_v21_acs_accepts_certificate_and_amqp_without_challenge(self):
        instance = _load_json(FIXTURES / "v02_01_example.json")
        instance["aic"] = aic.generate_aic(spec_version=aic.AIC_SPEC_V0201)
        instance["certificate"] = {
            "altNames": {"dns": ["agent.example.com"], "ip": ["127.0.0.1"]},
            "requestedValidity": 365,
        }
        instance["endPoints"].append(
            {
                "url": "amqps://mq.example.com:5671/acps?inbox=inbox_{AIC}",
                "transport": "AMQP",
                "security": [{"mtls": []}],
            }
        )

        acs.validate(instance)

        assert acs.get_acs_protocol_version(instance) == acs.ACS_PROTOCOL_V0201
        assert "x-caChallengeBaseUrl" not in instance["securitySchemes"]["mtls"]

    def test_v21_write_is_gated_but_read_validation_remains_available(self):
        instance = _load_json(FIXTURES / "v02_01_example.json")

        with patch.object(acs.settings, "ACPS_V21_ENABLED", False):
            acs.validate(instance)
            with pytest.raises(AgentException):
                acs.validate_for_write(instance)

        with patch.object(acs.settings, "ACPS_V21_ENABLED", True):
            acs.validate_for_write(instance)


class TestSupervisorDualCompatibility:
    @staticmethod
    def _check(checks, check_id):
        return next(item for item in checks if item["checkId"] == check_id)

    def test_v21_mtls_does_not_require_legacy_challenge_url(self):
        checks = _mutual_tls_checks(
            {
                "protocolVersion": "02.01",
                "securitySchemes": {"mtls": {"type": "mutualTLS"}},
            }
        )

        challenge_check = self._check(checks, "mtls_challenge_base_url_present")
        assert challenge_check["status"] == "pass"
        assert not any(check["status"] == "fail" for check in checks)

    def test_legacy_mtls_still_requires_challenge_url(self):
        checks = _mutual_tls_checks(
            {
                "protocolVersion": "02.00",
                "securitySchemes": {"mtls": {"type": "mutualTLS"}},
            }
        )

        challenge_check = self._check(checks, "mtls_challenge_base_url_present")
        assert challenge_check["status"] == "fail"
        assert "missing_ca_challenge_base_url" in challenge_check["riskTags"]

    @pytest.mark.parametrize("scheme", ["amqp", "amqps"])
    def test_v21_amqp_endpoint_is_valid_but_not_http_health_probed(self, scheme):
        instance = _load_json(FIXTURES / "v02_01_example.json")
        instance["endPoints"] = [
            {
                "url": f"{scheme}://mq.example.com:5671/acps?inbox=inbox_{{AIC}}",
                "transport": "AMQP",
                "security": [{"mtls": []}],
            }
        ]

        endpoint_checks = _endpoint_checks(instance)
        assert self._check(endpoint_checks, "endpoint_url_format")["status"] == "pass"
        assert _endpoint_health_route_check(instance)["status"] == "pass"
        assert "No valid endpoint URL" in _endpoint_health_route_check(instance)["evidence"][0]


def test_agent_approval_selects_aic_layout_from_acs_protocol_version():
    agent = MagicMock(spec=Agent)
    agent.approval_status = ApprovalStatus.APPROVED
    agent.aic = None
    agent.is_ontology = False
    agent.is_active = True
    agent.acs = {"protocolVersion": "02.01"}
    db = MagicMock()

    with (
        patch.object(aic.settings, "ACPS_V21_ENABLED", True),
        patch("app.agent.service.aic.generate_aic", return_value="v21-aic") as generate,
        patch("app.agent.service.update_agent_acs_data"),
    ):
        generate_aic_for_agent(db, agent)

    generate.assert_called_once_with(spec_version=aic.AIC_SPEC_V0201)
    assert agent.aic == "v21-aic"


def test_agent_approval_replaces_amqp_aic_placeholder():
    original_acs = {
        "protocolVersion": "02.01",
        "aic": "pending",
        "active": True,
        "endPoints": [
            {
                "url": "amqps://mq.example.com:5671/acps?inbox=inbox_{AIC}",
                "transport": "AMQP",
                "security": [{"mtls": []}],
            }
        ],
    }
    agent = MagicMock(spec=Agent)
    agent.id = "agent-id"
    agent.aic = "1.2.156.3088.1.0001.00001.ABCDEF.123456.0000"
    agent.is_active = True
    agent.acs = original_acs

    with patch("app.sync.service.update_agent_with_changelog"):
        update_agent_acs_data(agent, MagicMock())

    assert agent.acs["endPoints"][0]["url"].endswith(f"inbox=inbox_{agent.aic}")
    assert original_acs["endPoints"][0]["url"].endswith("inbox=inbox_{AIC}")
