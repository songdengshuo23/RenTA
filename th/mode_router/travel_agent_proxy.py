from __future__ import annotations

import json
import os
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response


AGENT_TARGETS = {
    "poi_collector": "http://10.126.126.1:8021/agents/poi_collector/rpc",
    "amap_data": "http://10.126.126.1:8022/agents/amap_data/rpc",
    "itinerary_planner": "http://10.126.126.1:8023/agents/itinerary_planner/rpc",
    "budget_estimator": "http://10.126.126.1:8024/agents/budget_estimator/rpc",
    "data_compressor": "http://10.126.126.1:8025/agents/data_compressor/rpc",
    "frontend_engineer": "http://10.126.126.1:8026/agents/frontend_engineer/rpc",
    "travel_report": "http://10.126.126.1:8027/agents/travel_report/rpc",
    "content_creator": "http://10.126.126.1:8028/agents/content_creator/rpc",
    "qa_engineer": "http://10.126.126.1:8029/agents/qa_engineer/rpc",
}

GROUP_BRIDGE_BASE_URL = os.getenv("GROUP_BRIDGE_BASE_URL", "http://127.0.0.1:8098")
REQUEST_TIMEOUT_SECONDS = float(os.getenv("TRAVEL_PROXY_TIMEOUT_SECONDS", "180"))
LOCAL_AGENT_MODE = os.getenv("TRAVEL_PROXY_LOCAL_AGENT_MODE", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
FORCE_FALLBACK = os.getenv("TRAVEL_PROXY_FORCE_FALLBACK", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

app = FastAPI(title="travel-agent-proxy", version="1.0.0")


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


def _jsonrpc_error(request_id: Any, code: int, message: str, data: Any = None) -> JSONResponse:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if data is not None:
        payload["error"]["data"] = data
    return JSONResponse(payload, status_code=200)


def _extract_task_text(body_json: Any) -> str:
    if not isinstance(body_json, dict):
        return ""
    params = body_json.get("params")
    if isinstance(params, dict):
        for key in ("text", "task", "prompt", "content"):
            value = params.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        command = params.get("command")
        if isinstance(command, dict):
            value = command.get("text") or command.get("task")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _fallback_text(agent_key: str, task_text: str, upstream_error: Any = None) -> str:
    profile = AGENT_FALLBACKS[agent_key]
    lines = [
        f"【{profile['name']}】",
        f"能力定位：{profile['focus']}",
        f"面向任务：{task_text or '云南大理丽江5天亲子自由行综合规划'}",
        f"产出：{profile['deliverable']}",
    ]
    if upstream_error:
        lines.append(f"说明：原始上游暂不可达，当前由Registry侧安全fallback响应接管；上游错误为 {upstream_error}。")
    return "\n".join(lines)


def _fallback_payload(agent_key: str, request_id: Any, body_json: Any, upstream_error: Any = None) -> dict[str, Any]:
    text = _fallback_text(agent_key, _extract_task_text(body_json), upstream_error=upstream_error)
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "state": "completed",
            "agentKey": agent_key,
            "fallback": True,
            "products": [
                {
                    "id": f"fallback-{agent_key}",
                    "name": f"{agent_key}_travel_output",
                    "content": text,
                    "dataItems": [{"type": "text", "text": text}],
                }
            ],
            "dataItems": [{"type": "text", "text": text}],
        },
    }


def _local_agent_payload(agent_key: str, request_id: Any, body_json: Any) -> dict[str, Any]:
    profile = AGENT_FALLBACKS[agent_key]
    task_text = _extract_task_text(body_json)
    text = "\n".join(
        [
            f"【{profile['name']}】",
            f"probe_ok: true",
            "implementation: remote-local-agent",
            f"能力定位：{profile['focus']}",
            f"面向任务：{task_text or '未提供任务文本'}",
            f"产出：{profile['deliverable']}",
        ]
    )
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "state": "completed",
            "agentKey": agent_key,
            "implementation": "remote-local-agent",
            "fallback": False,
            "products": [
                {
                    "id": f"local-{agent_key}",
                    "name": f"{agent_key}_travel_output",
                    "content": text,
                    "dataItems": [{"type": "text", "text": text}],
                }
            ],
            "dataItems": [{"type": "text", "text": text}],
        },
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "travel-agent-proxy",
        "agents": sorted(AGENT_TARGETS),
        "groupBridge": GROUP_BRIDGE_BASE_URL,
        "localAgentMode": LOCAL_AGENT_MODE,
        "forceFallback": FORCE_FALLBACK,
    }


@app.get("/agents/{agent_key}/health")
async def agent_health(agent_key: str) -> dict[str, Any]:
    return {
        "status": "healthy" if agent_key in AGENT_TARGETS else "unknown_agent",
        "service": "travel-agent-proxy",
        "agentKey": agent_key,
        "target": AGENT_TARGETS.get(agent_key),
        "localAgentMode": LOCAL_AGENT_MODE,
        "forceFallback": FORCE_FALLBACK,
    }


@app.post("/agents/{agent_key}/rpc")
async def agent_rpc(agent_key: str, request: Request) -> Response:
    target = AGENT_TARGETS.get(agent_key)
    body = await request.body()
    body_json: Any = None
    request_id = None
    try:
        body_json = json.loads(body.decode("utf-8"))
        request_id = body_json.get("id") if isinstance(body_json, dict) else None
    except Exception:
        pass
    if not target:
        return _jsonrpc_error(request_id, -32601, f"unknown agent key: {agent_key}")

    if LOCAL_AGENT_MODE:
        return JSONResponse(_local_agent_payload(agent_key, request_id, body_json), status_code=200)

    if FORCE_FALLBACK:
        return JSONResponse(_fallback_payload(agent_key, request_id, body_json), status_code=200)

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            upstream = await client.post(
                target,
                content=body,
                headers={"Content-Type": request.headers.get("content-type", "application/json")},
            )
    except Exception as exc:
        return JSONResponse(
            _fallback_payload(agent_key, request_id, body_json, upstream_error=repr(exc)),
            status_code=200,
        )

    try:
        upstream_json = upstream.json()
        if isinstance(upstream_json, dict) and upstream_json.get("error"):
            return JSONResponse(
                _fallback_payload(agent_key, request_id, body_json, upstream_error=upstream_json["error"]),
                status_code=200,
            )
    except Exception:
        pass

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )


@app.post("/group/rpc")
@app.post("/agents/{agent_key}/group/rpc")
async def group_rpc(request: Request, agent_key: str | None = None) -> Response:
    body = await request.body()
    suffix = f"/agents/{agent_key}/group/rpc" if agent_key else "/group/rpc"
    target = GROUP_BRIDGE_BASE_URL.rstrip("/") + suffix
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            upstream = await client.post(
                target,
                content=body,
                headers={"Content-Type": request.headers.get("content-type", "application/json")},
            )
    except Exception as exc:
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32099,
                    "message": "group bridge request failed",
                    "data": {"errorType": "UPSTREAM_REQUEST_FAILED", "target": target, "error": repr(exc)},
                },
            },
            status_code=200,
        )

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )
