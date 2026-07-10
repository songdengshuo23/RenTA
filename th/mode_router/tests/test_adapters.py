\
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters import (
    extract_skills_from_discovery_response,
    extract_skills_from_registry_discovery_response,
    normalize_request_payload,
)


class AdapterTests(unittest.TestCase):
    def test_extract_skills_from_discovery_response(self):
        payload = {
            "result": {
                "acsMap": {
                    "agent-a": {"name": "Agent A"}
                },
                "agents": [
                    {
                        "group": "default",
                        "agentSkills": [
                            {"aic": "agent-a", "skillId": "skill-1", "ranking": 1, "memo": "enhanced_score=0.91"}
                        ]
                    }
                ]
            }
        }
        skills = extract_skills_from_discovery_response(payload)
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0]["agent_name"], "Agent A")
        self.assertEqual(skills[0]["skillid"], "skill-1")

    def test_normalize_request_payload_prefers_discovery_response(self):
        sample_path = Path(__file__).resolve().parents[1] / "examples" / "sample_discovery_response.json"
        payload = json.loads(sample_path.read_text(encoding="utf-8"))
        normalized = normalize_request_payload(payload)
        self.assertEqual(normalized["source"], "discovery_response")
        self.assertEqual(len(normalized["skills"]), 4)

    def test_extract_skills_from_registry_discovery_response(self):
        payload = {
            "status": "ok",
            "result": {
                "items": [
                    {
                        "agentAic": "agent-aic",
                        "agentId": "agent-id",
                        "name": "Registry Agent",
                        "passportId": "passport-1",
                        "reviewId": "review-1",
                        "status": "VALID",
                        "decision": "APPROVE",
                        "riskLevel": "LOW",
                        "permissionTier": "T3",
                        "domains": ["text"],
                        "taskTypes": ["public_information_retrieval"],
                        "declaredSkills": [
                            {
                                "skillId": "general/search",
                                "name": "Search",
                                "description": "Find public information.",
                            }
                        ],
                        "orchestratorHints": {
                            "eligibleForAutoDispatch": True,
                            "parallelSafe": True,
                            "rankingAdjustments": {"capabilityBoost": 0.05, "riskPenalty": 0},
                        },
                        "capabilities": {"capabilityConfidence": 0.9},
                        "acp": {"endpoints": [{"url": "https://agent.example.com/rpc"}]},
                    }
                ]
            },
        }
        skills = extract_skills_from_registry_discovery_response(payload)
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0]["aic"], "agent-aic")
        self.assertEqual(skills[0]["skillid"], "general/search")
        self.assertEqual(skills[0]["agent_name"], "Registry Agent")
        self.assertEqual(skills[0]["acs"]["endPoints"][0]["url"], "https://agent.example.com/rpc")
        self.assertEqual(skills[0]["registry_passport"]["status"], "VALID")

        normalized = normalize_request_payload({"task": "find public info", "registry_discovery_response": payload})
        self.assertEqual(normalized["source"], "registry_passport_discovery")
        self.assertEqual(normalized["skills"][0]["skill_name"], "Search")


if __name__ == "__main__":
    unittest.main()
