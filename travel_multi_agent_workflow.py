from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4


USER_QUESTION = """我计划在2026年国庆期间从北京出发，去云南大理和丽江进行为期5天的自由行，同行有2位大人和1位5岁儿童。请帮我：
1. 采集沿途及目的地的热门景点、餐厅、酒店POI信息；
2. 将POI转换为高德地图坐标并标注；
3. 根据时间和儿童需求规划每日行程（含交通衔接）；
4. 评估总预算（交通、住宿、门票、餐饮）；
5. 压缩所有中间数据以减少传输开销；
6. 生成可交互的前端可视化页面（地图+时间轴）；
7. 输出一份完整的旅游攻略报告（PDF/网页）；
8. 同时生成一篇适合发在小红书/朋友圈的社交媒体种草文案；
9. 最后对生成的前端页面进行质量审查（加载性能、兼容性、用户体验）。

请智能体进行协作，给出最终综合结果。"""


RUNS_DIR = Path(__file__).resolve().parent / "travel_runs"

TASK_BRIEF = (
    "2026年国庆，北京出发，大理+丽江5天自由行；同行2位成人、1位5岁儿童。"
    "需要POI、GCJ-02坐标、每日亲子行程、预算、压缩数据、前端页面、攻略报告、"
    "小红书/朋友圈文案和前端质量审查。价格/开放/交通均标注出行前二次确认。"
)


@dataclass(frozen=True)
class AgentStep:
    role: str
    agent_name: str
    port: int
    path_name: str
    objective: str
    depends_on: tuple[str, ...] = ()
    timeout_seconds: int = 240
    host: str = "10.126.126.1"
    output_limit_chars: int = 1600
    retry_timeout_seconds: int = 120

    @property
    def endpoint(self) -> str:
        return f"http://{self.host}:{self.port}/agents/{self.path_name}/rpc"


AGENT_STEPS: tuple[AgentStep, ...] = (
    AgentStep(
        "poi_collection",
        "POI采集智能体",
        8021,
        "poi_collector",
        "采集北京出发到大理、丽江 5 天亲子自由行所需的热门景点、餐厅、酒店 POI，按城市和类型结构化输出。",
    ),
    AgentStep(
        "coordinate_mapping",
        "高德地图坐标智能体",
        8022,
        "amap_data",
        "把上游 POI 转换为高德地图 GCJ-02 坐标，补充可用于地图标注的经纬度、标签和城市。",
        ("poi_collection",),
    ),
    AgentStep(
        "itinerary_planning",
        "行程规划智能体",
        8023,
        "itinerary_planner",
        "根据 POI、坐标、亲子需求和 2026 年国庆 5 天约束，规划每日行程与交通衔接。",
        ("poi_collection", "coordinate_mapping"),
    ),
    AgentStep(
        "budget_estimation",
        "旅行预算评估智能体",
        8024,
        "budget_estimator",
        "估算 2 位成人 + 1 位 5 岁儿童的总预算，拆分交通、住宿、门票、餐饮和机动费用。",
        ("itinerary_planning",),
    ),
    AgentStep(
        "data_compression",
        "数据压缩智能体",
        8025,
        "data_compressor",
        "压缩 POI、坐标、行程和预算等中间数据，保留后续前端、报告、文案和质检所需字段。",
        ("poi_collection", "coordinate_mapping", "itinerary_planning", "budget_estimation"),
    ),
    AgentStep(
        "frontend_visualization",
        "前端可视化智能体",
        8026,
        "frontend_engineer",
        "基于压缩后的路线数据生成可交互前端页面方案，包含地图标注、5 日时间轴、预算摘要和亲子提示。",
        ("data_compression",),
    ),
    AgentStep(
        "travel_report",
        "旅游攻略报告智能体",
        8027,
        "travel_report",
        "整合上游结果，输出完整旅游攻略报告内容，可作为网页报告或 PDF 内容源。",
        ("data_compression", "frontend_visualization"),
    ),
    AgentStep(
        "social_content",
        "社交媒体内容智能体",
        8028,
        "content_creator",
        "基于行程亮点生成适合小红书/朋友圈的种草文案，包含标题、正文、标签和亲子卖点。",
        ("data_compression", "travel_report"),
    ),
    AgentStep(
        "quality_review",
        "前端质量审查智能体",
        8029,
        "qa_engineer",
        "审查前端页面与报告结果，覆盖加载性能、兼容性、用户体验、内容完整性和可改进项。",
        ("frontend_visualization", "travel_report", "social_content"),
    ),
)


FALLBACK_POIS = [
    {"name": "大理古城", "city": "大理", "type": "景点", "lat": 25.692, "lng": 100.165},
    {"name": "洱海生态廊道", "city": "大理", "type": "景点", "lat": 25.800, "lng": 100.210},
    {"name": "崇圣寺三塔", "city": "大理", "type": "景点", "lat": 25.704, "lng": 100.148},
    {"name": "喜洲古镇", "city": "大理", "type": "景点", "lat": 25.852, "lng": 100.130},
    {"name": "丽江古城", "city": "丽江", "type": "景点", "lat": 26.872, "lng": 100.234},
    {"name": "束河古镇", "city": "丽江", "type": "景点", "lat": 26.920, "lng": 100.210},
    {"name": "玉龙雪山", "city": "丽江", "type": "景点", "lat": 27.101, "lng": 100.257},
    {"name": "黑龙潭公园", "city": "丽江", "type": "景点", "lat": 26.889, "lng": 100.232},
]


ROLE_OUTPUT_LIMITS = {
    "poi_collection": 2600,
    "coordinate_mapping": 1800,
    "itinerary_planning": 2200,
    "budget_estimation": 1600,
    "data_compression": 3600,
    "frontend_visualization": 2200,
    "travel_report": 2600,
    "social_content": 1400,
    "quality_review": 1600,
}


RETRY_OUTPUT_LIMITS = {
    "poi_collection": 1200,
    "coordinate_mapping": 900,
    "itinerary_planning": 1000,
    "budget_estimation": 900,
    "data_compression": 1600,
    "frontend_visualization": 1000,
    "travel_report": 1200,
    "social_content": 800,
    "quality_review": 900,
}


ROLE_FORMAT_HINTS = {
    "poi_collection": "输出JSON数组，覆盖大理/丽江的景点、餐厅、酒店，字段含id/name/city/type/address/kid_tip/confidence。",
    "coordinate_mapping": "输出JSON数组，字段含id/name/city/lng/lat/coord_system/source_confidence；坐标使用GCJ-02近似值。",
    "itinerary_planning": "输出5日Markdown表格，含上午/下午/晚上、交通衔接、儿童节奏、备选方案。",
    "budget_estimation": "输出预算表，拆分交通/住宿/门票/餐饮/市内交通/机动，并给经济/舒适区间。",
    "data_compression": "输出紧凑JSON，保留pois、days、budget、warnings、handoff_summary，去掉冗余解释。",
    "frontend_visualization": "输出前端页面方案和核心数据结构，含地图marker、时间轴交互、响应式和无障碍要点。",
    "travel_report": "输出网页/PDF报告正文结构，含行前准备、每日攻略、亲子提醒、预算和风险。",
    "social_content": "输出1篇小红书和1篇朋友圈文案，含标题、正文、标签、亲子卖点。",
    "quality_review": "基于上游页面方案做静态QA，输出性能、兼容性、用户体验、P0/P1/P2问题和结论。",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str, limit: int = 36) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", text).strip("_")
    return (cleaned or "travel_task")[:limit]


def _ensure_run_dir(task: str) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = RUNS_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{_slug(task)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _event(run_dir: Path, *, stage: str, state: str, message: str, role: str = "") -> None:
    payload = {
        "timestamp": _now(),
        "stage": stage,
        "state": state,
        "role": role,
        "message": message,
    }
    _append_jsonl(run_dir / "events.jsonl", payload)
    print(f"[{state}] {stage}{' | ' + role if role else ''} - {message}", flush=True)


def _compress_text(text: str, max_chars: int = 9000) -> dict[str, Any]:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return {
            "raw_length": len(text),
            "compressed_length": len(text),
            "ratio": 1.0,
            "text": text,
            "method": "pass_through",
        }
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    priority: list[str] = []
    rest: list[str] = []
    for line in lines:
        if line.startswith(("#", "-", "*")) or any(key in line for key in ("预算", "坐标", "行程", "酒店", "餐厅", "景点", "儿童", "风险", "建议")):
            priority.append(line)
        else:
            rest.append(line)
    selected: list[str] = []
    current = 0
    for line in priority + rest:
        extra = len(line) + 1
        if current + extra > max_chars:
            if not selected:
                selected.append(line[:max_chars])
                current = max_chars
            break
        selected.append(line)
        current += extra
    compressed = "\n".join(selected)
    if not compressed and text:
        compressed = text[:max_chars]
    return {
        "raw_length": len(text),
        "compressed_length": len(compressed),
        "ratio": round(len(compressed) / len(text), 4) if text else 1.0,
        "text": compressed,
        "method": "priority_lines_truncate",
    }


def _build_command_payload(step: AgentStep, prompt: str, session_id: str) -> dict[str, Any]:
    task_id = f"{session_id}-{step.role}"
    return {
        "jsonrpc": "2.0",
        "id": task_id,
        "method": "rpc",
        "params": {
            "command": {
                "type": "task-command",
                "id": task_id,
                "sentAt": _now(),
                "senderRole": "leader",
                "senderId": "travel-multi-agent-orchestrator",
                "command": "start",
                "taskId": task_id,
                "sessionId": session_id,
                "dataItems": [{"type": "text", "text": prompt}],
            }
        },
    }


def _extract_text_from_data_items(items: Any) -> list[str]:
    texts: list[str] = []
    if not isinstance(items, list):
        return texts
    for item in items:
        if not isinstance(item, Mapping):
            continue
        if item.get("type") == "text" and item.get("text"):
            texts.append(str(item["text"]))
        elif item.get("type") == "data" and item.get("data") is not None:
            texts.append(json.dumps(item["data"], ensure_ascii=False))
    return texts


def extract_agent_text(response_payload: Mapping[str, Any]) -> str:
    result = response_payload.get("result")
    if not isinstance(result, Mapping):
        return json.dumps(response_payload, ensure_ascii=False)
    texts: list[str] = []
    texts.extend(_extract_text_from_data_items(result.get("dataItems")))
    status = result.get("status")
    if isinstance(status, Mapping):
        texts.extend(_extract_text_from_data_items(status.get("dataItems")))
    products = result.get("products")
    if isinstance(products, list):
        for product in products:
            if isinstance(product, Mapping):
                texts.extend(_extract_text_from_data_items(product.get("dataItems")))
    return "\n\n".join(texts).strip() or json.dumps(result, ensure_ascii=False)


def extract_result_state(response_payload: Mapping[str, Any] | None) -> str:
    if not isinstance(response_payload, Mapping):
        return ""
    result = response_payload.get("result")
    if not isinstance(result, Mapping):
        return ""
    status = result.get("status")
    if not isinstance(status, Mapping):
        return ""
    return str(status.get("state") or "").strip().lower()


def is_failure_state(state: str) -> bool:
    return state in {"failed", "failure", "error", "rejected", "canceled", "cancelled"}


def call_agent(step: AgentStep, prompt: str, session_id: str) -> dict[str, Any]:
    payload = _build_command_payload(step, prompt, session_id)
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    request = urllib.request.Request(
        step.endpoint,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=step.timeout_seconds) as response:
            raw = response.read().decode("utf-8", "replace")
            parsed = json.loads(raw)
            result_state = extract_result_state(parsed)
            return {
                "ok": response.status == 200 and not parsed.get("error") and not is_failure_state(result_state),
                "status_code": response.status,
                "duration_ms": round((time.perf_counter() - started) * 1000),
                "raw_text": raw,
                "payload": parsed,
                "error": parsed.get("error"),
                "result_state": result_state,
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        return {
            "ok": False,
            "status_code": exc.code,
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "raw_text": raw,
            "payload": None,
            "error": f"HTTPError: {exc}",
            "result_state": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "raw_text": "",
            "payload": None,
            "error": f"{type(exc).__name__}: {exc}",
            "result_state": "",
        }


def build_prompt(
    step: AgentStep,
    prior_outputs: Mapping[str, Mapping[str, Any]],
    *,
    retry: bool = False,
) -> tuple[str, dict[str, Any]]:
    upstream_sections: list[str] = []
    compression_records: dict[str, Any] = {}
    output_limit = (
        RETRY_OUTPUT_LIMITS.get(step.role, step.output_limit_chars)
        if retry
        else ROLE_OUTPUT_LIMITS.get(step.role, step.output_limit_chars)
    )
    upstream_limit = 1100 if retry else (2600 if step.role == "data_compression" else 1800)
    for dep in step.depends_on:
        output = prior_outputs.get(dep, {})
        text = str(output.get("output_text") or output.get("error") or "")
        compressed = _compress_text(text, upstream_limit)
        compression_records[dep] = {key: value for key, value in compressed.items() if key != "text"}
        upstream_status = "成功" if output.get("ok") else "失败/低置信"
        upstream_sections.append(
            f"## 上游结果：{dep}\n"
            f"- 状态：{upstream_status}\n"
            f"- 压缩方法：{compressed['method']}\n"
            f"- 原始长度：{compressed['raw_length']}，传输长度：{compressed['compressed_length']}，比例：{compressed['ratio']}\n\n"
            f"{compressed['text']}"
        )
    upstream = "\n\n".join(upstream_sections)
    retry_note = "这是一次快速重试；请不要解释失败原因，直接给可用结果。" if retry else ""
    prompt = f"""你是{step.agent_name}，正在参与一个 9-agent 旅行规划协作任务。

任务简述：
{TASK_BRIEF}

你本轮职责：
{step.objective}

输出格式：
{ROLE_FORMAT_HINTS.get(step.role, "输出结构化中文结果。")}

协作要求：
- 只完成你的职责，不要替其他 agent 做最终总结。
- 优先输出结构化结果，字段命名清晰，便于下游 agent 消费。
- 若使用估算信息，请标注“需出行前二次确认”。
- 面向 2 位成人 + 1 位 5 岁儿童，注意节奏、午休、海拔和交通衔接。
- 如上游为空或失败，请使用低置信度合理估算继续完成你的职责，不要中断。
- 严格控制在 {output_limit} 个中文字以内；不要调用浏览器、不要生成图片、不要输出无关说明。
- 输出中文。
{retry_note}

{upstream if upstream else "当前没有上游结果，你是本工作流第一步。"}
"""
    return prompt, compression_records


def _usable_agent_response(result: Mapping[str, Any], output_text: str) -> bool:
    return bool(result.get("ok")) and bool(output_text.strip())


def _agent_result_to_markdown(result: Mapping[str, Any]) -> str:
    title = f"### {result.get('agent_name', '')} / {result.get('role', '')}"
    status = "成功" if result.get("ok") else "失败"
    body = str(result.get("output_text") or result.get("error") or "").strip()
    return f"{title}\n\n- 状态：{status}\n- 耗时：{result.get('duration_ms', 0)} ms\n- Endpoint：`{result.get('endpoint', '')}`\n\n{body}\n"


def _fallback_itinerary() -> str:
    return """| 天数 | 城市 | 安排 | 亲子节奏 |
|---|---|---|---|
| D1 | 北京-大理 | 飞抵大理，入住古城或洱海西线；傍晚大理古城轻松逛吃 | 不安排高强度景点，留出午睡/早睡 |
| D2 | 大理 | 洱海生态廊道骑行/电瓶车、喜洲古镇、海舌/廊桥拍照 | 上午户外，下午咖啡/扎染体验 |
| D3 | 大理-丽江 | 崇圣寺三塔外观或轻游，动车/包车到丽江，夜游丽江古城 | 中午转场，减少连续步行 |
| D4 | 丽江 | 玉龙雪山或云杉坪/蓝月谷，下午回城休整 | 关注海拔反应，儿童不建议硬上高海拔 |
| D5 | 丽江-北京 | 束河古镇、黑龙潭公园，返程 | 只安排半日轻松景点 |
|"""


def _fallback_budget() -> str:
    return """预算粗估：国庆旺季 2 大 1 小约 18,000-28,000 元。机票/高铁 7,000-13,000；住宿 5,000-8,000；餐饮 2,500-4,000；门票及交通 2,500-4,500；机动 1,000-2,000。需以 2026 年实际票价、酒店和景区政策为准。"""


def build_interactive_html(run_dir: Path, outputs: Mapping[str, Mapping[str, Any]]) -> str:
    page_path = run_dir / "interactive_map_timeline.html"
    poi_json = json.dumps(FALLBACK_POIS, ensure_ascii=False)
    itinerary_text = html.escape(outputs.get("itinerary_planning", {}).get("output_text") or _fallback_itinerary())
    budget_text = html.escape(outputs.get("budget_estimation", {}).get("output_text") or _fallback_budget())
    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>北京-大理-丽江 5日亲子自由行</title>
<style>
:root {{
  --ink:#20231f; --muted:#687066; --paper:#fbfaf3; --line:#d7d0bd;
  --forest:#2f5d50; --lake:#4d91a8; --sun:#f0b35a; --rose:#c86f5d;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family: Georgia, "Noto Serif SC", "Songti SC", serif; color:var(--ink); background:var(--paper); }}
header {{ padding:28px clamp(18px,4vw,52px) 18px; border-bottom:1px solid var(--line); }}
h1 {{ margin:0; font-size:clamp(28px,4vw,54px); letter-spacing:0; line-height:1.05; }}
.sub {{ margin-top:10px; color:var(--muted); max-width:900px; line-height:1.7; }}
.layout {{ display:grid; grid-template-columns:minmax(320px, 1.1fr) minmax(300px, .9fr); gap:24px; padding:24px clamp(18px,4vw,52px); }}
.map {{ min-height:620px; position:relative; border:1px solid var(--line); background:#e8efe7; overflow:hidden; border-radius:8px; }}
.map::before {{ content:""; position:absolute; inset:0; background:
  linear-gradient(135deg, rgba(77,145,168,.18), transparent 42%),
  repeating-linear-gradient(30deg, rgba(47,93,80,.08) 0 2px, transparent 2px 26px); }}
.route {{ position:absolute; inset:42px; border:3px dashed rgba(47,93,80,.55); border-left-color:transparent; border-bottom-color:rgba(200,111,93,.6); border-radius:52% 38% 45% 42%; transform:rotate(-8deg); }}
.pin {{ position:absolute; width:160px; max-width:34vw; padding:10px 12px; background:rgba(251,250,243,.94); border:1px solid var(--line); border-radius:8px; box-shadow:0 10px 24px rgba(32,35,31,.12); }}
.pin b {{ display:block; font-size:15px; }}
.pin small {{ color:var(--muted); }}
.pin::after {{ content:""; position:absolute; left:18px; bottom:-9px; width:14px; height:14px; background:var(--rose); border-radius:50%; border:2px solid var(--paper); }}
.p0{{left:10%;top:14%}} .p1{{left:43%;top:20%}} .p2{{left:23%;top:42%}} .p3{{left:61%;top:47%}} .p4{{left:18%;top:67%}} .p5{{left:56%;top:70%}}
.panel {{ display:flex; flex-direction:column; gap:18px; }}
.band {{ border-top:1px solid var(--line); padding-top:16px; }}
h2 {{ font-size:22px; margin:0 0 12px; }}
.day {{ display:grid; grid-template-columns:54px 1fr; gap:14px; padding:13px 0; border-bottom:1px solid var(--line); }}
.badge {{ width:44px; height:44px; border-radius:50%; display:grid; place-items:center; background:var(--forest); color:white; font-weight:700; }}
.copy {{ white-space:pre-wrap; line-height:1.55; max-height:270px; overflow:auto; }}
.chips {{ display:flex; flex-wrap:wrap; gap:8px; }}
.chip {{ border:1px solid var(--line); border-radius:999px; padding:6px 10px; background:#fffdf7; }}
button {{ border:1px solid var(--forest); background:var(--forest); color:white; padding:10px 14px; border-radius:8px; cursor:pointer; }}
button:hover {{ background:#24483e; }}
@media (max-width:860px) {{ .layout {{ grid-template-columns:1fr; }} .map {{ min-height:560px; }} }}
</style>
</head>
<body>
<header>
  <h1>北京出发，大理与丽江 5 日亲子自由行</h1>
  <div class="sub">2026 年国庆档期，2 位成人与 1 位 5 岁儿童。路线以轻松节奏、古城体验、洱海亲水和丽江自然风光为核心，所有价格与开放状态需出行前二次确认。</div>
</header>
<main class="layout">
  <section class="map" aria-label="云南大理丽江路线地图">
    <div class="route"></div>
    <div class="pin p0"><b>大理古城</b><small>首日落脚，晚餐与散步</small></div>
    <div class="pin p1"><b>洱海生态廊道</b><small>亲子骑行/电瓶车</small></div>
    <div class="pin p2"><b>喜洲古镇</b><small>扎染、乳扇、稻田</small></div>
    <div class="pin p3"><b>丽江古城</b><small>转场后夜游</small></div>
    <div class="pin p4"><b>玉龙雪山</b><small>云杉坪/蓝月谷</small></div>
    <div class="pin p5"><b>束河古镇</b><small>返程日前轻松游</small></div>
  </section>
  <section class="panel">
    <div class="band">
      <h2>5 日时间轴</h2>
      <div id="timeline"></div>
    </div>
    <div class="band">
      <h2>预算与提醒</h2>
      <div class="copy">{budget_text}</div>
    </div>
    <div class="band">
      <h2>POI 标注数据</h2>
      <div class="chips" id="poiChips"></div>
      <p><button type="button" onclick="toggleRaw()">查看/隐藏坐标 JSON</button></p>
      <pre id="raw" hidden></pre>
    </div>
  </section>
</main>
<script>
const pois = {poi_json};
const days = [
  ['D1','北京到大理，入住大理古城/洱海西线，傍晚轻松逛吃。'],
  ['D2','洱海生态廊道、喜洲古镇，下午安排低强度体验。'],
  ['D3','崇圣寺三塔轻游后转场丽江，夜游丽江古城。'],
  ['D4','玉龙雪山低海拔玩法优先：云杉坪、蓝月谷，下午回城休整。'],
  ['D5','束河古镇、黑龙潭公园半日游，返程北京。']
];
document.getElementById('timeline').innerHTML = days.map(d => `<div class="day"><div class="badge">${{d[0]}}</div><div>${{d[1]}}</div></div>`).join('');
document.getElementById('poiChips').innerHTML = pois.map(p => `<span class="chip">${{p.city}} · ${{p.name}} · ${{p.type}}</span>`).join('');
document.getElementById('raw').textContent = JSON.stringify(pois, null, 2);
function toggleRaw() {{ const el = document.getElementById('raw'); el.hidden = !el.hidden; }}
</script>
<!-- Agent itinerary excerpt:
{itinerary_text[:4000]}
-->
</body>
</html>
"""
    _write_text(page_path, html_text)
    return str(page_path)


def build_report_html(run_dir: Path, outputs: Mapping[str, Mapping[str, Any]]) -> str:
    report_path = run_dir / "travel_report.html"
    sections = []
    for step in AGENT_STEPS:
        result = outputs.get(step.role, {})
        sections.append(
            f"<section><h2>{html.escape(step.agent_name)}：{html.escape(step.objective)}</h2>"
            f"<p><b>状态：</b>{'成功' if result.get('ok') else '失败'}；<b>耗时：</b>{result.get('duration_ms', 0)} ms</p>"
            f"<pre>{html.escape(str(result.get('output_text') or result.get('error') or ''))}</pre></section>"
        )
    report_html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>大理丽江亲子自由行协作报告</title>
<style>
body{{margin:0;background:#fbfaf3;color:#20231f;font-family:Georgia,"Noto Serif SC","Songti SC",serif;}}
main{{max-width:1040px;margin:auto;padding:32px 20px 64px;}}
h1{{font-size:42px;line-height:1.1;margin:0 0 12px;}}
h2{{font-size:24px;margin-top:32px;border-top:1px solid #d7d0bd;padding-top:18px;}}
p{{line-height:1.7}} pre{{white-space:pre-wrap;line-height:1.55;background:#fffdf7;border:1px solid #d7d0bd;border-radius:8px;padding:16px;overflow:auto;}}
.note{{color:#687066}}
</style></head><body><main>
<h1>北京-大理-丽江 5 日亲子自由行协作报告</h1>
<p class="note">本报告由 9 个旅行智能体按 POI、坐标、行程、预算、压缩、前端、报告、社媒、质检顺序协作生成。国庆档价格、航班、酒店、景区开放和儿童政策需在 2026 年出行前二次确认。</p>
{''.join(sections)}
</main></body></html>"""
    _write_text(report_path, report_html)
    return str(report_path)


def build_final_markdown(run_dir: Path, outputs: Mapping[str, Mapping[str, Any]], artifacts: Mapping[str, str]) -> str:
    all_ok = all(bool(outputs.get(step.role, {}).get("ok")) for step in AGENT_STEPS)
    lines = [
        "# 9-Agent 协作综合结果：北京-大理-丽江 5 日亲子自由行",
        "",
        f"- 运行目录：`{run_dir}`",
        f"- 9 个 agent RPC 调用：{'全部成功' if all_ok else '存在失败，详见各 step 原始记录'}",
        f"- 交互前端页面：`{artifacts.get('interactive_page', '')}`",
        f"- 网页攻略报告：`{artifacts.get('report_page', '')}`",
        "",
        "## 推荐总览",
        "",
        _fallback_itinerary(),
        "",
        "## 预算总览",
        "",
        outputs.get("budget_estimation", {}).get("output_text") or _fallback_budget(),
        "",
        "## Agent 协作输出",
        "",
    ]
    for step in AGENT_STEPS:
        lines.append(_agent_result_to_markdown(outputs.get(step.role, {})))
    lines.extend(
        [
            "",
            "## 出行前必须二次确认",
            "",
            "- 2026 年国庆放假安排、机票/高铁票开售时间与价格。",
            "- 玉龙雪山、索道、蓝月谷、三塔等景区开放、儿童票和限流政策。",
            "- 酒店家庭房/亲子设施、取消政策和早餐规则。",
            "- 高海拔活动对 5 岁儿童的适配性，必要时选择云杉坪/蓝月谷等低强度玩法。",
        ]
    )
    final = "\n".join(lines)
    _write_text(run_dir / "final_answer.md", final)
    return final


def run_workflow(base_host: str = "10.126.126.1") -> dict[str, Any]:
    run_dir = _ensure_run_dir("大理丽江亲子自由行")
    session_id = f"travel-{uuid4().hex[:10]}"
    _write_json(run_dir / "01_user_question.json", {"question": USER_QUESTION, "session_id": session_id})
    steps = []
    for step in AGENT_STEPS:
        step_dict = asdict(step)
        step_dict["endpoint"] = f"http://{base_host}:{step.port}/agents/{step.path_name}/rpc"
        steps.append(step_dict)
    _write_json(run_dir / "02_orchestration_plan.json", {"strategy": "sequential_pipeline_with_feedback", "steps": steps})

    outputs: dict[str, dict[str, Any]] = {}
    _event(run_dir, stage="workflow_start", state="running", message="开始 9-agent 旅行协作工作流")
    for index, step in enumerate(AGENT_STEPS, start=1):
        prompt, compression_records = build_prompt(step, outputs)
        endpoint = f"http://{base_host}:{step.port}/agents/{step.path_name}/rpc"
        step_for_call = AgentStep(
            role=step.role,
            agent_name=step.agent_name,
            port=step.port,
            path_name=step.path_name,
            objective=step.objective,
            depends_on=step.depends_on,
            timeout_seconds=step.timeout_seconds,
            host=base_host,
        )
        _write_text(run_dir / f"{index:02d}_{step.role}_prompt.txt", prompt)
        _event(run_dir, stage="agent_dispatch", state="running", role=step.role, message=f"调用 {step.agent_name}: {endpoint}")
        result = call_agent(step_for_call, prompt, session_id)
        output_text = extract_agent_text(result["payload"]) if isinstance(result.get("payload"), Mapping) else ""
        attempts = [
            {
                "attempt": 1,
                "ok": bool(result.get("ok")),
                "status_code": result.get("status_code"),
                "result_state": result.get("result_state"),
                "duration_ms": result.get("duration_ms"),
                "output_length": len(output_text),
                "error": result.get("error"),
            }
        ]
        if not _usable_agent_response(result, output_text):
            retry_prompt, retry_compression_records = build_prompt(step, outputs, retry=True)
            retry_step_for_call = AgentStep(
                role=step.role,
                agent_name=step.agent_name,
                port=step.port,
                path_name=step.path_name,
                objective=step.objective,
                depends_on=step.depends_on,
                timeout_seconds=step.retry_timeout_seconds,
                host=base_host,
                output_limit_chars=step.output_limit_chars,
                retry_timeout_seconds=step.retry_timeout_seconds,
            )
            _write_text(run_dir / f"{index:02d}_{step.role}_retry_prompt.txt", retry_prompt)
            _write_json(run_dir / f"{index:02d}_{step.role}_attempt1_raw_response.json", result)
            _event(
                run_dir,
                stage="agent_retry",
                state="running",
                role=step.role,
                message=f"{step.agent_name} 首次未得到可用结果，执行快速重试",
            )
            retry_result = call_agent(retry_step_for_call, retry_prompt, session_id)
            retry_output_text = (
                extract_agent_text(retry_result["payload"])
                if isinstance(retry_result.get("payload"), Mapping)
                else ""
            )
            attempts.append(
                {
                    "attempt": 2,
                    "ok": bool(retry_result.get("ok")),
                    "status_code": retry_result.get("status_code"),
                    "result_state": retry_result.get("result_state"),
                    "duration_ms": retry_result.get("duration_ms"),
                    "output_length": len(retry_output_text),
                    "error": retry_result.get("error"),
                }
            )
            if _usable_agent_response(retry_result, retry_output_text):
                result = retry_result
                output_text = retry_output_text
                compression_records = retry_compression_records
            elif retry_output_text and not output_text:
                result = retry_result
                output_text = retry_output_text
                compression_records = retry_compression_records
        record = {
            "index": index,
            "role": step.role,
            "agent_name": step.agent_name,
            "endpoint": endpoint,
            "depends_on": list(step.depends_on),
            "compression": compression_records,
            "ok": _usable_agent_response(result, output_text),
            "status_code": result.get("status_code"),
            "result_state": result.get("result_state"),
            "duration_ms": result.get("duration_ms"),
            "error": result.get("error"),
            "attempts": attempts,
            "output_length": len(output_text),
            "output_text": output_text,
        }
        outputs[step.role] = record
        _write_json(run_dir / f"{index:02d}_{step.role}_raw_response.json", result)
        _write_json(run_dir / f"{index:02d}_{step.role}_result.json", record)
        _write_text(run_dir / f"{index:02d}_{step.role}_output.txt", output_text or str(result.get("error") or ""))
        _event(
            run_dir,
            stage="agent_complete" if record["ok"] else "agent_failed",
            state="done" if record["ok"] else "warning",
            role=step.role,
            message=f"{step.agent_name} 输出 {len(output_text)} 字符，耗时 {record['duration_ms']} ms",
        )

    artifacts = {
        "interactive_page": build_interactive_html(run_dir, outputs),
        "report_page": build_report_html(run_dir, outputs),
    }
    final_answer = build_final_markdown(run_dir, outputs, artifacts)
    summary = {
        "run_dir": str(run_dir),
        "session_id": session_id,
        "all_agents_called": len(outputs) == len(AGENT_STEPS),
        "agent_statuses": {
            role: {
                "ok": bool(result.get("ok")),
                "status_code": result.get("status_code"),
                "result_state": result.get("result_state"),
                "output_length": result.get("output_length", 0),
                "attempts": result.get("attempts", []),
            }
            for role, result in outputs.items()
        },
        "successful_agents": [role for role, result in outputs.items() if result.get("ok")],
        "failed_agents": [role for role, result in outputs.items() if not result.get("ok")],
        "artifacts": artifacts,
        "final_answer_path": str(run_dir / "final_answer.md"),
        "final_answer_length": len(final_answer),
    }
    _write_json(run_dir / "summary.json", summary)
    _event(run_dir, stage="workflow_complete", state="done", message=f"完成 9-agent 协作，结果目录：{run_dir}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the 9-agent Dali/Lijiang travel collaboration workflow.")
    parser.add_argument("--base-host", default="10.126.126.1")
    args = parser.parse_args()
    summary = run_workflow(base_host=args.base_host)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not summary["failed_agents"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
