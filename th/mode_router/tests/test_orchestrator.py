\
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from discovery_client import build_discovery_request
from mode_selector import MODE_1, MODE_2, ModeDecision, decide_mode
from orchestrator import build_execution_plan, execute_plan_dry_run, get_placeholder_connector_contract


class OrchestratorTests(unittest.TestCase):
    def test_build_mode1_plan(self):
        skills = [
            {"aic": "agent-data", "agent_name": "Data Agent", "skillid": "query", "score": 0.95},
            {"aic": "agent-data", "agent_name": "Data Agent", "skillid": "chart", "score": 0.91}
        ]
        decision = decide_mode("build a report", skills, hints={"estimated_skill_count": 2})
        plan = build_execution_plan("build a report", skills, decision=decision)
        self.assertEqual(plan["mode"], MODE_1)
        self.assertEqual(plan["primary_agent"]["name"], "Data Agent")
        self.assertEqual(plan["strategy"], "single_agent_multi_skill")

    def test_build_mode2_plan(self):
        skills = [
            {"aic": "market", "agent_name": "Market Agent", "skillid": "market", "score": 0.93},
            {"aic": "legal", "agent_name": "Legal Agent", "skillid": "legal", "score": 0.92},
            {"aic": "finance", "agent_name": "Finance Agent", "skillid": "finance", "score": 0.90}
        ]
        decision = decide_mode("design a go-to-market plan", skills, hints={"estimated_skill_count": 3, "requires_independent_roles": True, "parallelizable": True})
        plan = build_execution_plan("design a go-to-market plan", skills, decision=decision)
        self.assertEqual(plan["mode"], MODE_2)
        self.assertEqual(plan["strategy"], "tree_root_parallel_children")
        self.assertEqual(len(plan["work_packages"]), 3)
        self.assertEqual(plan["coordinator"]["name"], "Market Agent")
        self.assertEqual(plan["root_package"]["agent"]["name"], "Market Agent")
        self.assertEqual(plan["group_chat"]["protocol"], "rabbitmq_group_chat")
        self.assertEqual(plan["group_chat"]["agent_group_endpoint"], "/group/rpc")
        self.assertEqual(len(plan["orchestration_tree"]["children"]), 3)
        for child in plan["orchestration_tree"]["children"]:
            self.assertEqual(child["parent_node"], plan["root_package"]["package_id"])
            self.assertEqual(child["input_from"], "root_agent")
            self.assertEqual(child["output_to"], "root_agent")

    def test_build_mode2_plan_sequential_children_have_dependency_chain(self):
        skills = [
            {"aic": "search", "agent_name": "Search Agent", "skillid": "search", "score": 0.95},
            {"aic": "analysis", "agent_name": "Analysis Agent", "skillid": "analysis", "score": 0.92},
            {"aic": "writing", "agent_name": "Writing Agent", "skillid": "writing", "score": 0.91}
        ]
        decision = decide_mode("write a literature review", skills, hints={"estimated_skill_count": 3, "requires_independent_roles": True, "parallelizable": False})
        plan = build_execution_plan("write a literature review", skills, decision=decision)
        self.assertEqual(plan["strategy"], "tree_root_sequential_children")
        self.assertEqual(plan["work_packages"][0]["depends_on"], [])
        self.assertEqual(len(plan["work_packages"][1]["depends_on"]), 1)
        self.assertEqual(len(plan["work_packages"][2]["depends_on"]), 1)

    def test_execute_plan_dry_run(self):
        skills = [
            {"aic": "market", "agent_name": "Market Agent", "skillid": "market", "score": 0.93},
            {"aic": "legal", "agent_name": "Legal Agent", "skillid": "legal", "score": 0.92},
            {"aic": "finance", "agent_name": "Finance Agent", "skillid": "finance", "score": 0.90}
        ]
        decision = decide_mode("design a go-to-market plan", skills, hints={"estimated_skill_count": 3, "requires_independent_roles": True})
        plan = build_execution_plan("design a go-to-market plan", skills, decision=decision)
        execution = execute_plan_dry_run(plan)
        self.assertTrue(execution["dry_run"])
        self.assertEqual(len(execution["runs"]), 3)

    def test_connector_contract_has_required_endpoints(self):
        contract = get_placeholder_connector_contract()
        required_paths = {endpoint["path"] for endpoint in contract["required_endpoints"]}
        self.assertIn("/tasks", required_paths)
        self.assertIn("/tasks/{run_id}", required_paths)
        self.assertEqual(contract["group_chat_protocol"]["agent_group_endpoint"], "/group/rpc")

    def test_discovery_request_includes_selection_and_workability_context(self):
        request = build_discovery_request(
            "build a market launch plan",
            {
                "route_label": "multi_agent",
                "limit": 4,
                "requester_user_id": "user-1",
                "session_id": "session-1",
            },
        )
        self.assertEqual(request["selection"]["mode"], "multi_agent")
        self.assertEqual(request["selection"]["minAgents"], 2)
        self.assertTrue(request["selection"]["workableOnly"])
        self.assertEqual(request["context"]["conversationId"], "session-1")
        self.assertEqual(request["context"]["metadata"]["selectionMode"], "multi_agent")
        self.assertEqual(request["context"]["metadata"]["requesterUserId"], "user-1")

    def test_build_mode0_llm_direct_plan(self):
        decision = ModeDecision(
            mode="mode_0",
            label="LLM",
            next_step="llm_direct",
            summary="direct answer",
            reasoning=[],
            evidence={"route_scores": {"LLM": 0.95, "Agent": 0.1, "多Agent": 0.05}},
        )
        plan = build_execution_plan("解释一下递归", [], decision=decision)
        self.assertEqual(plan["mode"], "mode_0")
        self.assertEqual(plan["strategy"], "llm_direct_answer")
        self.assertEqual(plan["work_packages"], [])


if __name__ == "__main__":
    unittest.main()
