import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from datetime import timedelta
from uuid import uuid4

from app.common.certificate_model import Certificate, CertificateStatus, CertificateType
from app.common import beijing_now


class TestExtensionAPI:
    """测试扩展API (Trust Bundle & Revoke Notify)"""

    def test_get_trust_bundle(self, client: TestClient):
        """测试获取信任包"""
        response = client.get("/acps-atr-v2/ca/trust-bundle")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/x-pem-file"
        assert len(response.content) > 0
        assert b"BEGIN CERTIFICATE" in response.content

    def test_revoke_notify_success(self, client: TestClient, db_session: Session, internal_auth_headers):
        """测试成功的吊销通知"""
        # 1. 准备测试数据：创建一个属于特定AIC的有效证书
        aic = "1.2.156.3088.1.34C2.478BDF.3GF546.1.0156"  # 10 段点分 AIC + CRC16(含盐) 的 Base36 编码
        # 创建证书
        cert = Certificate(
            certificate_type=CertificateType.USER,
            serial_number=f"TEST{uuid4().hex[:12].upper()}",
            subject="CN=test.example.com",
            issuer="CN=Test CA",
            status=CertificateStatus.VALID,
            issued_at=beijing_now(),
            expires_at=beijing_now() + timedelta(days=365),
            certificate_pem="-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----",
            public_key="TEST_KEY",
            aic=aic,
        )
        db_session.add(cert)
        db_session.commit()
        db_session.refresh(cert)

        # 2. 发送吊销通知
        payload = {"aic": aic, "reason": 1}  # keyCompromise
        response = client.post("/acps-atr-v2/ca/revoke-notify", json=payload, headers=internal_auth_headers)

        # 3. 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["aic"] == aic
        assert data["revocationReason"] == "keyCompromise"
        assert data["revokedCertCount"] == 1

        # 4. 验证数据库状态
        db_session.refresh(cert)
        assert cert.status == CertificateStatus.REVOKED
        assert cert.revocation_reason == "keyCompromise"

    def test_revoke_notify_invalid_aic(self, client: TestClient, internal_auth_headers):
        """测试无效AIC格式（空字符串）"""
        payload = {"aic": "", "reason": 1}
        response = client.post("/acps-atr-v2/ca/revoke-notify", json=payload, headers=internal_auth_headers)
        assert response.status_code == 400
        assert "Invalid AIC format" in response.json()["detail"]

    def test_revoke_notify_invalid_reason(self, client: TestClient, internal_auth_headers):
        """测试无效吊销原因"""
        payload = {"aic": "test_aic_12345678901234567890123", "reason": 99}
        response = client.post("/acps-atr-v2/ca/revoke-notify", json=payload, headers=internal_auth_headers)
        assert response.status_code == 400
        assert "Invalid revocation reason code" in response.json()["detail"]

    def test_revoke_notify_no_certs(self, client: TestClient, internal_auth_headers):
        """测试AIC无证书的情况"""
        payload = {"aic": "empty_aic_1234567890123456789012", "reason": 1}
        response = client.post("/acps-atr-v2/ca/revoke-notify", json=payload, headers=internal_auth_headers)
        assert response.status_code == 200
        assert response.json()["revokedCertCount"] == 0


    def test_revoke_notify_requires_internal_token(self, client: TestClient):
        payload = {"aic": "empty_aic_1234567890123456789012", "reason": 1}
        response = client.post("/acps-atr-v2/ca/revoke-notify", json=payload)
        assert response.status_code == 401

    def test_revoke_notify_rejects_bad_internal_token(self, client: TestClient):
        payload = {"aic": "empty_aic_1234567890123456789012", "reason": 1}
        response = client.post(
            "/acps-atr-v2/ca/revoke-notify",
            json=payload,
            headers={"Authorization": "Bearer wrong"},
        )
        assert response.status_code == 403

    def test_passport_sync_valid_issues_agent_certificate(
        self, client: TestClient, db_session: Session, internal_auth_headers
    ):
        aic = "1234567890abcdef1234567890abcdef"
        payload = {
            "aic": aic,
            "passportStatus": "VALID",
            "mtlsRequired": True,
            "subjectComponents": {"O": "BUPT", "OU": "AI", "C": "CN"},
            "endpointUrls": ["https://agent.example.com/rpc"],
            "validityDays": 49,
        }

        response = client.post(
            "/acps-atr-v2/ca/passport-sync",
            json=payload,
            headers=internal_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["aic"] == aic
        assert data["passportStatus"] == "VALID"
        assert data["action"] == "issued"
        assert data["certificateStatus"] == "VALID"
        assert data["issuer"]
        assert data["serialNumber"]
        assert data["notBefore"]
        assert data["notAfter"]
        assert data["version"] == 1
        assert data["renewalWindowDays"] == 14
        assert data["renewalDue"] is False
        assert data["nextReviewAfter"]
        assert data["rotationAudit"][0]["action"] == "certificate_issued"
        assert data["runtimeAlerts"] == []

        certificate = db_session.exec(
            select(Certificate).where(Certificate.aic == aic)
        ).first()
        assert certificate is not None
        assert certificate.certificate_type == CertificateType.AGENT
        assert certificate.status == CertificateStatus.VALID
        assert certificate.serial_number == data["serialNumber"]
        assert "BEGIN CERTIFICATE" in certificate.certificate_pem

    def test_passport_sync_valid_keeps_fresh_certificate(
        self, client: TestClient, db_session: Session, internal_auth_headers
    ):
        aic = "fresh1234567890abcdef1234567890ab"
        cert = Certificate(
            certificate_type=CertificateType.AGENT,
            serial_number=f"FRESH{uuid4().hex[:12].upper()}",
            subject="CN=fresh.example.com",
            issuer="CN=Test CA",
            status=CertificateStatus.VALID,
            issued_at=beijing_now(),
            expires_at=beijing_now() + timedelta(days=40),
            certificate_pem="-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----",
            public_key="TEST_KEY",
            version=3,
            aic=aic,
        )
        db_session.add(cert)
        db_session.commit()
        db_session.refresh(cert)

        response = client.post(
            "/acps-atr-v2/ca/passport-sync",
            json={
                "aic": aic,
                "passportStatus": "VALID",
                "mtlsRequired": True,
                "renewalWindowDays": 14,
            },
            headers=internal_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "unchanged"
        assert data["certificateStatus"] == "VALID"
        assert data["serialNumber"] == cert.serial_number
        assert data["version"] == 3
        assert data["revokedCertCount"] == 0
        assert data["renewalDue"] is False
        assert data["daysUntilExpiry"] >= 38
        assert data["rotationAudit"][0]["action"] == "certificate_kept"
        assert data["runtimeAlerts"] == []

        db_session.refresh(cert)
        assert cert.status == CertificateStatus.VALID

    def test_passport_sync_valid_renews_expiring_certificate(
        self, client: TestClient, db_session: Session, internal_auth_headers
    ):
        aic = "renew1234567890abcdef1234567890ab"
        old_cert = Certificate(
            certificate_type=CertificateType.AGENT,
            serial_number=f"OLD{uuid4().hex[:12].upper()}",
            subject="CN=old.example.com",
            issuer="CN=Test CA",
            status=CertificateStatus.VALID,
            issued_at=beijing_now() - timedelta(days=40),
            expires_at=beijing_now() + timedelta(days=3),
            certificate_pem="-----BEGIN CERTIFICATE-----\nOLD\n-----END CERTIFICATE-----",
            public_key="OLD_KEY",
            version=1,
            aic=aic,
        )
        db_session.add(old_cert)
        db_session.commit()
        db_session.refresh(old_cert)

        response = client.post(
            "/acps-atr-v2/ca/passport-sync",
            json={
                "aic": aic,
                "passportStatus": "VALID",
                "mtlsRequired": True,
                "renewalWindowDays": 14,
                "validityDays": 49,
            },
            headers=internal_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "renewed"
        assert data["certificateStatus"] == "VALID"
        assert data["serialNumber"] != old_cert.serial_number
        assert data["revokedCertCount"] == 1
        assert data["renewalDue"] is False
        assert data["rotationAudit"][0]["action"] == "certificate_rotated"
        assert data["rotationAudit"][0]["previousSerialNumber"] == old_cert.serial_number
        assert data["runtimeAlerts"][0]["code"] == "certificate_renewal_due"

        db_session.refresh(old_cert)
        assert old_cert.status == CertificateStatus.REVOKED

        valid_certs = db_session.exec(
            select(Certificate).where(
                Certificate.aic == aic,
                Certificate.status == CertificateStatus.VALID,
            )
        ).all()
        assert len(valid_certs) == 1
        assert valid_certs[0].serial_number == data["serialNumber"]

    def test_passport_sync_draft_defers_certificate_issue(
        self, client: TestClient, db_session: Session, internal_auth_headers
    ):
        aic = "abcdef1234567890abcdef1234567890"
        response = client.post(
            "/acps-atr-v2/ca/passport-sync",
            json={"aic": aic, "passportStatus": "DRAFT", "mtlsRequired": True},
            headers=internal_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["passportStatus"] == "DRAFT"
        assert data["action"] == "deferred"
        assert data["certificateStatus"] == "NOT_ISSUED"
        assert data["serialNumber"] is None

        certificate = db_session.exec(
            select(Certificate).where(Certificate.aic == aic)
        ).first()
        assert certificate is None

    def test_passport_sync_suspended_revokes_existing_certificate(
        self, client: TestClient, db_session: Session, internal_auth_headers
    ):
        aic = "fedcba0987654321fedcba0987654321"
        cert = Certificate(
            certificate_type=CertificateType.AGENT,
            serial_number=f"TEST{uuid4().hex[:12].upper()}",
            subject="CN=test.example.com",
            issuer="CN=Test CA",
            status=CertificateStatus.VALID,
            issued_at=beijing_now(),
            expires_at=beijing_now() + timedelta(days=365),
            certificate_pem="-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----",
            public_key="TEST_KEY",
            aic=aic,
        )
        db_session.add(cert)
        db_session.commit()
        db_session.refresh(cert)

        response = client.post(
            "/acps-atr-v2/ca/passport-sync",
            json={"aic": aic, "passportStatus": "SUSPENDED", "mtlsRequired": True},
            headers=internal_auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["passportStatus"] == "SUSPENDED"
        assert data["action"] == "revoked"
        assert data["certificateStatus"] == "REVOKED"
        assert data["revokedCertCount"] == 1

        db_session.refresh(cert)
        assert cert.status == CertificateStatus.REVOKED

    def test_passport_sync_requires_internal_token(self, client: TestClient):
        response = client.post(
            "/acps-atr-v2/ca/passport-sync",
            json={"aic": "1234567890abcdef1234567890abcdef", "passportStatus": "VALID"},
        )
        assert response.status_code == 401
