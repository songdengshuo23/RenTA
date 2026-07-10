#!/usr/bin/env python3
"""Exercise EAB storage and one-time consumption against an isolated database."""

from __future__ import annotations

import concurrent.futures
import os
import threading
import uuid
from datetime import timedelta

from sqlalchemy.engine import make_url


def _guard_isolated_database() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    database = make_url(database_url).database if database_url else None
    if not database or database == "registry_db":
        raise RuntimeError("stage2 EAB probe refuses to run against registry_db")


_guard_isolated_database()

from app.account.model import User
from app.agent.model import Agent, ApprovalStatus
from app.core.db_session import SessionLocal
from app.eab.exception import EabException
from app.eab.model import EabCredential
from app.eab.service import consume_eab_credential, generate_eab_credential
from app.utils.aic import AIC_SPEC_V0201, generate_aic
from app.utils.utils import get_beijing_time


def main() -> None:
    with SessionLocal() as db:
        owner = db.query(User).first()
        if owner is None:
            raise RuntimeError("isolated database has no account_user fixture")
        agent_aic = generate_aic(spec_version=AIC_SPEC_V0201)
        agent = Agent(
            aic=agent_aic,
            name=f"Stage2 EAB Probe {uuid.uuid4().hex[:8]}",
            version="1.0.0",
            acs={"protocolVersion": "02.01"},
            created_by_id=owner.id,
            approval_status=ApprovalStatus.APPROVED,
            is_active=True,
        )
        db.add(agent)
        db.commit()
        owner_id = owner.id

    with SessionLocal() as db:
        issued = generate_eab_credential(db, owner_id, agent_aic)
        stored = (
            db.query(EabCredential)
            .filter(EabCredential.key_id == issued.key_id)
            .one()
        )
        assert stored.mac_key_encrypted != issued.mac_key
        assert issued.mac_key not in stored.mac_key_encrypted

    barrier = threading.Barrier(2)

    def consume_once() -> str:
        with SessionLocal() as db:
            barrier.wait()
            try:
                result = consume_eab_credential(db, issued.key_id)
                assert result.mac_key == issued.mac_key
                return "OK"
            except EabException as exc:
                return exc.error_name

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(pool.map(lambda _: consume_once(), range(2)))
    assert results == ["EAB_ALREADY_CONSUMED", "OK"], results

    with SessionLocal() as db:
        expired = generate_eab_credential(db, owner_id, agent_aic)
        row = (
            db.query(EabCredential)
            .filter(EabCredential.key_id == expired.key_id)
            .one()
        )
        row.expires_at = get_beijing_time() - timedelta(seconds=1)
        db.add(row)
        db.commit()

    with SessionLocal() as db:
        try:
            consume_eab_credential(db, expired.key_id)
        except EabException as exc:
            assert exc.error_name == "EAB_EXPIRED"
        else:
            raise AssertionError("expired EAB was consumed")

    print("issuance_encrypted=OK")
    print("concurrent_once=OK")
    print("expiry=OK")


if __name__ == "__main__":
    main()
