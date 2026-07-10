import os
import unittest
from unittest.mock import patch

import server


class GatewayRoutingTests(unittest.TestCase):
    def test_ca_protocol_routes_precede_registry_route(self):
        for path in (
            "/acps-atr-v2/acme/directory",
            "/acps-atr-v2/ca/certificates/123",
            "/acps-atr-v2/crl/current",
            "/acps-atr-v2/ocsp/status",
        ):
            with self.subTest(path=path):
                self.assertEqual(server.proxy_for_path(path)[1], server.CA_UPSTREAM)
                self.assertTrue(server.is_ca_proxy_path(path))

    def test_registry_eab_and_agent_routes_stay_on_registry(self):
        for path in (
            "/acps-atr-v2/eab/1.2.3",
            "/acps-atr-v2/agent/search",
            "/api/agent/client",
        ):
            with self.subTest(path=path):
                self.assertEqual(server.proxy_for_path(path)[1], server.REGISTRY_UPSTREAM)
                self.assertFalse(server.is_ca_proxy_path(path))

    def test_ca_prefix_requires_path_segment_boundary(self):
        route = server.proxy_for_path("/acps-atr-v2/acme-legacy")
        self.assertEqual(route[1], server.REGISTRY_UPSTREAM)
        self.assertFalse(server.is_ca_proxy_path("/acps-atr-v2/acme-legacy"))

    def test_legacy_routes_keep_existing_strip_behavior(self):
        self.assertTrue(server.proxy_for_path("/acps-atr-v1/agent/search")[2])
        self.assertTrue(server.proxy_for_path("/mode-router/health")[2])
        self.assertFalse(server.proxy_for_path("/acps-atr-v2/eab/aic")[2])


class GatewayConfigTests(unittest.TestCase):
    def test_stage4_frontend_features_default_off(self):
        with patch.dict(os.environ, {}, clear=True):
            config = server.frontend_config()
        self.assertFalse(config["acpsV21FrontendEnabled"])
        self.assertFalse(config["eabIssuanceEnabled"])
        self.assertEqual(config["caDirectoryUrl"], "/acps-atr-v2/acme/directory")

    def test_stage4_frontend_features_can_be_enabled_independently(self):
        values = {
            "ACPS_FRONTEND_V21_ENABLED": "true",
            "ACPS_FRONTEND_EAB_ENABLED": "1",
        }
        with patch.dict(os.environ, values, clear=True):
            config = server.frontend_config()
        self.assertTrue(config["acpsV21FrontendEnabled"])
        self.assertTrue(config["eabIssuanceEnabled"])


class GatewayRewriteTests(unittest.TestCase):
    def test_external_origin_prefers_forwarded_headers(self):
        headers = {
            "Host": "internal:8888",
            "X-Forwarded-Host": "renta.example.com",
            "X-Forwarded-Proto": "https",
        }
        self.assertEqual(server.external_origin(headers), "https://renta.example.com")

    def test_ca_json_urls_are_rewritten_to_gateway_origin(self):
        body = (
            b'{"newAccount":"http://localhost:8003/acps-atr-v2/acme/new-account",'
            b'"newOrder":"http://127.0.0.1:8003/acps-atr-v2/acme/new-order"}'
        )
        rewritten = server.rewrite_ca_body(body, "application/json", "https://renta.example.com")
        text = rewritten.decode("utf-8")
        self.assertNotIn("localhost:8003", text)
        self.assertNotIn("127.0.0.1:8003", text)
        self.assertEqual(text.count("https://renta.example.com/acps-atr-v2/acme/"), 2)

    def test_non_json_ca_payload_is_not_modified(self):
        body = b"certificate http://localhost:8003 data"
        self.assertIs(server.rewrite_ca_body(body, "application/pem-certificate-chain", "https://public"), body)


if __name__ == "__main__":
    unittest.main()
