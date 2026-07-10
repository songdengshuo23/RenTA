"""
证书管理服务层
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlmodel import Session

from app.common import (
    CertificateService,
    Certificate,
    CertificateType,
    CertificateStatus,
    beijing_now,
)


class CertificateManagementService(CertificateService):
    """证书管理扩展服务"""

    def __init__(self, db: Session):
        super().__init__(db)

    def create_root_certificate(
        self, subject_name: str, validity_days: int = 3650
    ) -> Certificate:
        """
        创建根证书

        Args:
            subject_name: 证书主体名称
            validity_days: 有效期天数，默认10年

        Returns:
            Certificate: 创建的根证书
        """
        cert_pem, private_key_pem = self.generate_certificate_pair(
            subject_name=subject_name,
            certificate_type=CertificateType.ROOT,
            validity_days=validity_days,
        )

        certificate_data = {
            "certificate_type": CertificateType.ROOT,
            "subject": subject_name,
            "issuer": subject_name,  # 根证书是自签名的
            "status": CertificateStatus.VALID,
            "certificate_pem": cert_pem,
            "public_key": self._extract_public_key_from_cert(cert_pem),
            "expires_at": self._calculate_expiry_date(validity_days),
        }

        return self.create_certificate(certificate_data)

    def create_intermediate_certificate(
        self, subject_name: str, parent_certificate_id: UUID, validity_days: int = 1825
    ) -> Optional[Certificate]:
        """
        创建中间证书

        Args:
            subject_name: 证书主体名称
            parent_certificate_id: 父证书ID
            validity_days: 有效期天数，默认5年

        Returns:
            Optional[Certificate]: 创建的中间证书或None
        """
        parent_certificate = self.get_certificate_by_id(parent_certificate_id)
        if (
            not parent_certificate
            or parent_certificate.status != CertificateStatus.VALID
        ):
            return None

        cert_pem, private_key_pem = self.generate_certificate_pair(
            subject_name=subject_name,
            certificate_type=CertificateType.INTERMEDIATE,
            validity_days=validity_days,
            parent_certificate=parent_certificate,
        )

        certificate_data = {
            "certificate_type": CertificateType.INTERMEDIATE,
            "subject": subject_name,
            "issuer": parent_certificate.subject,
            "status": CertificateStatus.VALID,
            "certificate_pem": cert_pem,
            "public_key": self._extract_public_key_from_cert(cert_pem),
            "parent_certificate_id": parent_certificate_id,
            "expires_at": self._calculate_expiry_date(validity_days),
        }

        return self.create_certificate(certificate_data)

    def renew_certificate(
        self, certificate_id: UUID, validity_days: Optional[int] = None
    ) -> Optional[Certificate]:
        """
        续期证书

        Args:
            certificate_id: 证书ID
            validity_days: 新的有效期天数，如果不指定则使用默认值

        Returns:
            Optional[Certificate]: 新的证书或None
        """
        old_certificate = self.get_certificate_by_id(certificate_id)
        if not old_certificate:
            return None

        # 确定续期天数
        if validity_days is None:
            if old_certificate.certificate_type == CertificateType.ROOT:
                validity_days = 3650  # 10年
            elif old_certificate.certificate_type == CertificateType.INTERMEDIATE:
                validity_days = 1825  # 5年
            else:
                validity_days = 365  # 1年

        # 生成新证书
        cert_pem, private_key_pem = self.generate_certificate_pair(
            subject_name=old_certificate.subject,
            certificate_type=old_certificate.certificate_type,
            validity_days=validity_days,
            parent_certificate=(
                self.get_certificate_by_id(old_certificate.parent_certificate_id)
                if old_certificate.parent_certificate_id
                else None
            ),
            aic=old_certificate.aic,
        )

        # 创建新证书
        certificate_data = {
            "certificate_type": old_certificate.certificate_type,
            "subject": old_certificate.subject,
            "issuer": old_certificate.issuer,
            "status": CertificateStatus.VALID,
            "certificate_pem": cert_pem,
            "public_key": self._extract_public_key_from_cert(cert_pem),
            "parent_certificate_id": old_certificate.parent_certificate_id,
            "aic": old_certificate.aic,
            "expires_at": self._calculate_expiry_date(validity_days),
        }

        new_certificate = self.create_certificate(certificate_data)

        # 吊销旧证书
        self.revoke_certificate(certificate_id, "续期替换")

        return new_certificate

    def get_certificate_chain(self, certificate_id: UUID) -> List[Certificate]:
        """
        获取证书链

        Args:
            certificate_id: 证书ID

        Returns:
            List[Certificate]: 证书链，从用户证书到根证书
        """
        chain = []
        current_cert = self.get_certificate_by_id(certificate_id)

        while current_cert:
            chain.append(current_cert)
            if current_cert.parent_certificate_id:
                current_cert = self.get_certificate_by_id(
                    current_cert.parent_certificate_id
                )
            else:
                break

        return chain

    def _extract_public_key_from_cert(self, cert_pem: str) -> str:
        """
        从证书PEM中提取公钥

        Args:
            cert_pem: 证书PEM格式字符串

        Returns:
            str: 公钥PEM格式字符串
        """
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization

        cert = x509.load_pem_x509_certificate(cert_pem.encode())
        public_key = cert.public_key()

        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        return public_key_pem

    def _calculate_expiry_date(self, validity_days: int):
        """
        计算过期日期

        Args:
            validity_days: 有效期天数

        Returns:
            datetime: 过期日期
        """
        from datetime import timedelta
        from app.common import beijing_now

        return beijing_now() + timedelta(days=validity_days)

    def get_latest_certificate_by_aic(self, aic: str) -> Optional[Certificate]:
        """Return the latest certificate row for the given AIC."""
        from sqlmodel import select

        statement = (
            select(Certificate)
            .where(Certificate.aic == aic)
            .order_by(Certificate.created_at.desc())
        )
        return self.db.exec(statement).first()

    def get_latest_valid_certificate_by_aic(self, aic: str) -> Optional[Certificate]:
        """Return the newest currently valid certificate for the given AIC."""
        from sqlmodel import select

        statement = (
            select(Certificate)
            .where(Certificate.aic == aic, Certificate.status == CertificateStatus.VALID)
            .order_by(Certificate.created_at.desc())
        )
        return self.db.exec(statement).first()

    def _days_until_expiry(self, certificate: Optional[Certificate]) -> Optional[int]:
        """Return whole days until expiry; negative means already expired."""
        if not certificate or not certificate.expires_at:
            return None
        expires_at = certificate.expires_at
        now = beijing_now()
        if expires_at.tzinfo is None and now.tzinfo is not None:
            expires_at = expires_at.replace(tzinfo=now.tzinfo)
        delta = expires_at - now
        return int(delta.total_seconds() // 86400)

    def _certificate_needs_renewal(
        self, certificate: Optional[Certificate], renewal_window_days: int
    ) -> bool:
        days_until_expiry = self._days_until_expiry(certificate)
        if days_until_expiry is None:
            return True
        return days_until_expiry <= renewal_window_days

    def _next_review_after(
        self, certificate: Optional[Certificate], renewal_window_days: int
    ) -> Optional[datetime]:
        if not certificate or not certificate.expires_at:
            return None
        return certificate.expires_at - timedelta(days=renewal_window_days)

    def _rotation_audit_event(
        self,
        *,
        action: str,
        reason: str,
        previous_certificate: Optional[Certificate] = None,
        new_certificate: Optional[Certificate] = None,
    ) -> Dict[str, Any]:
        return {
            "action": action,
            "reason": reason,
            "previousSerialNumber": (
                previous_certificate.serial_number if previous_certificate else None
            ),
            "newSerialNumber": new_certificate.serial_number if new_certificate else None,
            "previousVersion": previous_certificate.version if previous_certificate else None,
            "newVersion": new_certificate.version if new_certificate else None,
            "auditedAt": beijing_now().isoformat(),
        }

    def _certificate_runtime_alerts(
        self,
        *,
        aic: str,
        passport_status: str,
        certificate: Optional[Certificate],
        renewal_window_days: int,
    ) -> List[Dict[str, Any]]:
        days_until_expiry = self._days_until_expiry(certificate)
        if days_until_expiry is None:
            return []
        if days_until_expiry < 0:
            return [
                {
                    "code": "certificate_expired",
                    "severity": "HIGH",
                    "aic": aic,
                    "passportStatus": passport_status,
                    "daysUntilExpiry": days_until_expiry,
                    "message": "Agent certificate is already expired and must be rotated.",
                }
            ]
        if days_until_expiry <= renewal_window_days:
            return [
                {
                    "code": "certificate_renewal_due",
                    "severity": "MEDIUM",
                    "aic": aic,
                    "passportStatus": passport_status,
                    "daysUntilExpiry": days_until_expiry,
                    "renewalWindowDays": renewal_window_days,
                    "message": "Agent certificate is inside the renewal window.",
                }
            ]
        return []

    def issue_agent_certificate(
        self,
        aic: str,
        subject_components: Optional[Dict[str, str]] = None,
        endpoint_urls: Optional[List[str]] = None,
        validity_days: int = 49,
    ) -> Certificate:
        """Issue a real CA-signed agent certificate and persist its metadata."""
        from datetime import timezone

        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        from app.common.certificate_version import get_next_certificate_version
        from app.core.ca_manager import get_ca_manager

        ca_manager = get_ca_manager()
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        csr = (
            x509.CertificateSigningRequestBuilder()
            .subject_name(
                x509.Name(
                    [
                        x509.NameAttribute(
                            NameOID.COMMON_NAME,
                            ca_manager.settings.build_agent_common_name(aic),
                        )
                    ]
                )
            )
            .sign(private_key, hashes.SHA256())
        )

        cert_pem = ca_manager.sign_certificate(
            csr=csr,
            agent_ids=[aic],
            validity_days=validity_days,
            subject_components=subject_components or None,
            agent_endpoints=endpoint_urls or None,
        )
        cert_obj = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
        public_key_pem = cert_obj.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        timezone_info = beijing_now().tzinfo
        not_before = getattr(cert_obj, "not_valid_before_utc", None)
        not_after = getattr(cert_obj, "not_valid_after_utc", None)
        if not_before is None:
            not_before = cert_obj.not_valid_before.replace(tzinfo=timezone.utc)
        if not_after is None:
            not_after = cert_obj.not_valid_after.replace(tzinfo=timezone.utc)

        certificate = Certificate(
            certificate_type=CertificateType.AGENT,
            serial_number=format(cert_obj.serial_number, "X"),
            subject=cert_obj.subject.rfc4514_string(),
            issuer=cert_obj.issuer.rfc4514_string(),
            status=CertificateStatus.VALID,
            issued_at=not_before.astimezone(timezone_info),
            expires_at=not_after.astimezone(timezone_info),
            certificate_pem=cert_pem,
            public_key=public_key_pem,
            version=get_next_certificate_version(self.db, aic),
            aic=aic,
        )
        self.db.add(certificate)
        self.db.commit()
        self.db.refresh(certificate)
        return certificate

    def _certificate_sync_payload(
        self,
        *,
        aic: str,
        passport_status: str,
        action: str,
        mtls_required: bool,
        certificate: Optional[Certificate] = None,
        certificate_status: Optional[str] = None,
        revoked_cert_count: int = 0,
        revocation_reason: Optional[str] = None,
        renewal_window_days: int = 14,
        renewal_due: Optional[bool] = None,
        rotation_audit: Optional[List[Dict[str, Any]]] = None,
        runtime_alerts: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Normalize certificate sync results for the API layer."""
        status_value = certificate_status
        if not status_value and certificate is not None:
            status_value = certificate.status.value.upper()
        if not status_value:
            status_value = "NOT_ISSUED"

        reason_value = revocation_reason
        if not reason_value and certificate is not None and certificate.revocation_reason:
            reason = certificate.revocation_reason
            reason_value = getattr(reason, "value", str(reason))

        days_until_expiry = self._days_until_expiry(certificate)
        if renewal_due is None:
            renewal_due = (
                days_until_expiry is not None
                and days_until_expiry <= renewal_window_days
            )

        return {
            "aic": aic,
            "passport_status": passport_status,
            "action": action,
            "certificate_status": status_value,
            "issuer": certificate.issuer if certificate else None,
            "serial_number": certificate.serial_number if certificate else None,
            "not_before": certificate.issued_at if certificate else None,
            "not_after": certificate.expires_at if certificate else None,
            "version": certificate.version if certificate else None,
            "revoked_cert_count": revoked_cert_count,
            "revocation_reason": reason_value,
            "mtls_required": mtls_required,
            "renewal_window_days": renewal_window_days,
            "days_until_expiry": days_until_expiry,
            "renewal_due": renewal_due,
            "next_review_after": self._next_review_after(
                certificate, renewal_window_days
            ),
            "rotation_audit": rotation_audit or [],
            "runtime_alerts": runtime_alerts or [],
        }

    def sync_passport_certificate(
        self,
        *,
        aic: str,
        passport_status: str,
        mtls_required: bool = True,
        subject_components: Optional[Dict[str, str]] = None,
        endpoint_urls: Optional[List[str]] = None,
        validity_days: int = 49,
        renewal_window_days: int = 14,
    ) -> Dict[str, Any]:
        """Drive certificate lifecycle from the Registry Passport status."""
        normalized_status = (passport_status or "").upper()
        if not aic:
            raise ValueError("AIC is required for passport certificate sync")

        if not mtls_required:
            return self._certificate_sync_payload(
                aic=aic,
                passport_status=normalized_status,
                action="skipped",
                mtls_required=False,
                certificate_status="NOT_REQUIRED",
                renewal_window_days=renewal_window_days,
                renewal_due=False,
            )

        if normalized_status == "VALID":
            existing_certificate = self.get_latest_valid_certificate_by_aic(aic)
            if existing_certificate and not self._certificate_needs_renewal(
                existing_certificate, renewal_window_days
            ):
                return self._certificate_sync_payload(
                    aic=aic,
                    passport_status=normalized_status,
                    action="unchanged",
                    mtls_required=True,
                    certificate=existing_certificate,
                    renewal_window_days=renewal_window_days,
                    renewal_due=False,
                    rotation_audit=[
                        self._rotation_audit_event(
                            action="certificate_kept",
                            reason="outside_renewal_window",
                            previous_certificate=existing_certificate,
                        )
                    ],
                    runtime_alerts=[],
                )

            runtime_alerts = self._certificate_runtime_alerts(
                aic=aic,
                passport_status=normalized_status,
                certificate=existing_certificate,
                renewal_window_days=renewal_window_days,
            )
            resolved_runtime_alerts = [
                {
                    **alert,
                    "resolved": True,
                    "resolvedBy": "certificate_rotation",
                }
                for alert in runtime_alerts
            ]
            revoked_count = self.revoke_certificates_by_aic(aic, "superseded")
            certificate = self.issue_agent_certificate(
                aic=aic,
                subject_components=subject_components,
                endpoint_urls=endpoint_urls,
                validity_days=validity_days,
            )
            action = "issued"
            reason = "no_existing_certificate"
            if existing_certificate:
                action = "renewed"
                days_until_expiry = self._days_until_expiry(existing_certificate)
                reason = (
                    "certificate_expired"
                    if days_until_expiry is not None and days_until_expiry < 0
                    else "inside_renewal_window"
                )
            return self._certificate_sync_payload(
                aic=aic,
                passport_status=normalized_status,
                action=action,
                mtls_required=True,
                certificate=certificate,
                revoked_cert_count=revoked_count,
                renewal_window_days=renewal_window_days,
                renewal_due=False,
                rotation_audit=[
                    self._rotation_audit_event(
                        action=(
                            "certificate_rotated"
                            if existing_certificate
                            else "certificate_issued"
                        ),
                        reason=reason,
                        previous_certificate=existing_certificate,
                        new_certificate=certificate,
                    )
                ],
                runtime_alerts=resolved_runtime_alerts,
            )

        if normalized_status == "SUSPENDED":
            revoked_count = self.revoke_certificates_by_aic(aic, "unspecified")
            latest_certificate = self.get_latest_certificate_by_aic(aic)
            return self._certificate_sync_payload(
                aic=aic,
                passport_status=normalized_status,
                action="revoked" if revoked_count else "noop",
                mtls_required=True,
                certificate=latest_certificate,
                certificate_status=(
                    "REVOKED"
                    if latest_certificate and latest_certificate.status == CertificateStatus.REVOKED
                    else None
                ),
                revoked_cert_count=revoked_count,
                revocation_reason="unspecified" if revoked_count else None,
                renewal_window_days=renewal_window_days,
                renewal_due=False,
                rotation_audit=[
                    self._rotation_audit_event(
                        action="certificate_revoked",
                        reason="passport_suspended",
                        previous_certificate=latest_certificate,
                    )
                ]
                if revoked_count
                else [],
                runtime_alerts=[
                    {
                        "code": "passport_suspended_certificate_revoked",
                        "severity": "HIGH",
                        "aic": aic,
                        "passportStatus": normalized_status,
                        "message": "Passport is suspended; active certificate was revoked.",
                    }
                ]
                if revoked_count
                else [],
            )

        if normalized_status == "DRAFT":
            return self._certificate_sync_payload(
                aic=aic,
                passport_status=normalized_status,
                action="deferred",
                mtls_required=True,
                certificate_status="NOT_ISSUED",
                renewal_window_days=renewal_window_days,
                renewal_due=False,
                runtime_alerts=[
                    {
                        "code": "passport_draft_certificate_deferred",
                        "severity": "LOW",
                        "aic": aic,
                        "passportStatus": normalized_status,
                        "message": "Passport is still draft; certificate issuance is deferred.",
                    }
                ],
            )

        raise ValueError(f"Unsupported passport status: {passport_status}")

    def revoke_certificates_by_aic(self, aic: str, reason: str) -> int:
        """
        根据 AIC 批量吊销证书

        根据 ATR-DESIGN 规范，查找指定 AIC 的所有状态为 "pending" 或 "valid" 的证书并吊销。

        Args:
            aic: Agent Identity Code
            reason: 吊销原因

        Returns:
            int: 成功吊销的证书数量
        """
        from sqlmodel import select
        from app.common import Certificate, CertificateStatus

        # 查找所有与该 AIC 相关的有效证书
        # 直接使用 aic 字段进行查询
        statement = select(Certificate).where(
            Certificate.aic == aic,
            Certificate.status.in_(
                [CertificateStatus.PENDING, CertificateStatus.VALID]
            ),
        )

        certificates = self.db.exec(statement).all()

        revoked_count = 0
        for cert in certificates:
            try:
                # 调用父类的吊销方法
                if self.revoke_certificate(cert.id, reason):
                    revoked_count += 1
            except Exception as e:
                # 记录错误但继续处理其他证书
                print(f"Failed to revoke certificate {cert.id}: {e} - services.py:252")
                continue

        return revoked_count
    
    def retrieve_certificate_by_aic_and_version(
        self, aic: str, version: Optional[int]
    ) -> Certificate:
        """
        根据 AIC 和版本号检索证书

        Args:
            aic: Agent Identity Code
            version: 版本号，如果为 None 则检索最新有效证书

        Returns:
            str: 证书内容（PEM 格式）

        Raises:
            ValueError: 如果未找到符合条件的证书
        """
        from sqlmodel import select
        from app.common import Certificate, CertificateStatus

        statement = select(Certificate).where(
            Certificate.aic == aic,
        )

        if version:
            statement = statement.where(Certificate.version == version)
        else:
            statement = statement.where(Certificate.status == CertificateStatus.VALID)

        statement = statement.order_by(Certificate.created_at.desc())

        certificate = self.db.exec(statement).first()

        if not certificate:
            raise ValueError("Certificate not found for the given AIC and version")

        return certificate
    
    def retrieve_certificate_by_cert(self, cert_pem: str)  -> Certificate:
        """
        从证书PEM中提取AIC

        Args:
            cert_pem: 证书PEM格式字符串

        Returns:
            Certificate: 证书对象
        """
        from sqlmodel import select
        from app.common import Certificate, CertificateStatus
        from sqlalchemy import func
        from urllib.parse import unquote
        
        try:
            # cert_pem 可能来自 URL query（出现 %0A、%20 等），先做一次 URL 解码。
            # 注意：不要用 unquote_plus，避免把 PEM/base64 里的 '+' 误当空格。
            cert_pem = unquote(cert_pem or "")

            # 1) 快路径：精确匹配（最快）
            statement = select(Certificate).where(Certificate.certificate_pem == cert_pem)
            certificate = self.db.exec(statement).first()
            if certificate:
                return certificate

            # 2) 兼容：入参可能把换行替换成空格/混用 \r\n，忽略所有空白后再匹配。
            normalized_input = "".join(cert_pem.split())
            statement = select(Certificate).where(
                func.regexp_replace(
                    Certificate.certificate_pem,
                    r"\\s+",
                    "",
                    "g",
                )
                == normalized_input
            )
            certificate = self.db.exec(statement).first()
            if certificate:
                return certificate

            # 3) 回退：在不支持 regexp_replace 的数据库上（例如 SQLite），用 Python 做归一化匹配。
            # 数据量很大时不建议使用该路径。
            candidates = self.db.exec(select(Certificate)).all()
            for item in candidates:
                if "".join((item.certificate_pem or "").split()) == normalized_input:
                    return item

            raise ValueError("Certificate not found for the given cert_pem")
        except Exception as e:
            print(f"Error retrieving certificate by cert: {e} - services.py:344")
            raise ValueError(f"Error retrieving certificate by cert: {e}")

