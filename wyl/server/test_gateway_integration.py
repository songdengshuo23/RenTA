import http.client
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import server


class FakeUpstreamHandler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def _record(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        self.server.requests.append((self.command, self.path, self.headers.get("Host"), body))

    def do_POST(self):
        self._record()
        if self.server.role == "registry":
            payload = {
                "keyId": "stage4-key-id",
                "macKey": "stage4-one-time-mac-key",
                "aic": "1.2.156.3088.stage4",
                "expiresAt": "2026-07-10T18:00:00+08:00",
            }
            data = json.dumps(payload).encode("utf-8")
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        data = b'{"status":"pending"}'
        self.send_response(201)
        self.send_header("Content-Type", "application/json")
        self.send_header("Location", self.server.internal_origin + "/acps-atr-v2/acme/order/123")
        self.send_header("Replay-Nonce", "stage4-nonce")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._record()
        data = json.dumps({
            "newNonce": self.server.internal_origin + "/acps-atr-v2/acme/new-nonce",
            "newAccount": self.server.internal_origin + "/acps-atr-v2/acme/new-account",
            "newOrder": self.server.internal_origin + "/acps-atr-v2/acme/new-order",
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Replay-Nonce", "stage4-directory-nonce")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def start_server(role):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeUpstreamHandler)
    httpd.role = role
    httpd.requests = []
    httpd.internal_origin = f"http://127.0.0.1:{httpd.server_port}"
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread


class GatewayIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.registry, self.registry_thread = start_server("registry")
        self.ca, self.ca_thread = start_server("ca")
        self.original_registry = server.REGISTRY_UPSTREAM
        self.original_ca = server.CA_UPSTREAM
        self.original_proxies = server.PROXIES
        server.REGISTRY_UPSTREAM = self.registry.internal_origin + "/"
        server.CA_UPSTREAM = self.ca.internal_origin + "/"
        server.PROXIES = server.build_proxies(server.REGISTRY_UPSTREAM, server.CA_UPSTREAM)

        self.gateway = ThreadingHTTPServer(("127.0.0.1", 0), server.SPAProxyHandler)
        self.gateway_thread = threading.Thread(target=self.gateway.serve_forever, daemon=True)
        self.gateway_thread.start()

    def tearDown(self):
        self.gateway.shutdown()
        self.registry.shutdown()
        self.ca.shutdown()
        self.gateway.server_close()
        self.registry.server_close()
        self.ca.server_close()
        self.gateway_thread.join(timeout=2)
        self.registry_thread.join(timeout=2)
        self.ca_thread.join(timeout=2)
        server.REGISTRY_UPSTREAM = self.original_registry
        server.CA_UPSTREAM = self.original_ca
        server.PROXIES = self.original_proxies

    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.gateway.server_port, timeout=3)
        headers = {"Host": "renta.example.test:8888"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = response.read()
        headers = dict(response.getheaders())
        connection.close()
        return response.status, headers, data

    def test_eab_stays_on_registry(self):
        status, _headers, data = self.request("POST", "/acps-atr-v2/eab/1.2.156.3088.stage4")
        self.assertEqual(status, 201)
        self.assertEqual(json.loads(data)["keyId"], "stage4-key-id")
        self.assertEqual(len(self.registry.requests), 1)
        self.assertEqual(len(self.ca.requests), 0)

    def test_ca_directory_urls_and_host_are_gateway_visible(self):
        status, headers, data = self.request("GET", "/acps-atr-v2/acme/directory")
        self.assertEqual(status, 200)
        directory = json.loads(data)
        for value in directory.values():
            self.assertTrue(value.startswith("http://renta.example.test:8888/acps-atr-v2/acme/"))
        self.assertEqual(headers["Replay-Nonce"], "stage4-directory-nonce")
        self.assertEqual(self.ca.requests[0][2], "renta.example.test:8888")
        self.assertEqual(len(self.registry.requests), 0)

    def test_ca_location_and_nonce_headers_are_preserved(self):
        status, headers, _data = self.request("POST", "/acps-atr-v2/acme/new-order", body=b"{}")
        self.assertEqual(status, 201)
        self.assertEqual(headers["Location"], "http://renta.example.test:8888/acps-atr-v2/acme/order/123")
        self.assertEqual(headers["Replay-Nonce"], "stage4-nonce")


if __name__ == "__main__":
    unittest.main()
