import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from route_classifier import ROUTE_AGENT, ROUTE_LLM, ROUTE_MULTI_AGENT, classify_task_route


NO_LLM_ENV = {
    "ROUTER_LLM_URL": "",
    "ROUTER_LLM_API_KEY": "",
    "LLM_API_URL": "",
    "LLM_API_KEY": "",
    "DEEPSEEK_API_KEY": "",
}


class RouteClassifierTests(unittest.TestCase):
    def test_llm_route_for_direct_reasoning_task(self):
        with patch.dict("route_classifier.os.environ", NO_LLM_ENV):
            result = classify_task_route("解释一下什么是递归，并给一个简单例子。")
        self.assertEqual(result.label, ROUTE_LLM)
        self.assertEqual(result.mode, "mode_0")
        self.assertFalse(result.llm_used)

    def test_agent_route_for_tool_using_single_role_task(self):
        with patch.dict("route_classifier.os.environ", NO_LLM_ENV):
            result = classify_task_route("联网搜索最新的行业新闻并整理成摘要。")
        self.assertEqual(result.label, ROUTE_AGENT)
        self.assertEqual(result.mode, "mode_1")

    def test_multi_agent_route_for_cross_role_task(self):
        with patch.dict("route_classifier.os.environ", NO_LLM_ENV):
            result = classify_task_route("设计一个系统架构，需要后端、前端、运维和安全审查分工协作。")
        self.assertEqual(result.label, ROUTE_MULTI_AGENT)
        self.assertEqual(result.mode, "mode_2")

    def test_multi_agent_route_for_english_ops_task(self):
        with patch.dict("route_classifier.os.environ", NO_LLM_ENV):
            result = classify_task_route(
                "Use multiple specialist agents to audit backend services, registry discovery, message queue, and produce an operations report."
            )
        self.assertEqual(result.label, ROUTE_MULTI_AGENT)
        self.assertEqual(result.mode, "mode_2")

    def test_route_scores_override(self):
        result = classify_task_route(
            "任意任务",
            payload={"route_scores": {"LLM": 0.1, "Agent": 0.2, "多Agent": 0.9}},
        )
        self.assertEqual(result.label, ROUTE_MULTI_AGENT)
        self.assertEqual(result.model, "override")

    def test_llm_request_uses_default_prompt_document_with_question_placeholder(self):
        captured: dict[str, object] = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"LLM": 0.05, "Agent": 0.92, "多Agent": 0.2}'
                                }
                            }
                        ]
                    },
                    ensure_ascii=False,
                ).encode("utf-8")

        def fake_urlopen(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        with patch("route_classifier.urllib.request.urlopen", side_effect=fake_urlopen):
            result = classify_task_route(
                "读取一个文件并生成摘要。",
                payload={"route_llm_url": "http://llm.example", "route_llm_api_key": "token"},
            )

        prompt = captured["body"]["messages"][0]["content"]
        self.assertIn("## 任务\n读取一个文件并生成摘要。", prompt)
        self.assertNotIn("{question}", prompt)
        self.assertTrue(result.prompt_source.endswith("路由prompt.md"))
        self.assertTrue(result.llm_used)
        self.assertEqual(result.label, ROUTE_AGENT)
        self.assertEqual(result.mode, "mode_1")


if __name__ == "__main__":
    unittest.main()
