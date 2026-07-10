from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

HERE = Path(__file__).resolve().parent
WORKSPACE_ROOT = HERE.parent.parent
SDK_PATH = WORKSPACE_ROOT / "ACPs_update_code" / "ACPs-SDK"

try:
    from monitoring.traffic_monitor import count_tokens, get_snapshot as get_traffic_snapshot
    from monitoring.traffic_monitor import record as record_traffic
    from monitoring.traffic_monitor import reset as reset_traffic
    from monitoring.traffic_monitor import serialize_payload
except Exception:  # pragma: no cover - monitoring must never block execution
    count_tokens = None
    get_traffic_snapshot = None
    record_traffic = None
    reset_traffic = None
    serialize_payload = None


@dataclass(frozen=True)
class GroupExecutionConfig:
    leader_aic: str = "th-generic-orchestrator"
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_vhost: str = "/"
    max_poll_rounds: int = 480
    poll_interval_seconds: float = 0.5

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any] | None = None) -> "GroupExecutionConfig":
        payload = payload or {}
        rabbitmq = payload.get("rabbitmq") or payload.get("rabbitmq_config") or payload.get("rabbitmqConfig") or {}
        return cls(
            leader_aic=str(payload.get("leader_aic") or payload.get("leaderAic") or os.getenv("GENERIC_ORCHESTRATOR_AIC") or cls.leader_aic),
            rabbitmq_host=str(rabbitmq.get("host") or os.getenv("RABBITMQ_HOST", cls.rabbitmq_host)),
            rabbitmq_port=int(rabbitmq.get("port") or os.getenv("RABBITMQ_PORT", cls.rabbitmq_port)),
            rabbitmq_user=str(rabbitmq.get("user") or os.getenv("RABBITMQ_USER", cls.rabbitmq_user)),
            rabbitmq_password=str(rabbitmq.get("password") or os.getenv("RABBITMQ_PASSWORD", cls.rabbitmq_password)),
            rabbitmq_vhost=str(rabbitmq.get("vhost") or os.getenv("RABBITMQ_VHOST", cls.rabbitmq_vhost)),
            max_poll_rounds=int(payload.get("max_poll_rounds") or payload.get("maxPollRounds") or os.getenv("GROUP_AGENT_MAX_POLLS", cls.max_poll_rounds)),
            poll_interval_seconds=float(payload.get("poll_interval_seconds") or payload.get("pollIntervalSeconds") or cls.poll_interval_seconds),
        )

    def rabbitmq_dict(self) -> dict[str, Any]:
        return {
            "host": self.rabbitmq_host,
            "port": self.rabbitmq_port,
            "user": self.rabbitmq_user,
            "password": self.rabbitmq_password,
            "vhost": self.rabbitmq_vhost,
        }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_group_rpc_url(agent_url: str) -> str:
    if not agent_url:
        return agent_url
    if "travel-agent-proxy" in agent_url and agent_url.endswith("/rpc"):
        group_url = agent_url[: -len("/rpc")] + "/group/rpc"
        return group_url.replace("http://travel-agent-proxy:8099", "http://127.0.0.1:8099")
    if "/agents/" in agent_url and agent_url.endswith("/rpc"):
        base, rest = agent_url.split("/agents/", 1)
        agent_key = rest.split("/", 1)[0]
        if base.startswith("http://10.126.126.1:802"):
            base = "http://127.0.0.1:8099"
        return f"{base.rstrip('/')}/agents/{agent_key}/group/rpc"
    return agent_url.replace("/rpc", "/group/rpc") if agent_url.endswith("/rpc") else agent_url


def _json_safe(value: Any, limit: int = 4000) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=2) if not isinstance(value, str) else value
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]..."


def _truthy(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no", "off", "disabled"}
    return bool(value)


def _payload_bool(payload: Mapping[str, Any] | None, keys: tuple[str, ...], default: bool) -> bool:
    payload = payload or {}
    for key in keys:
        if key in payload:
            return _truthy(payload.get(key), default)
    return default


def _traffic_enabled(payload: Mapping[str, Any] | None) -> bool:
    default = _truthy(os.getenv("MODE_ROUTER_TRAFFIC_MONITOR", "true"), True)
    return _payload_bool(
        payload,
        (
            "traffic_monitor",
            "trafficMonitor",
            "traffic_monitoring",
            "trafficMonitoring",
            "enable_traffic_monitor",
            "enableTrafficMonitor",
        ),
        default,
    )


def _traffic_reset_on_start(payload: Mapping[str, Any] | None) -> bool:
    default = _truthy(os.getenv("MODE_ROUTER_TRAFFIC_RESET_ON_START", "false"), False)
    return _payload_bool(payload, ("traffic_reset_on_start", "trafficResetOnStart"), default)


def _record_payload_traffic(
    *,
    enabled: bool,
    source: str,
    target: str,
    payload: Any,
    edge_type: str,
    session_id: str = "",
    execution_id: str = "",
    package_id: str = "",
    task_id: str = "",
) -> int:
    if not enabled or count_tokens is None or record_traffic is None or serialize_payload is None:
        return 0
    try:
        serialized = serialize_payload(payload)
        tokens = count_tokens(serialized)
        record_traffic(
            source=source,
            target=target,
            tokens=tokens,
            edge_type=edge_type,
            route_mode="mode_2",
            group_chat=True,
            session_id=session_id,
            execution_id=execution_id,
            package_id=package_id,
            task_id=task_id,
        )
        return tokens
    except Exception:
        return 0


def _agent_aic(package: Mapping[str, Any]) -> str:
    agent = package.get("agent") if isinstance(package.get("agent"), Mapping) else {}
    return str(agent.get("aic") or "").strip()


def _agent_name(package: Mapping[str, Any]) -> str:
    agent = package.get("agent") if isinstance(package.get("agent"), Mapping) else {}
    return str(agent.get("name") or agent.get("aic") or "").strip()


def _agent_url(package: Mapping[str, Any]) -> str:
    agent = package.get("agent") if isinstance(package.get("agent"), Mapping) else {}
    return str(agent.get("url") or agent.get("endpoint") or "").strip()


def _package_id(package: Mapping[str, Any]) -> str:
    return str(package.get("package_id") or package.get("id") or uuid4().hex[:8])


def _package_prompt(task: str, package: Mapping[str, Any], upstream_outputs: Mapping[str, str]) -> str:
    dependencies = list(package.get("depends_on") or [])
    upstream = {
        package_id: upstream_outputs.get(str(package_id), "")
        for package_id in dependencies
        if upstream_outputs.get(str(package_id))
    }
    return (
        "你是一个被通用 Orchestrator 通过群聊总线分配任务的执行智能体。\n"
        "请只完成当前 work package，不要假设自己拥有其他智能体的私有状态。\n\n"
        f"用户原始任务：\n{task}\n\n"
        f"当前 package_id：{_package_id(package)}\n"
        f"当前目标：\n{package.get('objective') or ''}\n\n"
        f"可用技能：\n{_json_safe(package.get('skills') or [])}\n\n"
        f"上游依赖结果：\n{_json_safe(upstream) if upstream else '无，上游依赖为空或尚无可用文本。'}\n\n"
        "输出要求：\n"
        "- 给出可被 root/coordinator 汇总的结构化结果。\n"
        "- 明确说明完成了哪些部分、仍有哪些假设或风险。\n"
        "- 如果需要后续智能体继续处理，请写出可传递的关键信息。"
    )


def _role_dependencies(packages: list[Mapping[str, Any]]) -> dict[str, list[str]]:
    package_ids = {_package_id(package) for package in packages}
    dependencies: dict[str, list[str]] = {}
    previous = ""
    for package in packages:
        package_id = _package_id(package)
        raw_deps = [str(item) for item in list(package.get("depends_on") or []) if str(item) in package_ids]
        if not raw_deps and package.get("dispatch_mode") == "sequential" and previous:
            raw_deps = [previous]
        dependencies[package_id] = raw_deps
        previous = package_id
    return dependencies


def _final_state_terminal(state: Any, task_state: Any) -> bool:
    terminal = {
        getattr(task_state, "AwaitingCompletion", "awaiting-completion"),
        getattr(task_state, "Completed", "completed"),
        getattr(task_state, "Failed", "failed"),
        getattr(task_state, "Rejected", "rejected"),
        getattr(task_state, "Canceled", "canceled"),
    }
    return state in terminal or str(state).lower() in {"awaiting-completion", "completed", "failed", "rejected", "canceled", "cancelled"}


async def execute_plan_group_chat_async(
    task: str,
    plan: Mapping[str, Any],
    *,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if str(SDK_PATH) not in sys.path:
        sys.path.insert(0, str(SDK_PATH))

    from acps_sdk.aip import ACSObject, GroupLeader, TaskState

    config = GroupExecutionConfig.from_payload(payload)
    packages = [package for package in list(plan.get("work_packages") or []) if isinstance(package, Mapping)]
    if plan.get("mode") != "mode_2":
        return {
            "execution_id": f"exec-{uuid4().hex[:12]}",
            "plan_id": plan.get("plan_id"),
            "status": "skipped",
            "mode": plan.get("mode"),
            "strategy": plan.get("strategy"),
            "dry_run": False,
            "group_chat": False,
            "message": "Real group execution only applies to mode_2 plans.",
            "runs": [],
        }
    if not packages:
        raise ValueError("mode_2 plan has no work_packages to execute")

    missing_endpoints = [
        {"package_id": _package_id(package), "aic": _agent_aic(package), "name": _agent_name(package)}
        for package in packages
        if not _agent_url(package)
    ]
    if missing_endpoints:
        raise ValueError(f"cannot execute group chat because agent endpoint URL is missing: {missing_endpoints}")

    execution_id = f"exec-{uuid4().hex[:12]}"
    session_id = str((payload or {}).get("session_id") or (payload or {}).get("sessionId") or f"generic-{uuid4().hex[:10]}")
    task_prefix = f"generic-{session_id}"
    traffic_enabled = _traffic_enabled(payload)
    if traffic_enabled and _traffic_reset_on_start(payload) and reset_traffic is not None:
        reset_traffic()
    leader = GroupLeader(leader_aic=config.leader_aic, rabbitmq_config=config.rabbitmq_dict())
    group_session = await leader.create_group_session(session_id=session_id, initial_partners=[])

    invited: list[dict[str, Any]] = []
    seen_aics: set[str] = set()
    for package in packages:
        aic = _agent_aic(package)
        if not aic or aic in seen_aics:
            continue
        seen_aics.add(aic)
        group_rpc_url = _to_group_rpc_url(_agent_url(package))
        invite_tokens = _record_payload_traffic(
            enabled=traffic_enabled,
            source=config.leader_aic,
            target=aic,
            payload={"session_id": session_id, "partner_aic": aic, "partner_rpc_url": group_rpc_url},
            edge_type="partner_invite",
            session_id=session_id,
            execution_id=execution_id,
            package_id=_package_id(package),
        )
        await leader.invite_partner(
            session_id=session_id,
            partner_acs=ACSObject(aic=aic),
            partner_rpc_url=group_rpc_url,
        )
        invited.append(
            {
                "aic": aic,
                "name": _agent_name(package),
                "rpc_url": _agent_url(package),
                "group_rpc_url": group_rpc_url,
                "traffic_invite_tokens": invite_tokens,
            }
        )

    dependencies = _role_dependencies(packages)
    package_by_id = {_package_id(package): package for package in packages}
    pending = [_package_id(package) for package in packages]
    completed: set[str] = set()
    outputs: dict[str, str] = {}
    run_by_package: dict[str, dict[str, Any]] = {}
    events: list[dict[str, Any]] = [
        {
            "timestamp": _utc_now(),
            "state": "running",
            "stage": "group_session_created",
            "session_id": session_id,
            "invited_count": len(invited),
        }
    ]

    async def dispatch_package(package_id: str) -> None:
        package = package_by_id[package_id]
        aic = _agent_aic(package)
        prompt = _package_prompt(task, package, outputs)
        task_id = f"{task_prefix}-{package_id}"
        started = time.perf_counter()
        dispatch_tokens = _record_payload_traffic(
            enabled=traffic_enabled,
            source=config.leader_aic,
            target=aic,
            payload={"session_id": session_id, "task_id": task_id, "text_content": prompt, "mentions": [aic]},
            edge_type="task_dispatch",
            session_id=session_id,
            execution_id=execution_id,
            package_id=package_id,
            task_id=task_id,
        )
        events.append(
            {
                "timestamp": _utc_now(),
                "state": "assigned",
                "stage": "agent_dispatch",
                "package_id": package_id,
                "agent_aic": aic,
                "agent_name": _agent_name(package),
                "task_id": task_id,
                "traffic_tokens": dispatch_tokens,
            }
        )
        await group_session.leader_mq_client.start_task(
            session_id=session_id,
            text_content=prompt,
            task_id=task_id,
            mentions=[aic],
        )

        observed: Mapping[str, Any] | None = None
        poll_round = 0
        while True:
            snap = group_session.get_partner_task_snapshot(task_id, aic)
            if snap:
                observed = snap
                state = snap.get("state")
                events.append(
                    {
                        "timestamp": _utc_now(),
                        "state": str(state),
                        "stage": "agent_status",
                        "package_id": package_id,
                        "agent_aic": aic,
                        "task_id": task_id,
                    }
                )
                if _final_state_terminal(state, TaskState):
                    break
            poll_round += 1
            if poll_round > config.max_poll_rounds:
                break
            await asyncio.sleep(config.poll_interval_seconds)

        final_state = str(observed.get("state") if observed else "unknown")
        output_text = ""
        if observed:
            output_text = str(observed.get("product_text") or observed.get("awaiting_prompt") or "")
        if not output_text:
            output_text = f"[NO_GROUP_OUTPUT] package_id={package_id}"
        response_tokens = _record_payload_traffic(
            enabled=traffic_enabled,
            source=aic,
            target=config.leader_aic,
            payload={"task_id": task_id, "state": final_state, "output_text": output_text},
            edge_type="agent_result",
            session_id=session_id,
            execution_id=execution_id,
            package_id=package_id,
            task_id=task_id,
        )
        outputs[package_id] = output_text

        if observed and observed.get("state") == getattr(TaskState, "AwaitingCompletion", None):
            _record_payload_traffic(
                enabled=traffic_enabled,
                source=config.leader_aic,
                target=aic,
                payload={"task_id": task_id, "session_id": session_id, "command": "complete_task"},
                edge_type="task_completion_ack",
                session_id=session_id,
                execution_id=execution_id,
                package_id=package_id,
                task_id=task_id,
            )
            await group_session.leader_mq_client.complete_task(task_id=task_id, session_id=session_id, mentions=[aic])

        run_by_package[package_id] = {
            "run_id": f"run-{uuid4().hex[:10]}",
            "package_id": package_id,
            "task_id": task_id,
            "agent": dict(package.get("agent") or {}),
            "status": "completed" if output_text else "unknown",
            "final_state": final_state,
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "depends_on": dependencies.get(package_id, []),
            "prompt_length": len(prompt),
            "output_length": len(output_text),
            "traffic_prompt_tokens": dispatch_tokens,
            "traffic_output_tokens": response_tokens,
            "output_text": output_text,
            "raw_snapshot": dict(observed or {}),
        }

    while pending:
        ready = [package_id for package_id in pending if all(dep in completed for dep in dependencies.get(package_id, []))]
        if not ready:
            ready = pending[:1]
        await asyncio.gather(*(dispatch_package(package_id) for package_id in ready))
        for package_id in ready:
            completed.add(package_id)
            pending.remove(package_id)

    runs = [run_by_package[_package_id(package)] for package in packages if _package_id(package) in run_by_package]
    final_result = "\n\n".join(
        f"## {run['agent'].get('name') or run['package_id']}\n{run['output_text']}"
        for run in runs
    )
    final_result_tokens = _record_payload_traffic(
        enabled=traffic_enabled,
        source=config.leader_aic,
        target="client",
        payload={"execution_id": execution_id, "session_id": session_id, "final_result": final_result},
        edge_type="final_result",
        session_id=session_id,
        execution_id=execution_id,
    )
    traffic_snapshot = get_traffic_snapshot() if traffic_enabled and get_traffic_snapshot is not None else {"enabled": False}
    events.append(
        {
            "timestamp": _utc_now(),
            "state": "done",
            "stage": "group_execution_complete",
            "completed_packages": len(runs),
            "traffic_tokens": final_result_tokens,
        }
    )
    return {
        "execution_id": execution_id,
        "plan_id": plan.get("plan_id"),
        "status": "done" if len(runs) == len(packages) else "partial",
        "mode": plan.get("mode"),
        "strategy": plan.get("strategy"),
        "dry_run": False,
        "group_chat": True,
        "session_id": session_id,
        "leader_aic": config.leader_aic,
        "invited_agents": invited,
        "runs": runs,
        "events": events,
        "traffic_snapshot": traffic_snapshot,
        "final_result": final_result,
        "next_requirement": "",
    }


def execute_plan_group_chat(
    task: str,
    plan: Mapping[str, Any],
    *,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return asyncio.run(execute_plan_group_chat_async(task, plan, payload=payload))
