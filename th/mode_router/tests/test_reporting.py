\
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reporting import write_report_bundle


class ReportingTests(unittest.TestCase):
    def test_write_report_bundle(self):
        payload = {
            "version": "0.4.0",
            "source": "skills",
            "normalized_skill_count": 2,
            "decision": {
                "mode": "mode_1",
                "next_step": "skill_router",
                "summary": "Recommend mode_1 because one agent covers the task.",
                "reasoning": ["All relevant skills belong to the same agent."],
                "evidence": {
                    "relevant_skill_count": 2,
                    "distinct_agent_count": 1,
                    "best_agent": {"aic": "a1", "name": "??Agent", "coverage": 1.0},
                },
            },
            "zh": {
                "decision": {
                    "??": "??1??Agent + ?Skills",
                    "???": "??????",
                    "??": "?????1?",
                    "??": ["???????????Agent??"],
                    "??": {
                        "?????": 2,
                        "??Agent?": 1,
                        "???Agent": {"AIC": "a1", "??": "??Agent", "???": "100%"},
                    },
                }
            }
        }
        report = write_report_bundle(payload)
        self.assertTrue(Path(report["json"]).exists())
        self.assertTrue(Path(report["markdown"]).exists())


if __name__ == "__main__":
    unittest.main()
