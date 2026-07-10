import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service import _decide_with_route_classification, _registry_token_from_payload, create_server


class FakeRegistryHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path.startswith("/passports/discovery"):
            body = {
                "status": "ok",
                "result": {
                    "items": [
                        {
                            "agentAic": "agent-search",
                            "agentId": "agent-id-search",
                            "name": "Search Agent",
                            "passportId": "passport-search",
                            "reviewId": "review-search",
                            "status": "VALID",
                            "decision": "APPROVE",
                            "riskLevel": "LOW",
                            "permissionTier": "T3",
                            "domains": ["text"],
                            "taskTypes": ["public_information_retrieval"],
                            "declaredSkills": [
                                {"skillId": "search.web", "name": "Web Search", "description": "Find public sources."}
                            ],
                            "orchestratorHints": {
                                "eligibleForAutoDispatch": True,
                                "eligibleForMultiAgentMode": True,
                                "parallelSafe": True,
                                "rankingAdjustments": {"capabilityBoost": 0.05, "riskPenalty": 0},
                            },
                            "capabilities": {"capabilityConfidence": 0.9},
                            "acp": {"endpoints": [{"url": "http://127.0.0.1:8021/rpc"}]},
                        },
                        {
                            "agentAic": "agent-writer",
                            "agentId": "agent-id-writer",
                            "name": "Writing Agent",
                            "passportId": "passport-writer",
                            "reviewId": "review-writer",
                            "status": "VALID",
                            "decision": "APPROVE",
                            "riskLevel": "LOW",
                            "permissionTier": "T3",
                            "domains": ["text"],
                            "taskTypes": ["structured_json_response"],
                            "declaredSkills": [
                                {"skillId": "write.report", "name": "Report Writing", "description": "Write a final report."}
                            ],
                            "orchestratorHints": {
                                "eligibleForAutoDispatch": True,
                                "eligibleForMultiAgentMode": True,
                                "parallelSafe": True,
                                "rankingAdjustments": {"capabilityBoost": 0.05, "riskPenalty": 0},
                            },
                            "capabilities": {"capabilityConfidence": 0.88},
                            "acp": {"endpoints": [{"url": "http://127.0.0.1:8022/rpc"}]},
                        },
                    ],
                    "total": 2,
                    "limit": 25,
                },
            }
            self._send_json(body)
            return

        if self.path.startswith("/passports/") and self.path.endswith("/dispatch"):
            agent_aic = self.path.split("/")[2]
            body = {
                "status": "ok",
                "result": {
                    "agentAic": agent_aic,
                    "status": "VALID",
                    "eligibleForDispatch": True,
                    "reasons": [],
                    "decision": "APPROVE",
                    "riskLevel": "LOW",
                    "permissionTier": "T3",
                    "orchestratorHints": {"eligibleForAutoDispatch": True, "parallelSafe": True},
                    "permissions": {"tier": "T3"},
                },
            }
            self._send_json(body)
            return

        self.send_response(404)
        self.end_headers()

    def _send_json(self, body):
        data = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class RegistryPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = ThreadingHTTPServer(("127.0.0.1", 0), FakeRegistryHandler)
        cls.registry_port = cls.registry.server_address[1]
        cls.registry_thread = threading.Thread(target=cls.registry.serve_forever, daemon=True)
        cls.registry_thread.start()

        cls.mode_router = create_server("127.0.0.1", 0)
        cls.mode_router_port = cls.mode_router.server_address[1]
        cls.mode_router_thread = threading.Thread(target=cls.mode_router.serve_forever, daemon=True)
        cls.mode_router_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.registry.shutdown()
        cls.registry.server_close()
        cls.registry_thread.join(timeout=2)
        cls.mode_router.shutdown()
        cls.mode_router.server_close()
        cls.mode_router_thread.join(timeout=2)

    def test_registry_pipeline_builds_plan_with_dispatch_guards(self):
        payload = {
            "task": "research and write a public information brief",
            "registry_url": f"http://127.0.0.1:{self.registry_port}",
            "save_report": False,
            "route_scores": {"LLM": 0.05, "Agent": 0.2, "多Agent": 0.95},
            "hints": {
                "estimated_skill_count": 2,
                "requires_independent_roles": True,
                "parallelizable": True,
            },
        }
        request = Request(
            f"http://127.0.0.1:{self.mode_router_port}/pipeline/registry",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            body = json.loads(response.read().decode("utf-8"))

        self.assertEqual(body["source"], "registry_pipeline")
        self.assertEqual(body["route_classification"]["label"], "多Agent")
        self.assertEqual(body["normalized_skill_count"], 2)
        self.assertEqual(body["decision"]["mode"], "mode_2")
        self.assertEqual(body["plan"]["registry_validation"]["status"], "passed")
        self.assertTrue(body["plan"]["work_packages"][0]["dispatch_guard"]["eligible_for_dispatch"])
        self.assertEqual(set(body["dispatch_views"].keys()), {"agent-search", "agent-writer"})

    def test_registry_pipeline_llm_route_does_not_require_registry(self):
        payload = {
            "task": "解释一下什么是递归。",
            "save_report": False,
            "route_scores": {"LLM": 0.95, "Agent": 0.1, "多Agent": 0.05},
        }
        request = Request(
            f"http://127.0.0.1:{self.mode_router_port}/pipeline/registry",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            body = json.loads(response.read().decode("utf-8"))

        self.assertEqual(body["route_classification"]["label"], "LLM")
        self.assertEqual(body["decision"]["mode"], "mode_0")
        self.assertEqual(body["plan"]["strategy"], "llm_direct_answer")
        self.assertEqual(body["dispatch_views"], {})

    def test_multi_agent_route_keeps_all_discovered_candidates(self):
        from route_classifier import ROUTE_MULTI_AGENT

        skills = [
            {"aic": f"agent-{index}", "agent_name": f"Agent {index}", "skillid": f"skill-{index}"}
            for index in range(5)
        ]
        decision = _decide_with_route_classification(
            "coordinate five specialist agents",
            skills,
            {},
            {},
            {"label": ROUTE_MULTI_AGENT, "scores": {"multi": 0.99}, "reasoning": ["forced multi-agent route"]},
        )

        self.assertEqual(decision.mode, "mode_2")
        self.assertEqual(len(decision.evidence["selected_skills"]), 5)
        self.assertEqual(decision.evidence["relevant_skill_count"], 5)
        self.assertEqual(decision.evidence["distinct_agent_count"], 5)
    def test_registry_token_accepts_auth_aliases(self):
        self.assertEqual(
            _registry_token_from_payload({"registry_auth_token": "alias-token"}),
            "alias-token",
        )
        self.assertEqual(
            _registry_token_from_payload({"authToken": "camel-token"}),
            "camel-token",
        )


if __name__ == "__main__":
    unittest.main()
