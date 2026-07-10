import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mq_v21_runtime import MQV21Settings, partner_tls_paths


class MQV21SettingsTests(unittest.TestCase):
    def test_defaults_keep_mq_inbox_disabled_and_fallback_enabled(self):
        with patch.dict(os.environ, {}, clear=False):
            for key in ("ACPS_MQ_INBOX_ENABLED", "ACPS_MQ_LEGACY_FALLBACK_ENABLED"):
                os.environ.pop(key, None)
            settings = MQV21Settings.from_payload({})
        self.assertFalse(settings.enabled)
        self.assertTrue(settings.fallback_enabled)
        self.assertEqual(settings.leader_aic, "1.2.156.3088.1.1.34C2.478BDF.3GF546.0JU4")
        self.assertEqual(settings.port, 5671)
        self.assertEqual(settings.vhost, "acps")

    def test_payload_override_builds_valid_stage6_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cert = Path(tmpdir) / "leader.pem"
            key = Path(tmpdir) / "leader.key"
            ca = Path(tmpdir) / "ca.pem"
            for path in (cert, key, ca):
                path.touch()
            settings = MQV21Settings.from_payload(
                {
                    "mq_inbox": {
                        "enabled": True,
                        "host": "mq.internal",
                        "port": 5671,
                        "vhost": "acps",
                        "authServiceUrl": "https://mq-auth.internal:9007/",
                        "certFile": str(cert),
                        "keyFile": str(key),
                        "caFile": str(ca),
                        "invitationTimeoutSeconds": 8,
                    }
                }
            )
            settings.validate()
        self.assertEqual(settings.host, "mq.internal")
        self.assertEqual(settings.auth_service_url, "https://mq-auth.internal:9007")
        self.assertEqual(settings.invitation_timeout_seconds, 8)

    def test_rejects_non_v21_port_or_vhost(self):
        for config, message in (
            ({"enabled": True, "port": 5672}, "port 5671"),
            ({"enabled": True, "vhost": "/"}, "shared 'acps' vhost"),
        ):
            with self.subTest(config=config):
                with self.assertRaisesRegex(ValueError, message):
                    MQV21Settings.from_payload({"mq_inbox": config}).validate()

    def test_partner_certificate_names_are_aic_scoped(self):
        cert, key = partner_tls_paths("/run/renta-mq", "1.2.156.3088.1.1.A.B.1.0000")
        self.assertTrue(cert.endswith("1.2.156.3088.1.1.A.B.1.0000.pem"))
        self.assertTrue(key.endswith("1.2.156.3088.1.1.A.B.1.0000.key"))


if __name__ == "__main__":
    unittest.main()
