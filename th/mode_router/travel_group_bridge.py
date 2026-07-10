from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from mq_v21_runtime import create_client_ssl_context, partner_tls_paths, truthy


HERE = Path(__file__).resolve().parent
WORKSPACE_ROOT = HERE.parent.parent
SDK_PATH = WORKSPACE_ROOT / "ACPs_update_code" / "ACPs-SDK"
if str(SDK_PATH) not in sys.path:
    sys.path.insert(0, str(SDK_PATH))

from acps_sdk.aip.aip_base_model import Product, TaskState, TextDataItem
from acps_sdk.aip.aip_group_model import RabbitMQRequest
from acps_sdk.aip.aip_group_partner import GroupPartnerMqClient, extract_text_from_command


AGENT_TARGETS = {
    "poi_collector": {
        "aic": "1.2.156.3088.0001.00001.UQJNCO.POIC01.1.0L5H",
        "url": "http://10.126.126.1:8021/agents/poi_collector/rpc",
    },
    "amap_data": {
        "aic": "1.2.156.3088.0001.00001.UQJNCO.AMAP02.1.0L5H",
        "url": "http://10.126.126.1:8022/agents/amap_data/rpc",
    },
    "itinerary_planner": {
        "aic": "1.2.156.3088.0001.00001.UQJNCO.ITIN03.1.0L5H",
        "url": "http://10.126.126.1:8023/agents/itinerary_planner/rpc",
    },
    "budget_estimator": {
        "aic": "1.2.156.3088.0001.00001.UQJNCO.BUDG04.1.0L5H",
        "url": "http://10.126.126.1:8024/agents/budget_estimator/rpc",
    },
    "data_compressor": {
        "aic": "1.2.156.3088.0001.00001.UQJNCO.CMPR05.1.0L5H",
        "url": "http://10.126.126.1:8025/agents/data_compressor/rpc",
    },
    "frontend_engineer": {
        "aic": "1.2.156.3088.0001.00001.UQJNCO.FEND06.1.0L5H",
        "url": "http://10.126.126.1:8026/agents/frontend_engineer/rpc",
    },
    "travel_report": {
        "aic": "1.2.156.3088.0001.00001.UQJNCO.RPRT07.1.0L5H",
        "url": "http://10.126.126.1:8027/agents/travel_report/rpc",
    },
    "content_creator": {
        "aic": "1.2.156.3088.0001.00001.UQJNCO.CONT08.1.0L5H",
        "url": "http://10.126.126.1:8028/agents/content_creator/rpc",
    },
    "qa_engineer": {
        "aic": "1.2.156.3088.0001.00001.UQJNCO.QAE09.1.0L5H",
        "url": "http://10.126.126.1:8029/agents/qa_engineer/rpc",
    },
}

REQUEST_TIMEOUT_SECONDS = float(os.getenv("TRAVEL_GROUP_BRIDGE_TIMEOUT_SECONDS", "240"))
FORCE_FALLBACK = os.getenv("TRAVEL_GROUP_BRIDGE_FORCE_FALLBACK", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

app = FastAPI(title="travel-group-bridge", version="1.0.0")
_clients: list[GroupPartnerMqClient] = []
_v21_clients: list[Any] = []


AGENT_FALLBACKS: dict[str, dict[str, Any]] = {
    "poi_collector": {
        "name": "POI采集智能体",
        "focus": "采集大理、丽江亲子自由行热门景点、餐厅、酒店和交通节点。",
        "deliverable": "POI清单：大理古城、洱海生态廊道、喜洲古镇、丽江古城、束河古镇、玉龙雪山蓝月谷；亲子餐厅、家庭房酒店、机场/车站接驳点。",
    },
    "amap_data": {
        "name": "高德地图坐标智能体",
        "focus": "把POI转换为可在高德地图标注的经纬度和类别信息。",
        "deliverable": "坐标标注：大理古城约25.691,100.162；洱海生态廊道约25.785,100.190；丽江古城约26.876,100.238；玉龙雪山游客中心约27.101,100.257。",
    },
    "itinerary_planner": {
        "name": "行程规划智能体",
        "focus": "按5天、2位成人和1位5岁儿童规划低疲劳行程和交通衔接。",
        "deliverable": "行程建议：D1北京飞大理休整；D2洱海/喜洲；D3大理至丽江并游丽江古城；D4玉龙雪山低强度线路；D5束河休闲后返程。",
    },
    "budget_estimator": {
        "name": "旅行预算评估智能体",
        "focus": "估算交通、住宿、门票、餐饮和本地交通总预算。",
        "deliverable": "预算区间：机票约9000-15000元，住宿约2800-5000元，餐饮约1800-3000元，门票/索道约1200-2200元，本地交通约1200-2500元，总计约16000-28000元。",
    },
    "data_compressor": {
        "name": "数据压缩智能体",
        "focus": "压缩中间POI、坐标、预算和行程数据，减少跨Agent传输体积。",
        "deliverable": "压缩策略：按poi_id引用坐标和费用字段，公共地点名去重，时间轴只保留day/slot/poi_id/transport/cost_range。",
    },
    "frontend_engineer": {
        "name": "前端可视化智能体",
        "focus": "生成地图+时间轴的前端可视化页面方案。",
        "deliverable": "前端方案：左侧高德地图点位图层，右侧5日时间轴；支持按天筛选、亲子友好标签、预算悬浮卡片和移动端纵向布局。",
    },
    "travel_report": {
        "name": "旅游攻略报告智能体",
        "focus": "输出完整旅游攻略报告，可用于网页或PDF。",
        "deliverable": "报告结构：行前准备、航班与接驳、每日行程、餐厅酒店推荐、儿童注意事项、预算明细、备选雨天方案和风险提示。",
    },
    "content_creator": {
        "name": "社交媒体内容智能体",
        "focus": "生成小红书/朋友圈风格种草文案。",
        "deliverable": "种草文案：国庆带娃去云南，5天把大理的风和丽江的慢都装进行程里；洱海骑行、喜洲稻田、蓝月谷拍照，节奏轻、出片稳。",
    },
    "qa_engineer": {
        "name": "前端质量审查智能体",
        "focus": "审查前端页面加载性能、兼容性和用户体验。",
        "deliverable": "QA建议：地图懒加载，点位聚合，首屏骨架屏，移动端时间轴避免横向溢出；Chrome/Edge/Safari和安卓微信内置浏览器需验证。",
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonrpc_error(request_id: Any, code: int, message: str, data: Any = None) -> JSONResponse:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
    if data is not None:
        payload["error"]["data"] = data
    return JSONResponse(payload, status_code=200)


def _task_result_state(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    result = payload.get("result")
    if not isinstance(result, dict):
        return ""
    status = result.get("status")
    if isinstance(status, dict):
        return str(status.get("state") or "").strip().lower()
    return ""


def _state_is_working(state: str) -> bool:
    return str(state or "").strip().lower() in {"accepted", "pending", "running", "working", "processing", "in-progress", "in_progress"}


def _state_is_terminal(state: str) -> bool:
    return str(state or "").strip().lower() in {"awaiting-completion", "completed", "failed", "rejected", "canceled", "cancelled"}


def _make_direct_rpc_payload(command: Any, task_text: str, rpc_command: str = "start") -> dict[str, Any]:
    task_id = str(getattr(command, "taskId", None) or getattr(command, "id", None) or uuid4())
    return {
        "jsonrpc": "2.0",
        "id": f"bridge-{uuid4().hex[:10]}",
        "method": "rpc",
        "params": {
            "command": {
                "type": "task-command",
                "id": f"{task_id}-{rpc_command}-{uuid4().hex[:8]}",
                "taskId": task_id,
                "sentAt": _utc_now(),
                "senderRole": "leader",
                "senderId": "travel-group-bridge",
                "command": rpc_command,
                "dataItems": ([{"type": "text", "text": task_text}] if task_text else []),
            },
            "text": task_text,
            "task": task_text,
        },
    }


def _extract_direct_output(payload: Any) -> str:
    if not isinstance(payload, dict):
        return str(payload)
    if payload.get("error"):
        return "Agent RPC error: " + json.dumps(payload["error"], ensure_ascii=False)
    result = payload.get("result")
    if isinstance(result, dict):
        products = result.get("products") or []
        for product in products:
            if not isinstance(product, dict):
                continue
            content = product.get("content")
            if content:
                return str(content)
            for item in product.get("dataItems") or []:
                if isinstance(item, dict) and item.get("text"):
                    return str(item["text"])
        for item in result.get("dataItems") or []:
            if isinstance(item, dict) and item.get("text"):
                return str(item["text"])
        status = result.get("status")
        if isinstance(status, dict):
            for item in status.get("dataItems") or []:
                if isinstance(item, dict) and item.get("text"):
                    return str(item["text"])
            return ""
        return json.dumps(result, ensure_ascii=False)
    return json.dumps(payload, ensure_ascii=False)


def _fallback_direct_output(agent_key: str, task_text: str, upstream_error: Any = None) -> str:
    profile = AGENT_FALLBACKS[agent_key]
    lines = [
        "[travel_group_bridge]",
        f"agent_key: {agent_key}",
        "target: registry-side fallback",
        "",
        f"【{profile['name']}】",
        f"能力定位：{profile['focus']}",
        f"面向任务：{task_text or '云南大理丽江5天亲子自由行综合规划'}",
        f"产出：{profile['deliverable']}",
    ]
    if upstream_error:
        lines.append(f"说明：原始上游暂不可达，当前由群聊桥接fallback响应接管；上游错误为 {upstream_error}。")
    return "\n".join(lines)


async def _call_direct_agent(agent_key: str, task_text: str, command: Any) -> str:
    target = AGENT_TARGETS[agent_key]["url"]
    started = time.perf_counter()
    if FORCE_FALLBACK:
        return _fallback_direct_output(agent_key, task_text)
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        try:
            response = await client.post(target, json=_make_direct_rpc_payload(command, task_text, "start"))
            response.raise_for_status()
            parsed = response.json()
        except Exception as exc:
            return _fallback_direct_output(agent_key, task_text, upstream_error=repr(exc))

        state = _task_result_state(parsed)
        ready_payload: Any = parsed
        awaiting_payload: Any = None
        deadline = time.perf_counter() + min(REQUEST_TIMEOUT_SECONDS, 120.0)
        while _state_is_working(state) and time.perf_counter() < deadline:
            await asyncio.sleep(1.0)
            try:
                response = await client.post(target, json=_make_direct_rpc_payload(command, task_text, "get"))
                response.raise_for_status()
                parsed = response.json()
            except Exception as exc:
                return _fallback_direct_output(agent_key, task_text, upstream_error=repr(exc))
            ready_payload = parsed
            state = _task_result_state(parsed)
            if _state_is_terminal(state):
                break

        if state == "awaiting-completion":
            awaiting_payload = ready_payload
            try:
                response = await client.post(target, json=_make_direct_rpc_payload(command, task_text, "complete"))
                response.raise_for_status()
                parsed = response.json()
                ready_payload = parsed
                state = _task_result_state(parsed) or state
            except Exception as exc:
                return _fallback_direct_output(agent_key, task_text, upstream_error=repr(exc))

    output = _extract_direct_output(ready_payload)
    if not output and awaiting_payload is not None:
        output = _extract_direct_output(awaiting_payload)
    if "Agent RPC error:" in output:
        return _fallback_direct_output(agent_key, task_text, upstream_error=output)
    return (
        f"[travel_group_bridge]\n"
        f"agent_key: {agent_key}\n"
        f"target: {target}\n"
        f"duration_ms: {round((time.perf_counter() - started) * 1000)}\n\n"
        f"{output}"
    )


def _command_handler_for(agent_key: str):
    async def handle_command(command: Any, is_mentioned: bool) -> None:
        if not is_mentioned:
            return
        client = handle_command.client
        task_id = str(getattr(command, "taskId", None) or getattr(command, "id", None) or uuid4())
        session_id = str(getattr(command, "sessionId", None) or "")
        task_text = extract_text_from_command(command) or str(getattr(command, "id", ""))
        try:
            await client.accept_task(task_id, session_id)
            await client.start_working(task_id, session_id)
            output = await _call_direct_agent(agent_key, task_text, command)
            product = Product(
                id=f"product-{uuid4().hex[:10]}",
                name=f"{agent_key}_output",
                dataItems=[TextDataItem(text=output)],
            )
            await client.submit_for_completion(task_id, session_id, [product])
        except Exception as exc:
            await client.fail_task(task_id, session_id, repr(exc))

    return handle_command


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "travel-group-bridge",
        "agents": sorted(AGENT_TARGETS),
        "activeClients": len(_clients),
        "mqInboxEnabled": truthy(os.getenv("ACPS_MQ_INBOX_ENABLED"), False),
        "mqInboxConsumers": len(_v21_clients),
    }


@app.on_event("startup")
async def start_mq_inbox_consumers() -> None:
    if not truthy(os.getenv("ACPS_MQ_INBOX_ENABLED"), False):
        return

    from acps_sdk.aip_v21 import GroupPartnerMqClient as V21GroupPartnerMqClient
    from acps_sdk.aip_v21.aip_group_runtime import ensure_valid_aic

    cert_dir = os.getenv("ACPS_MQ_PARTNER_CERT_DIR", "").strip()
    ca_file = os.getenv("ACPS_MQ_TLS_CA_FILE", "").strip()
    host = os.getenv("ACPS_MQ_HOST", "127.0.0.1").strip()
    port = int(os.getenv("ACPS_MQ_PORT", "5671"))
    vhost = os.getenv("ACPS_MQ_VHOST", "acps").strip()
    check_hostname = truthy(os.getenv("ACPS_MQ_TLS_CHECK_HOSTNAME"), False)
    if port != 5671 or vhost != "acps":
        raise RuntimeError("MQ Inbox consumers require AMQPS port 5671 and vhost acps")

    for agent_key, target in AGENT_TARGETS.items():
        aic = str(target["aic"])
        try:
            ensure_valid_aic(aic)
        except ValueError:
            continue
        cert_file, key_file = partner_tls_paths(cert_dir, aic)
        ssl_context = create_client_ssl_context(
            cert_file=cert_file,
            key_file=key_file,
            ca_file=ca_file,
            check_hostname=check_hostname,
        )
        client = V21GroupPartnerMqClient(
            partner_aic=aic,
            rabbitmq_host=host,
            rabbitmq_port=port,
            rabbitmq_vhost=vhost,
            rabbitmq_user=None,
            rabbitmq_password=None,
            ssl_context=ssl_context,
        )
        handler = _command_handler_for(agent_key)
        handler.client = client
        client.set_command_handler(handler)
        await client.start_inbox_consuming(client.join_group_from_invitation)
        _v21_clients.append(client)


@app.on_event("shutdown")
async def stop_mq_inbox_consumers() -> None:
    while _v21_clients:
        client = _v21_clients.pop()
        await client.close()


@app.post("/agents/{agent_key}/group/rpc")
async def group_rpc(agent_key: str, request: Request) -> JSONResponse:
    body = await request.json()
    request_id = body.get("id")
    if agent_key not in AGENT_TARGETS:
        return _jsonrpc_error(request_id, -32601, f"unknown agent key: {agent_key}")
    try:
        group_request = RabbitMQRequest.model_validate(body)
    except Exception as exc:
        return _jsonrpc_error(request_id, -32602, "invalid group request", repr(exc))

    invited_partners = list(getattr(group_request.params.group, "partners", []) or [])
    partner_aic = (
        getattr(invited_partners[-1], "aic", None)
        if invited_partners
        else AGENT_TARGETS[agent_key]["aic"]
    )
    client = GroupPartnerMqClient(partner_aic=partner_aic)
    handler = _command_handler_for(agent_key)
    handler.client = client
    client.set_command_handler(handler)

    response = await client.join_group(group_request)
    _clients.append(client)
    return JSONResponse(response.model_dump(exclude_none=True), status_code=200)
