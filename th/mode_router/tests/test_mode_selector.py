import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mode_selector import INSUFFICIENT_INFO, MODE_1, MODE_2, decide_mode


class ModeSelectorTests(unittest.TestCase):
    def test_mode1_when_single_agent_covers_all_relevant_skills(self):
        decision = decide_mode(
            task_description="build a sales report",
            skills=[
                {"aic": "agent-data", "agent_name": "Data Agent", "skillid": "query", "score": 0.95},
                {"aic": "agent-data", "agent_name": "Data Agent", "skillid": "chart", "score": 0.91},
                {"aic": "agent-data", "agent_name": "Data Agent", "skillid": "ppt", "score": 0.88},
            ],
            hints={"estimated_skill_count": 3},
        )
        self.assertEqual(decision.mode, MODE_1)
        self.assertEqual(decision.next_step, "skill_router")

    def test_mode2_when_independent_roles_are_required(self):
        decision = decide_mode(
            task_description="design a go-to-market plan",
            skills=[
                {"aic": "market", "agent_name": "Market Agent", "skillid": "market", "score": 0.93},
                {"aic": "legal", "agent_name": "Legal Agent", "skillid": "legal", "score": 0.92},
                {"aic": "finance", "agent_name": "Finance Agent", "skillid": "finance", "score": 0.90},
            ],
            hints={"estimated_skill_count": 3, "requires_independent_roles": True},
        )
        self.assertEqual(decision.mode, MODE_2)
        self.assertEqual(decision.next_step, "orchestrator")

    def test_score_can_be_parsed_from_memo(self):
        decision = decide_mode(
            task_description="parse score from memo",
            skills=[
                {"aic": "agent-a", "skillid": "s1", "memo": "llm_score=0.60 enhanced_score=0.83"},
                {"aic": "agent-a", "skillid": "s2", "memo": "llm_score=0.57 enhanced_score=0.81"},
            ],
        )
        self.assertEqual(decision.mode, MODE_1)
        self.assertEqual(decision.evidence["relevant_skill_count"], 2)

    def test_insufficient_info_when_no_skills(self):
        decision = decide_mode(task_description="empty input", skills=[])
        self.assertEqual(decision.mode, INSUFFICIENT_INFO)


if __name__ == "__main__":
    unittest.main()
