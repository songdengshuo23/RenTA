from __future__ import annotations

import asyncio
import contextlib
import os
import ssl
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / "ACPs_update_code" / "ACPs-SDK"
MODE_ROUTER = ROOT / "th" / "mode_router"
for path in (SDK, MODE_ROUTER):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from acps_sdk.aip_v21 import GroupPartnerMqClient, Product, TextDataItem
from generic_group_executor import execute_plan_group_chat_async
from mq_v21_runtime import create_client_ssl_context

LEADER_AIC = "1.2.156.3088.1.1.34C2.478BDF.3GF546.0JU4"
PARTNER_AIC = "1.2.156.3088.1.1.34C2.478BDF.3GF547.0JUE"


def tls_context(cert_file: Path, key_file: Path, ca_file: Path) -> ssl.SSLContext:
    return create_client_ssl_context(
        cert_file=str(cert_file),
        key_file=str(key_file),
        ca_file=str(ca_file),
        check_hostname=False,
    )


async def run() -> None:
    certs = ROOT / "sds" / "mq-auth-server" / "certs"
    ca_file = certs / "acps-root-ca.pem"
    partner_context = tls_context(
        certs / "partners" / f"{PARTNER_AIC}.pem",
        certs / "partners" / f"{PARTNER_AIC}.key",
        ca_file,
    )

    partner = GroupPartnerMqClient(
        partner_aic=PARTNER_AIC,
        rabbitmq_host="127.0.0.1",
        rabbitmq_port=5671,
        rabbitmq_vhost="acps",
        rabbitmq_user=None,
        rabbitmq_password=None,
        ssl_context=partner_context,
    )

    async def handle_command(command, is_mentioned: bool) -> None:
        if not is_mentioned or not command.taskId:
            return
        session_id = str(command.sessionId or "")
        await partner.accept_task(command.taskId, session_id)
        await partner.start_working(command.taskId, session_id)
        await partner.submit_for_completion(
            command.taskId,
            session_id,
            [
                Product(
                    id="stage6-product",
                    name="stage6-e2e",
                    dataItems=[TextDataItem(text="mq inbox e2e ok")],
                )
            ],
        )

    partner.set_command_handler(handle_command)
    await partner.start_inbox_consuming(partner.join_group_from_invitation)

    try:
        result = await execute_plan_group_chat_async(
            "stage6 inbox integration test",
            {
                "plan_id": "stage6-e2e-plan",
                "mode": "mode_2",
                "strategy": "single-partner-inbox",
                "work_packages": [
                    {
                        "package_id": "stage6-package",
                        "objective": "return the stage6 integration marker",
                        "skills": ["stage6-test"],
                        "agent": {
                            "aic": PARTNER_AIC,
                            "name": "Stage6 Partner",
                            "acs": {
                                "protocolVersion": "02.01",
                                "endPoints": [
                                    {
                                        "transport": "AMQP",
                                        "url": f"amqps://127.0.0.1:5671/acps?inbox=inbox_{PARTNER_AIC}",
                                    }
                                ],
                            },
                        },
                    }
                ],
            },
            payload={
                "session_id": "stage6-e2e",
                "max_poll_rounds": 100,
                "poll_interval_seconds": 0.1,
                "traffic_monitor": False,
                "mq_inbox": {
                    "enabled": True,
                    "leaderAic": LEADER_AIC,
                    "host": "127.0.0.1",
                    "port": 5671,
                    "vhost": "acps",
                    "authServiceUrl": "https://127.0.0.1:9007",
                    "certFile": str(certs / "leader.pem"),
                    "keyFile": str(certs / "leader.key"),
                    "caFile": str(ca_file),
                    "checkHostname": False,
                    "invitationTimeoutSeconds": 10,
                },
            },
        )
        if result.get("execution_transport") != "mq_inbox":
            raise AssertionError(f"unexpected execution transport: {result}")
        invited = result.get("invited_agents") or []
        if not invited or invited[0].get("invitation_route") != "inbox":
            raise AssertionError(f"partner invitation did not use MQ Inbox: {invited}")
        runs = result.get("runs") or []
        if not runs or runs[0].get("output_text") != "mq inbox e2e ok":
            raise AssertionError(f"unexpected task result: {runs}")
        print("invitation_route=inbox", flush=True)
        print("task_result=mq inbox e2e ok", flush=True)
        print("execution_transport=" + str(result.get("execution_transport")), flush=True)
        print("leader_aic=" + LEADER_AIC, flush=True)
        print("partner_aic=" + PARTNER_AIC, flush=True)
    finally:
        await asyncio.sleep(0.5)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(partner._cleanup_group_resources(), timeout=5)
        with contextlib.suppress(Exception):
            await asyncio.wait_for(partner.close(), timeout=5)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    asyncio.run(asyncio.wait_for(run(), timeout=45))
