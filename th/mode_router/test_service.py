\
import json
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import service
from service import create_server
from route_classifier import RouteClassification


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def _get_json(self, path: str) -> dict:
        with urlopen(f"http://127.0.0.1:{self.port}{path}") as response:
            return json.loads(response.read().decode("utf-8"))

    def _post_json(self, path: str, payload: dict) -> dict:
        request = Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_health_endpoint(self):
        response = self._get_json("/health")
        self.assertEqual(response["status"], "ok")

    def test_traffic_snapshot_endpoint_exposes_agent_message_tokens(self):
        from monitoring.traffic_monitor import record, reset

        reset()
        record("leader", "agent-a", 42, edge_type="unit_test")
        response = self._get_json("/traffic/snapshot")

        self.assertTrue(response["enabled"])
        self.assertEqual(response["global_tokens_total"], 42)
        self.assertEqual(response["messages_total"], 1)
        self.assertEqual(response["edges"][0]["from"], "leader")
        self.assertEqual(response["edges"][0]["to"], "agent-a")
        self.assertEqual(response["platform_mode2_group_chat"]["tokens_total"], 42)
        self.assertEqual(response["platform_mode2_group_chat"]["edge_types"][0]["edge_type"], "unit_test")

        mode2 = self._get_json("/traffic/platform/mode2")
        self.assertEqual(mode2["tokens_total"], 42)
        self.assertEqual(mode2["window"]["tokens_total"], 42)

    def test_workflow_latest_exposes_progress_and_role_status(self):
        old_runs_dir = service.RUNS_DIR
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                runs_dir = Path(tmpdir)
                run_dir = runs_dir / "20260603_demo"
                run_dir.mkdir()
                service.RUNS_DIR = runs_dir
                (run_dir / "01_user_request.json").write_text(json.dumps({"task": "demo task"}), encoding="utf-8")
                (run_dir / "06_mode_decision.json").write_text(json.dumps({"mode": "mode_2", "summary": "parallel"}), encoding="utf-8")
                (run_dir / "07_orchestrator_plan.json").write_text(
                    json.dumps({"strategy": "tree_root_parallel_children", "work_packages": [{"id": "search"}]}),
                    encoding="utf-8",
                )
                (run_dir / "08_role_agents.json").write_text(
                    json.dumps({"search": {"name": "search agent"}}),
                    encoding="utf-8",
                )
                (run_dir / "08e_workflow_checklist.json").write_text(
                    json.dumps(
                        {
                            "steps": [
                                {"stage": "user_input", "status": "done", "description": "received", "artifact": "01_user_request.json"},
                                {"stage": "agent_search", "status": "done", "description": "search done", "artifact": "step1_search_result.json"},
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                (run_dir / "09_full_data_flow.json").write_text(
                    json.dumps(
                        {
                            "final_result": "hello",
                            "orchestration_tree": {"children": [{"role": "search", "agent_name": "search agent"}]},
                            "steps": [
                                {
                                    "role": "search",
                                    "agent": {"name": "search agent"},
                                    "task_id": "task-search",
                                    "final_state": "awaiting-completion",
                                    "output_length": 5,
                                    "depends_on_roles": [],
                                }
                            ],
                        }
                    ),
                    encoding="utf-8",
                )
                (run_dir / "12_state_events.jsonl").write_text(
                    "\n".join(
                        [
                            json.dumps({"timestamp": "t1", "stage": "workflow_start", "state": "running", "message": "start"}),
                            json.dumps({"timestamp": "t2", "stage": "agent_dispatch", "state": "waiting_summary", "role": "search", "agent_name": "search agent", "message": "ready"}),
                            json.dumps({"timestamp": "t3", "stage": "workflow_complete", "state": "done", "message": "done"}),
                        ]
                    ),
                    encoding="utf-8",
                )
                response = self._get_json("/workflow/latest")
        finally:
            service.RUNS_DIR = old_runs_dir

        self.assertEqual(response["status"], "done")
        self.assertEqual(response["progress"]["percent"], 100)
        self.assertEqual(response["role_progress"][0]["role"], "search")
        self.assertEqual(response["stage_progress"][1]["stage"], "agent_search")
        self.assertEqual(response["final_length"], 5)

    def test_mode_decide_endpoint_has_zh(self):
        response = self._post_json(
            "/mode/decide",
            {
                "task": "build a sales report",
                "skills": [
                    {"aic": "agent-data", "agent_name": "Data Agent", "skillid": "query", "score": 0.95},
                    {"aic": "agent-data", "agent_name": "Data Agent", "skillid": "chart", "score": 0.91}
                ],
                "hints": {"estimated_skill_count": 2}
            }
        )
        self.assertEqual(response["decision"]["mode"], "mode_1")
        self.assertIn("zh", response)
        self.assertIn("decision", response["zh"])

    def test_mode_classify_endpoint_returns_three_way_route(self):
        response = self._post_json(
            "/mode/classify",
            {
                "task": "设计一个系统架构，需要后端、前端、运维和安全审查分工协作。",
                "save_report": False,
            },
        )
        self.assertEqual(response["route_classification"]["label"], "多Agent")
        self.assertEqual(response["decision"]["mode"], "mode_2")

    def test_route_classification_can_select_llm_mode_even_when_skills_exist(self):
        decision = service._decide_with_route_classification(
            "解释一下递归。",
            [{"aic": "agent-data", "agent_name": "Data Agent", "skillid": "query", "score": 0.95}],
            {},
            {},
            {
                "label": "LLM",
                "mode": "mode_0",
                "next_step": "llm_direct",
                "summary": "direct",
                "reasoning": ["Top route score is LLM=0.95."],
                "scores": {"LLM": 0.95, "Agent": 0.1, "多Agent": 0.05},
            },
        )

        self.assertEqual(decision.mode, "mode_0")
        self.assertEqual(decision.next_step, "llm_direct")
        self.assertEqual(decision.evidence["route_label"], "LLM")

    def test_orchestrator_execute_mode0_returns_final_answer(self):
        response = self._post_json(
            "/orchestrator/execute",
            {
                "task": "1+1=?",
                "route_scores": {"LLM": 0.95, "Agent": 0.1, service.ROUTE_MULTI_AGENT: 0.05},
            },
        )

        self.assertEqual(response["decision"]["mode"], "mode_0")
        self.assertEqual(response["execution"]["status"], "done")
        self.assertEqual(response["execution"]["final_result"], "2")
        self.assertEqual(response["final_result"], "2")
        self.assertNotEqual(response["execution"]["status"], "skipped")

    def test_orchestrator_plan_from_discovery_response(self):
        response = self._post_json(
            "/orchestrator/plan",
            {
                "task": "prepare an expansion plan",
                "hints": {"estimated_skill_count": 2, "requires_independent_roles": True},
                "discovery_response": {
                    "result": {
                        "acsMap": {
                            "agent-market": {"name": "Market Agent"},
                            "agent-legal": {"name": "Legal Agent"}
                        },
                        "agents": [
                            {
                                "group": "default",
                                "agentSkills": [
                                    {"aic": "agent-market", "skillId": "market-entry", "ranking": 1, "memo": "enhanced_score=0.92"},
                                    {"aic": "agent-legal", "skillId": "compliance", "ranking": 2, "memo": "enhanced_score=0.91"}
                                ]
                            }
                        ]
                    }
                }
            }
        )
        self.assertEqual(response["source"], "discovery_response")
        self.assertEqual(response["decision"]["mode"], "mode_2")
        self.assertEqual(response["plan"]["mode"], "mode_2")
        self.assertIn("plan", response["zh"])

    def test_orchestrator_execute_mode1_discovers_and_calls_single_agent(self):
        calls = {"discovery": 0, "agent": 0, "agent_payload": None}

        class AgentHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def do_POST(self):
                calls["agent"] += 1
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8")
                calls["agent_payload"] = json.loads(raw)
                body = {
                    "jsonrpc": "2.0",
                    "id": calls["agent_payload"].get("id"),
                    "result": {
                        "state": "completed",
                        "products": [
                            {
                                "content": "agent completed task",
                                "dataItems": [{"type": "text", "text": "agent completed task"}],
                            }
                        ],
                    },
                }
                payload = json.dumps(body).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        agent_server = ThreadingHTTPServer(("127.0.0.1", 0), AgentHandler)
        agent_thread = threading.Thread(target=agent_server.serve_forever, daemon=True)
        agent_thread.start()
        agent_url = f"http://127.0.0.1:{agent_server.server_address[1]}/rpc"

        class DiscoveryHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def do_POST(self):
                calls["discovery"] += 1
                length = int(self.headers.get("Content-Length", "0"))
                self.rfile.read(length)
                body = {
                    "result": {
                        "acsMap": {
                            "agent-news": {
                                "name": "News Agent",
                                "endPoints": [{"url": agent_url, "transport": "http"}],
                            }
                        },
                        "agents": [
                            {
                                "group": "default",
                                "agentSkills": [
                                    {
                                        "aic": "agent-news",
                                        "skillId": "news-summary",
                                        "ranking": 1,
                                        "memo": "enhanced_score=0.96",
                                    }
                                ],
                            }
                        ],
                    }
                }
                payload = json.dumps(body).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        discovery_server = ThreadingHTTPServer(("127.0.0.1", 0), DiscoveryHandler)
        discovery_thread = threading.Thread(target=discovery_server.serve_forever, daemon=True)
        discovery_thread.start()
        discovery_url = f"http://127.0.0.1:{discovery_server.server_address[1]}/discover"

        try:
            response = self._post_json(
                "/orchestrator/execute",
                {
                    "task": "search current industry news and summarize it",
                    "discovery_url": discovery_url,
                    "registry_url": "http://127.0.0.1:1",
                    "prefer_discovery": True,
                    "check_dispatch": False,
                    "route_scores": {"LLM": 0.05, "Agent": 0.95, service.ROUTE_MULTI_AGENT: 0.1},
                },
            )
        finally:
            discovery_server.shutdown()
            discovery_server.server_close()
            discovery_thread.join(timeout=2)
            agent_server.shutdown()
            agent_server.server_close()
            agent_thread.join(timeout=2)

        self.assertEqual(calls["discovery"], 1)
        self.assertEqual(calls["agent"], 1)
        self.assertEqual(response["candidate_source"], "discovery")
        self.assertEqual(response["decision"]["mode"], "mode_1")
        self.assertEqual(response["execution"]["status"], "done")
        self.assertFalse(response["execution"]["group_chat"])
        self.assertEqual(response["execution"]["runs"][0]["endpoint"], agent_url)
        self.assertIn("agent completed task", response["execution"]["final_result"])
        self.assertIn("agent completed task", response["final_result"])
        self.assertEqual(calls["agent_payload"]["method"], "rpc")
        self.assertEqual(
            calls["agent_payload"]["params"]["command"]["senderRole"],
            "leader",
        )

    def test_http_mode2_polls_working_agent_until_ready(self):
        calls = []

        class AgentHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                command = body["params"]["command"]["command"]
                calls.append(command)
                state = "working"
                data_items = []
                if command == "get":
                    state = "awaiting-completion"
                    data_items = [{"type": "text", "text": "ready output"}]
                elif command == "complete":
                    state = "completed"
                payload = json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": body.get("id"),
                        "result": {
                            "status": {"state": state, "dataItems": data_items},
                            "products": None,
                        },
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        agent_server = ThreadingHTTPServer(("127.0.0.1", 0), AgentHandler)
        agent_thread = threading.Thread(target=agent_server.serve_forever, daemon=True)
        agent_thread.start()
        agent_url = f"http://127.0.0.1:{agent_server.server_address[1]}/rpc"

        try:
            execution = service.execute_plan_http_agents(
                "coordinate a small task",
                {
                    "mode": "mode_2",
                    "strategy": "tree_root_dependency_children",
                    "work_packages": [
                        {
                            "package_id": "pkg-a",
                            "objective": "produce output",
                            "agent": {"aic": "agent-a", "name": "Agent A", "url": agent_url},
                        }
                    ],
                },
                payload={"agent_poll_interval": 0.2, "agent_poll_timeout": 2, "agent_timeout": 5},
            )
        finally:
            agent_server.shutdown()
            agent_server.server_close()
            agent_thread.join(timeout=2)

        self.assertEqual(execution["status"], "done")
        self.assertEqual(calls[:3], ["start", "get", "complete"])
        self.assertIn("ready output", execution["final_result"])

    def test_mode2_defaults_to_generic_group_executor(self):
        payload = {
            "candidate_skills": [
                {
                    "aic": "agent-a",
                    "agent_name": "Agent A",
                    "skillid": "plan",
                    "score": 0.95,
                    "acs": {"endpoints": [{"url": "http://127.0.0.1:9/rpc"}]},
                },
                {
                    "aic": "agent-b",
                    "agent_name": "Agent B",
                    "skillid": "build",
                    "score": 0.93,
                    "acs": {"endpoints": [{"url": "http://127.0.0.1:9/rpc"}]},
                },
            ],
            "hints": {"requires_independent_roles": True},
            "check_dispatch": False,
            "route_scores": {"LLM": 0.0, "Agent": 0.2, service.ROUTE_MULTI_AGENT: 0.9},
        }
        group_result = {"status": "done", "group_chat": True, "runs": [], "final_result": "group ok"}

        fake_route = RouteClassification(
            scores={"LLM": 0.0, "Agent": 0.2, service.ROUTE_MULTI_AGENT: 0.9},
            label=service.ROUTE_MULTI_AGENT,
            mode="mode_2",
            next_step="orchestrator",
            summary="multi-agent",
            reasoning=["mocked"],
            prompt_source="mock",
            llm_used=False,
            model="mock",
            raw_response=None,
        )

        with patch.object(service, "classify_task_route", return_value=fake_route):
            with patch.object(service, "execute_plan_group_chat", return_value=group_result) as group_call:
                with patch.object(service, "execute_plan_http_agents") as http_call:
                    response = service._build_orchestrator_execute_response("coordinate a multi-agent build", payload)

        group_call.assert_called_once()
        http_call.assert_not_called()
        self.assertEqual(response["decision"]["mode"], "mode_2")
        self.assertTrue(response["execution"]["group_chat"])
        self.assertEqual(response["final_result"], "group ok")

    def test_orchestrator_execute_agent_route_defaults_to_square_registry(self):
        calls = {"registry": 0, "discovery": 0}

        class RegistryHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def do_GET(self):
                calls["registry"] += 1
                if self.path.startswith("/passports/discovery"):
                    self.send_response(404)
                    self.end_headers()
                    return
                if self.path.startswith("/acps-atr-v2/passports/discovery"):
                    body = {
                        "status": "ok",
                        "result": {
                            "items": [
                                {
                                    "agentAic": "agent-square",
                                    "name": "Square Agent",
                                    "version": "2.0.0",
                                    "passportId": "passport-square",
                                    "status": "VALID",
                                    "decision": "APPROVE",
                                    "riskLevel": "LOW",
                                    "permissionTier": "T3",
                                    "declaredSkills": [
                                        {
                                            "skillId": "square.research",
                                            "name": "Square research",
                                            "description": "Summarize public information.",
                                        }
                                    ],
                                    "orchestratorHints": {"eligibleForAutoDispatch": True},
                                    "acp": {"endpoints": [{"url": "http://127.0.0.1:9/rpc"}]},
                                    "eligibleForDispatch": True,
                                    "dispatchReasons": [],
                                }
                            ],
                            "total": 1,
                            "limit": 25,
                        },
                    }
                    payload = json.dumps(body).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                self.send_response(404)
                self.end_headers()

        class DiscoveryHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def do_POST(self):
                calls["discovery"] += 1
                self.send_response(500)
                self.end_headers()

        registry_server = ThreadingHTTPServer(("127.0.0.1", 0), RegistryHandler)
        registry_thread = threading.Thread(target=registry_server.serve_forever, daemon=True)
        registry_thread.start()
        registry_url = f"http://127.0.0.1:{registry_server.server_address[1]}"
        discovery_server = ThreadingHTTPServer(("127.0.0.1", 0), DiscoveryHandler)
        discovery_thread = threading.Thread(target=discovery_server.serve_forever, daemon=True)
        discovery_thread.start()
        discovery_url = f"http://127.0.0.1:{discovery_server.server_address[1]}/discover"

        try:
            response = self._post_json(
                "/orchestrator/execute",
                {
                    "task": "search current industry news and summarize it",
                    "registry_url": registry_url,
                    "discovery_url": discovery_url,
                    "check_dispatch": False,
                    "dry_run": True,
                    "route_scores": {"LLM": 0.05, "Agent": 0.95, service.ROUTE_MULTI_AGENT: 0.1},
                },
            )
        finally:
            registry_server.shutdown()
            registry_server.server_close()
            registry_thread.join(timeout=2)
            discovery_server.shutdown()
            discovery_server.server_close()
            discovery_thread.join(timeout=2)

        self.assertEqual(calls["discovery"], 0)
        self.assertGreaterEqual(calls["registry"], 1)
        self.assertEqual(response["candidate_source"], "registry_discovery")
        self.assertEqual(response["decision"]["mode"], "mode_1")
        self.assertTrue(response["execution"]["dry_run"])
        self.assertEqual(response["plan"]["primary_agent"]["aic"], "agent-square")


if __name__ == "__main__":
    unittest.main()
