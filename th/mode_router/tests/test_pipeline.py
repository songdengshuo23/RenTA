\
import json
import sys
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service import create_server


class FakeDiscoveryHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_POST(self):
        body = {
            "result": {
                "acsMap": {
                    "agent-market": {"name": "??Agent"},
                    "agent-legal": {"name": "??Agent"}
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
        data = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.discovery_server = ThreadingHTTPServer(("127.0.0.1", 0), FakeDiscoveryHandler)
        cls.discovery_port = cls.discovery_server.server_address[1]
        cls.discovery_thread = threading.Thread(target=cls.discovery_server.serve_forever, daemon=True)
        cls.discovery_thread.start()

        cls.mode_router = create_server("127.0.0.1", 0)
        cls.mode_router_port = cls.mode_router.server_address[1]
        cls.mode_router_thread = threading.Thread(target=cls.mode_router.serve_forever, daemon=True)
        cls.mode_router_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.discovery_server.shutdown()
        cls.discovery_server.server_close()
        cls.discovery_thread.join(timeout=2)
        cls.mode_router.shutdown()
        cls.mode_router.server_close()
        cls.mode_router_thread.join(timeout=2)

    def test_pipeline_discovery_endpoint(self):
        payload = {
            "task": "?????????",
            "discovery_url": f"http://127.0.0.1:{self.discovery_port}/acps-adp-v2/discover",
            "limit": 2,
            "hints": {
                "estimated_skill_count": 2,
                "requires_independent_roles": True
            }
        }
        request = Request(
            f"http://127.0.0.1:{self.mode_router_port}/pipeline/discovery",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urlopen(request) as response:
            body = json.loads(response.read().decode("utf-8"))
        self.assertEqual(body["source"], "discovery_pipeline")
        self.assertEqual(body["decision"]["mode"], "mode_2")
        self.assertIn("zh", body)
        self.assertIn("plan", body)


if __name__ == "__main__":
    unittest.main()
