from __future__ import annotations

import argparse
import ast
import concurrent.futures
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse
from uuid import uuid4

from adapters import normalize_request_payload
from discovery_client import DiscoveryCallError, build_discovery_request, call_discovery
from generic_group_executor import execute_plan_group_chat
from mode_selector import ModeDecision, decide_mode
from orchestrator import (
    annotate_plan_with_dispatch_guards,
    build_execution_plan,
    collect_plan_agent_aics,
    execute_plan_dry_run,
    get_placeholder_connector_contract,
)
from registry_client import (
    RegistryCallError,
    call_registry_discovery,
    call_registry_agent_call_settlement,
    call_registry_dispatch,
    call_registry_public_recent,
    call_registry_runtime_review_schedule,
)
from reporting import write_report_bundle
from route_classifier import ROUTE_AGENT, ROUTE_LLM, ROUTE_MULTI_AGENT, classify_task_route
from zh import summarize_decision_zh, summarize_execution_zh, summarize_plan_zh

try:
    from monitoring.traffic_monitor import count_tokens, get_snapshot as get_traffic_snapshot
    from monitoring.traffic_monitor import record as record_traffic
    from monitoring.traffic_monitor import serialize_payload
except Exception:  # pragma: no cover - monitoring must not block the API
    count_tokens = None
    record_traffic = None
    serialize_payload = None

    def get_traffic_snapshot() -> dict[str, Any]:
        return {"enabled": False, "error": "traffic monitor is unavailable"}

SERVICE_NAME = "mode-router-service"
SERVICE_VERSION = "0.4.1"
RUNS_DIR = Path(__file__).resolve().parent / "literature_runs"
PLATFORM_RUNS_DIR = Path(__file__).resolve().parent / "platform_task_runs"
DEFAULT_DISCOVERY_URL = "http://127.0.0.1:8005/acps-adp-v2/discover"
DEFAULT_REGISTRY_URL = "http://127.0.0.1:8001"
EVENT_CENTER_URL = os.getenv("EVENT_CENTER_URL", "http://127.0.0.1:8001/api/events/publish")
EVENT_CENTER_TOKEN = os.getenv("EVENT_CENTER_TOKEN", "local-dev-token")
ROLE_ORDER = ("search", "analysis", "writing")


def _load_local_env_file() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_local_env_file()

def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _post_runtime_event(
    *,
    event_type: str,
    level: str,
    title: str,
    message: str,
    extra: Mapping[str, Any] | None = None,
) -> None:
    if not EVENT_CENTER_URL or not EVENT_CENTER_TOKEN:
        return
    payload = {
        "source": "mode-router",
        "type": event_type,
        "level": level,
        "title": title,
        "message": message,
        "extra": {"service": SERVICE_NAME, **dict(extra or {})},
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        EVENT_CENTER_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {EVENT_CENTER_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=2).read()
    except Exception:
        return


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or 0)
    raw_body = handler.rfile.read(length) if length else b"{}"
    if not raw_body:
        return {}
    return json.loads(raw_body.decode("utf-8"))


def _latest_run_dir() -> Path | None:
    if not RUNS_DIR.exists():
        return None
    run_dirs = [item for item in RUNS_DIR.iterdir() if item.is_dir()]
    if not run_dirs:
        return None
    return max(run_dirs, key=lambda item: item.stat().st_mtime)


def _latest_platform_run_dir() -> Path | None:
    if not PLATFORM_RUNS_DIR.exists():
        return None
    run_dirs = [item for item in PLATFORM_RUNS_DIR.iterdir() if item.is_dir()]
    if not run_dirs:
        return None
    return max(run_dirs, key=lambda item: item.stat().st_mtime)


def _load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def _count_states(events: list[Mapping[str, Any]]) -> dict[str, int]:
    state_counts: dict[str, int] = {}
    for event in events:
        state = str(event.get("state") or "unknown")
        state_counts[state] = state_counts.get(state, 0) + 1
    return state_counts


def _latest_events_by_role(events: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for event in events:
        role = str(event.get("role") or "")
        if role:
            latest[role] = dict(event)
    return latest


def _progress_from_checklist(checklist: Mapping[str, Any]) -> dict[str, Any]:
    steps = list(checklist.get("steps") or [])
    total = len(steps)
    done = sum(1 for item in steps if item.get("status") == "done")
    missing = sum(1 for item in steps if item.get("status") == "missing")
    return {
        "total_steps": total,
        "done_steps": done,
        "missing_steps": missing,
        "percent": round((done / total) * 100, 1) if total else 0,
    }


def _ordered_roles(*role_groups: Any) -> list[str]:
    seen: set[str] = set()
    roles: list[str] = []
    for role in ROLE_ORDER:
        seen.add(role)
        roles.append(role)
    for group in role_groups:
        if isinstance(group, Mapping):
            candidates = group.keys()
        else:
            candidates = group or []
        for role in candidates:
            role = str(role or "")
            if role and role not in seen:
                seen.add(role)
                roles.append(role)
    return roles


def _role_progress(
    *,
    role_latest: Mapping[str, Mapping[str, Any]],
    final_payload: Mapping[str, Any],
    role_agents: Mapping[str, Any],
) -> list[dict[str, Any]]:
    steps = list(final_payload.get("steps") or [])
    result_by_role = {str(item.get("role") or ""): item for item in steps if item.get("role")}
    children = list(((final_payload.get("orchestration_tree") or {}).get("children") or []))
    child_by_role = {str(item.get("role") or ""): item for item in children if item.get("role")}
    roles = _ordered_roles(role_latest, result_by_role, child_by_role, role_agents)
    progress: list[dict[str, Any]] = []
    for role in roles:
        latest = role_latest.get(role, {})
        result = result_by_role.get(role, {})
        child = child_by_role.get(role, {})
        agent = result.get("agent") or role_agents.get(role) or {}
        if not latest and not result and not child and role not in role_agents:
            continue
        progress.append(
            {
                "role": role,
                "agent_name": agent.get("name") or child.get("agent_name", ""),
                "state": latest.get("state") or result.get("final_state") or "pending",
                "stage": latest.get("stage", ""),
                "message": latest.get("message", ""),
                "task_id": latest.get("task_id") or result.get("task_id", ""),
                "final_state": result.get("final_state", ""),
                "output_length": result.get("output_length", 0),
                "depends_on_roles": result.get("depends_on_roles") or child.get("depends_on_roles") or [],
                "feedback_in_prompt": bool(result.get("feedback_in_prompt")),
                "compression_ratio": result.get("upstream_compression_ratio", 1.0),
            }
        )
    return progress


def _stage_progress(checklist: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "stage": item.get("stage", ""),
            "status": item.get("status", ""),
            "description": item.get("description", ""),
            "artifact": item.get("artifact", ""),
            "depends_on": item.get("depends_on") or [],
            "feedback_in_prompt": item.get("feedback_in_prompt"),
        }
        for item in checklist.get("steps", []) or []
    ]


def _latest_run_snapshot() -> dict[str, Any]:
    run_dir = _latest_run_dir()
    if not run_dir:
        return {
            "status": "idle",
            "message": "No runs found yet.",
            "runs_root": str(RUNS_DIR),
            "events": [],
        }

    events = _load_jsonl(run_dir / "12_state_events.jsonl")
    latest_event = events[-1] if events else {}
    state_counts = _count_states(events)
    role_latest = _latest_events_by_role(events)

    request = _load_json_if_exists(run_dir / "01_user_request.json")
    decision = _load_json_if_exists(run_dir / "06_mode_decision.json")
    plan = _load_json_if_exists(run_dir / "07_orchestrator_plan.json")
    checklist = _load_json_if_exists(run_dir / "08e_workflow_checklist.json")
    final_payload = _load_json_if_exists(run_dir / "09_full_data_flow.json")
    role_agents = _load_json_if_exists(run_dir / "08_role_agents.json")
    stored_status = _load_json_if_exists(run_dir / "13_run_status_summary.json")
    completed = bool(final_payload)
    progress = stored_status.get("progress") or _progress_from_checklist(checklist)
    role_progress = stored_status.get("roles") or _role_progress(
        role_latest=role_latest,
        final_payload=final_payload,
        role_agents=role_agents,
    )
    current = stored_status.get("current") or {
        "stage": latest_event.get("stage", ""),
        "state": latest_event.get("state", ""),
        "message": latest_event.get("message", ""),
        "timestamp": latest_event.get("timestamp", ""),
    }
    status = stored_status.get("status") or ("running" if not completed else "done")

    return {
        "status": status,
        "run_directory": str(run_dir),
        "task": request.get("task", ""),
        "decision": {
            "mode": decision.get("mode", ""),
            "summary": decision.get("summary", ""),
        },
        "plan": {
            "strategy": plan.get("strategy", ""),
            "summary": plan.get("summary", ""),
            "child_count": len(plan.get("work_packages", []) or []),
        },
        "checklist": checklist,
        "latest_event": latest_event,
        "state_counts": state_counts,
        "role_latest": role_latest,
        "current": current,
        "progress": progress,
        "role_progress": role_progress,
        "stage_progress": _stage_progress(checklist),
        "operator_summary": {
            "headline": f"{status} · {progress.get('percent', 0)}% · {len(role_progress)} roles",
            "current_message": current.get("message", ""),
            "event_count": len(events),
        },
        "events": events[-60:],
        "completed": completed,
        "final_length": len(str(final_payload.get("final_result", ""))) if completed else 0,
    }


def _latest_platform_snapshot() -> dict[str, Any]:
    run_dir = _latest_platform_run_dir()
    if not run_dir:
        return {
            "status": "idle",
            "message": "No platform task dry-run found yet.",
            "runs_root": str(PLATFORM_RUNS_DIR),
        }
    snapshot = _load_json_if_exists(run_dir / "08_processing_flow.json")
    if not snapshot:
        return {
            "status": "unknown",
            "run_directory": str(run_dir),
            "message": "Latest platform dry-run exists but has no processing flow file.",
        }
    return snapshot


def _monitor_page(snapshot: Mapping[str, Any]) -> str:
    snapshot_json = json.dumps(snapshot, ensure_ascii=False)
    template = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Demo 实时状态</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0d1117;
      --panel: #161b22;
      --panel-2: #0f1520;
      --text: #e6edf3;
      --muted: #9da7b3;
      --line: #2b3440;
    }
    body { margin: 0; background: var(--bg); color: var(--text); font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif; }
    .wrap { max-width: 1280px; margin: 0 auto; padding: 20px; }
    .top { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 16px; }
    h1 { font-size: 22px; margin: 0; }
    .sub { color: var(--muted); font-size: 13px; }
    .grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 12px; }
    .card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 12px; min-height: 86px; }
    .label { color: var(--muted); font-size: 12px; margin-bottom: 8px; }
    .value { font-size: 15px; line-height: 1.45; word-break: break-word; }
    .pill { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; border: 1px solid var(--line); }
    .pill.running { background: rgba(88,166,255,0.16); color: #9ecbff; }
    .pill.done { background: rgba(46,160,67,0.16); color: #8ddb8c; }
    .pill.idle { background: rgba(157,167,179,0.12); color: var(--muted); }
    .pill.assigned { background: rgba(210,153,34,0.16); color: #f2c36b; }
    .pill.waiting_summary { background: rgba(126,231,135,0.14); color: #9af0a6; }
    .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; margin-top: 12px; }
    .panel-head { display:flex; justify-content:space-between; align-items:center; padding: 12px; border-bottom: 1px solid var(--line); background: var(--panel-2); }
    .panel-head h2 { font-size: 15px; margin:0; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: top; text-align: left; }
    th { color: var(--muted); background: var(--panel-2); position: sticky; top: 0; z-index: 1; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
    .small { font-size: 12px; color: var(--muted); }
    .countbar { display: flex; gap: 8px; flex-wrap: wrap; }
    .count { border: 1px solid var(--line); border-radius: 999px; padding: 4px 10px; font-size: 12px; background: var(--panel-2); }
    .progress-track { height: 8px; border-radius: 999px; background: var(--panel-2); border: 1px solid var(--line); overflow: hidden; margin-top: 8px; }
    .progress-fill { height: 100%; width: 0%; background: #58a6ff; transition: width .2s ease; }
    .role-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; padding: 12px; }
    .role-card { border: 1px solid var(--line); border-radius: 8px; background: var(--panel-2); padding: 10px 12px; min-height: 108px; }
    .role-title { display:flex; justify-content:space-between; align-items:center; gap: 10px; margin-bottom: 8px; }
    .role-meta { display:grid; gap: 4px; font-size: 12px; color: var(--muted); }
    .checklist { display: grid; gap: 8px; padding: 12px; }
    .check-item { border: 1px solid var(--line); border-radius: 8px; background: var(--panel-2); padding: 10px 12px; }
    .check-title { display:flex; justify-content:space-between; gap: 12px; align-items: center; margin-bottom: 6px; }
    .check-title strong { font-size: 13px; }
    .check-meta { font-size: 12px; color: var(--muted); }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr 1fr; } }
    @media (max-width: 640px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="top">
      <div>
        <h1>Demo 实时状态</h1>
        <div class="sub">自动刷新，每 1 秒更新一次</div>
      </div>
      <div class="pill idle" id="status-pill">idle</div>
    </div>

    <div class="grid">
      <div class="card"><div class="label">任务</div><div class="value" id="task">暂无任务</div></div>
      <div class="card"><div class="label">运行目录</div><div class="value mono" id="run-directory">-</div></div>
      <div class="card"><div class="label">模式 / 策略</div><div class="value" id="decision">- / -</div></div>
      <div class="card">
        <div class="label">整体进度</div>
        <div class="value" id="progress-text">0/0 (0%)</div>
        <div class="progress-track"><div class="progress-fill" id="progress-fill"></div></div>
      </div>
    </div>

    <div class="grid">
      <div class="card"><div class="label">状态计数</div><div class="countbar" id="state-counts"></div></div>
      <div class="card"><div class="label">最新状态</div><div class="value" id="latest-state">-</div></div>
      <div class="card"><div class="label">当前阶段</div><div class="value" id="current-stage">-</div></div>
      <div class="card"><div class="label">完成情况</div><div class="value" id="completion">进行中</div></div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <h2>角色进度</h2>
        <div class="small" id="operator-summary">-</div>
      </div>
      <div class="role-grid" id="role-progress"></div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <h2>阶段清单</h2>
        <div class="small" id="latest-message">-</div>
      </div>
      <div class="checklist" id="checklist"></div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <h2>事件流</h2>
        <div class="small">最近 60 条状态事件</div>
      </div>
      <table>
        <thead>
          <tr>
            <th style="width: 180px;">时间</th>
            <th style="width: 110px;">状态</th>
            <th style="width: 150px;">阶段</th>
            <th style="width: 120px;">角色</th>
            <th style="width: 180px;">智能体</th>
            <th>消息</th>
          </tr>
        </thead>
        <tbody id="events-body">
          <tr><td colspan="6" class="small">等待状态事件...</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <script>
    window.__INITIAL_SNAPSHOT__ = __SNAPSHOT__;

    function pillClass(state) {
      return 'pill ' + (state || 'idle');
    }

    function esc(text) {
      return (text ?? '').toString()
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }

    function render(snapshot) {
      const latestState = snapshot.latest_event?.state || 'idle';
      const statusPill = document.getElementById('status-pill');
      statusPill.className = pillClass(latestState);
      statusPill.textContent = snapshot.status || 'idle';

      document.getElementById('task').textContent = snapshot.task || '暂无任务';
      document.getElementById('run-directory').textContent = snapshot.run_directory || '-';
      document.getElementById('decision').textContent = `${snapshot.decision?.mode || '-'} / ${snapshot.plan?.strategy || '-'}`;
      document.getElementById('latest-state').textContent = latestState || '-';
      document.getElementById('current-stage').textContent = snapshot.current?.stage || snapshot.latest_event?.stage || '-';
      document.getElementById('latest-message').textContent = snapshot.current?.message || snapshot.latest_event?.message || '-';

      const progress = snapshot.progress || {};
      const percent = Number(progress.percent || 0);
      document.getElementById('progress-text').textContent = `${progress.done_steps || 0}/${progress.total_steps || 0} (${percent}%)`;
      document.getElementById('progress-fill').style.width = Math.max(0, Math.min(100, percent)) + '%';
      const finalLength = snapshot.final_length ? ` · 结果 ${snapshot.final_length} 字符` : '';
      document.getElementById('completion').textContent = (snapshot.completed ? '已完成' : '进行中') + finalLength;
      document.getElementById('operator-summary').textContent = snapshot.operator_summary?.headline || '-';

      const counts = document.getElementById('state-counts');
      counts.innerHTML = '';
      const stateCounts = snapshot.state_counts || {};
      const entries = Object.entries(stateCounts);
      if (!entries.length) {
        counts.innerHTML = '<span class="small">暂无状态事件</span>';
      } else {
        entries.sort((a, b) => a[0].localeCompare(b[0]));
        for (const [state, count] of entries) {
          const el = document.createElement('span');
          el.className = 'count';
          el.textContent = `${state}: ${count}`;
          counts.appendChild(el);
        }
      }

      const roleBox = document.getElementById('role-progress');
      const roles = snapshot.role_progress || [];
      if (!roles.length) {
        roleBox.innerHTML = '<div class="small">暂无角色进度</div>';
      } else {
        roleBox.innerHTML = roles.map(role => `
          <div class="role-card">
            <div class="role-title">
              <strong class="mono">${esc(role.role || '')}</strong>
              <span class="pill ${esc(role.state || 'idle')}">${esc(role.state || '')}</span>
            </div>
            <div class="role-meta">
              <div>${esc(role.agent_name || '-')}</div>
              <div>阶段：${esc(role.stage || '-')}</div>
              <div>依赖：${esc((role.depends_on_roles || []).join(', ') || '无')}</div>
              <div>输出：${esc(role.output_length || 0)} 字符 · 反馈：${role.feedback_in_prompt ? '是' : '否'}</div>
              <div>${esc(role.message || '')}</div>
            </div>
          </div>
        `).join('');
      }

      const body = document.getElementById('events-body');
      const checklist = document.getElementById('checklist');
      const checklistData = snapshot.stage_progress || snapshot.checklist?.steps || [];
      if (!checklistData.length) {
        checklist.innerHTML = '<div class="small">暂无清单</div>';
      } else {
        checklist.innerHTML = checklistData.map(item => `
          <div class="check-item">
            <div class="check-title">
              <strong>${esc(item.stage || '')}</strong>
              <span class="pill ${esc(item.status || 'idle')}">${esc(item.status || '')}</span>
            </div>
            <div class="check-meta">${esc(item.description || '')}</div>
            <div class="check-meta">产物：${esc(item.artifact || '-')}</div>
          </div>
        `).join('');
      }

      const events = snapshot.events || [];
      if (!events.length) {
        body.innerHTML = '<tr><td colspan="6" class="small">暂无事件</td></tr>';
        return;
      }
      body.innerHTML = events.slice().reverse().map(event => `
        <tr>
          <td class="mono">${esc(event.timestamp || '')}</td>
          <td><span class="pill ${esc(event.state || 'idle')}">${esc(event.state || '')}</span></td>
          <td>${esc(event.stage || '')}</td>
          <td>${esc(event.role || '')}</td>
          <td>${esc(event.agent_name || '')}</td>
          <td>${esc(event.message || '')}</td>
        </tr>
      `).join('');
    }

    async function refresh() {
      try {
        const resp = await fetch('/workflow/latest?ts=' + Date.now());
        if (!resp.ok) return;
        const snapshot = await resp.json();
        render(snapshot);
      } catch (err) {
        console.error(err);
      }
    }

    render(window.__INITIAL_SNAPSHOT__ || {});
    refresh();
    setInterval(refresh, 1000);
  </script>
</body>
</html>"""
    return template.replace('__SNAPSHOT__', snapshot_json)
def _response_shell(source: str, normalized_skill_count: int, decision: Mapping[str, Any]) -> dict[str, Any]:
    response = {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "source": source,
        "normalized_skill_count": normalized_skill_count,
        "decision": decision,
    }
    response["zh"] = {"decision": summarize_decision_zh(decision)}
    return response


def _classification_decision(task: str, route_classification: Mapping[str, Any]) -> ModeDecision:
    label = str(route_classification.get("label") or "")
    mode = str(route_classification.get("mode") or "")
    next_step = str(route_classification.get("next_step") or "")
    summary = str(route_classification.get("summary") or "")
    reasoning = list(route_classification.get("reasoning") or [])
    scores = dict(route_classification.get("scores") or {})
    return ModeDecision(
        mode=mode,
        label=label,
        next_step=next_step,
        summary=summary,
        reasoning=reasoning,
        evidence={
            "task": task,
            "route_scores": scores,
            "route_label": label,
            "route_classification": dict(route_classification),
            "relevant_skill_count": 0,
            "distinct_agent_count": 0,
            "best_agent": {"aic": "", "name": "", "skill_count": 0, "coverage": 0},
            "agent_skill_counts": {},
            "selected_skills": [],
        },
    )


def _decide_with_route_classification(
    task: str,
    skills: list[Mapping[str, Any]],
    hints: Mapping[str, Any],
    config: Mapping[str, Any],
    route_classification: Mapping[str, Any],
) -> ModeDecision:
    base_decision = decide_mode(task, skills, hints=hints, config=config)
    route_label = str(route_classification.get("label") or "")
    if route_label == ROUTE_LLM:
        return _classification_decision(task, route_classification)
    if route_label not in {ROUTE_AGENT, ROUTE_MULTI_AGENT}:
        return base_decision

    target_mode = "mode_1" if route_label == ROUTE_AGENT else "mode_2"
    target_label = "single_agent_multi_skill" if route_label == ROUTE_AGENT else "multi_agent"
    next_step = "skill_router" if route_label == ROUTE_AGENT else "orchestrator"
    evidence = {
        **dict(base_decision.evidence or {}),
        "route_scores": dict(route_classification.get("scores") or {}),
        "route_label": route_label,
        "route_classification": dict(route_classification),
    }
    route_reasoning = list(route_classification.get("reasoning") or [])
    summary = str(route_classification.get("summary") or base_decision.summary)
    if base_decision.mode == target_mode:
        summary = f"{summary} Skill evidence agrees with {target_mode}."
    else:
        summary = f"{summary} Override heuristic skill coverage from {base_decision.mode} to {target_mode}."
    return ModeDecision(
        mode=target_mode,
        label=target_label,
        next_step=next_step,
        summary=summary,
        reasoning=route_reasoning + list(base_decision.reasoning or []),
        evidence=evidence,
    )


def _finalize_response(response: dict[str, Any], save_report: bool) -> dict[str, Any]:
    if save_report:
        response["report"] = write_report_bundle(response)
    return response


def _registry_url_from_payload(payload: Mapping[str, Any]) -> str:
    return str(
        payload.get("registry_url")
        or payload.get("registryUrl")
        or payload.get("registry_base_url")
        or payload.get("registryBaseUrl")
        or os.getenv("ORCHESTRATOR_REGISTRY_URL")
        or os.getenv("REGISTRY_URL")
        or ""
    ).rstrip("/")


def _registry_token_from_payload(payload: Mapping[str, Any]) -> str:
    return str(
        payload.get("registry_token")
        or payload.get("registryToken")
        or payload.get("registry_auth_token")
        or payload.get("registryAuthToken")
        or payload.get("registry_service_token")
        or payload.get("registryServiceToken")
        or payload.get("auth_token")
        or payload.get("authToken")
        or os.getenv("ORCHESTRATOR_REGISTRY_SERVICE_TOKEN")
        or os.getenv("REGISTRY_SERVICE_TOKEN")
        or ""
    )


def _requester_user_id_from_payload(payload: Mapping[str, Any]) -> str:
    return str(
        payload.get("requester_user_id")
        or payload.get("requesterUserId")
        or payload.get("user_id")
        or payload.get("userId")
        or ""
    )


def _dispatch_views_for_plan(registry_url: str, plan: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if not registry_url or not bool(payload.get("check_dispatch", payload.get("checkDispatch", True))):
        return {}
    registry_token = _registry_token_from_payload(payload)
    requester_user_id = _requester_user_id_from_payload(payload)
    timeout = float(payload.get("timeout", 120))
    retries = int(payload.get("retries", 1))
    retry_backoff = float(payload.get("retry_backoff", payload.get("retryBackoff", 2)))
    views: dict[str, dict[str, Any]] = {}
    for aic in collect_plan_agent_aics(plan):
        try:
            views[aic] = call_registry_dispatch(
                registry_url,
                aic,
                requester_user_id=requester_user_id,
                auth_token=registry_token,
                timeout=timeout,
                retries=retries,
                retry_backoff=retry_backoff,
            )
        except RegistryCallError as exc:
            views[aic] = {
                "result": {
                    "eligibleForDispatch": True,
                    "reasons": [],
                    "status": "DISPATCH_CHECK_UNAVAILABLE",
                    "decision": "APPROVE",
                    "dispatchCheckError": str(exc),
                }
            }
    return views


def _settle_completed_agent_runs(registry_url: str, payload: Mapping[str, Any], execution: dict[str, Any]) -> dict[str, Any]:
    requester_user_id = _requester_user_id_from_payload(payload)
    if not registry_url or not requester_user_id or bool(payload.get("skip_points_settlement", payload.get("skipPointsSettlement", False))):
        return {"enabled": False, "settled": 0, "errors": []}

    registry_token = _registry_token_from_payload(payload)
    timeout = float(payload.get("points_settlement_timeout", payload.get("pointsSettlementTimeout", 10)))
    amount = payload.get("agent_call_points", payload.get("agentCallPoints", 0.7))
    settled = 0
    skipped = 0
    errors: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    for run in list(execution.get("runs") or []):
        if not isinstance(run, dict):
            continue
        if run.get("status") != "completed" or not run.get("agent_rpc_called"):
            continue
        agent_aic = str(run.get("agent_aic") or (run.get("agent") or {}).get("aic") or "").strip()
        if not agent_aic:
            continue
        settlement_payload = {
            "requester_user_id": requester_user_id,
            "agent_aic": agent_aic,
            "agent_name": str(run.get("agent_name") or (run.get("agent") or {}).get("name") or ""),
            "amount": amount,
            "execution_id": str(execution.get("execution_id") or ""),
            "run_id": str(run.get("run_id") or ""),
            "task_id": str(run.get("task_id") or ""),
        }
        try:
            result = call_registry_agent_call_settlement(
                registry_url,
                settlement_payload,
                auth_token=registry_token,
                timeout=timeout,
                retries=0,
            )
            run["points_settlement"] = result
            results.append({"agent_aic": agent_aic, "result": result})
            if result.get("settled"):
                settled += 1
            elif result.get("skipped"):
                skipped += 1
        except Exception as exc:
            error = {"agent_aic": agent_aic, "error": str(exc)}
            run["points_settlement"] = error
            errors.append(error)

    summary = {"enabled": True, "settled": settled, "skipped": skipped, "errors": errors, "results": results}
    execution["points_settlement"] = summary
    return summary


def _discovery_url_from_payload(payload: Mapping[str, Any]) -> str:
    return str(
        payload.get("discovery_url")
        or payload.get("discoveryUrl")
        or os.getenv("ORCHESTRATOR_DISCOVERY_URL")
        or DEFAULT_DISCOVERY_URL
    ).rstrip("/")


def _registry_fallback_url_from_payload(payload: Mapping[str, Any]) -> str:
    return (
        _registry_url_from_payload(payload)
        or str(payload.get("fallback_registry_url") or payload.get("fallbackRegistryUrl") or os.getenv("ORCHESTRATOR_FALLBACK_REGISTRY_URL") or DEFAULT_REGISTRY_URL).rstrip("/")
    )


def _has_candidate_payload(payload: Mapping[str, Any]) -> bool:
    candidate_keys = (
        "skills",
        "candidate_skills",
        "candidateSkills",
        "discovery_response",
        "discoveryResponse",
        "adp_response",
        "adpResponse",
        "registry_discovery_response",
        "registryDiscoveryResponse",
    )
    if any(payload.get(key) is not None for key in candidate_keys):
        return True
    result = payload.get("result")
    if isinstance(result, Mapping) and (result.get("agents") or result.get("items") or result.get("acsMap")):
        return True
    return bool(payload.get("agents"))


def _payload_prefers_discovery(payload: Mapping[str, Any]) -> bool:
    source = str(payload.get("candidate_source") or payload.get("candidateSource") or "").strip().lower()
    if source in {"discovery", "adp", "discovery_server", "acps_discovery"}:
        return True
    if source in {"registry", "registry_discovery", "registry_passport", "passport"}:
        return False
    for key in ("prefer_discovery", "preferDiscovery", "use_discovery", "useDiscovery"):
        if key in payload:
            return _truthy(payload.get(key), False)
    return _truthy(os.getenv("ACPS_DISCOVERY_V21_ENABLED"), False)


def _registry_discovery_fallback_enabled(payload: Mapping[str, Any]) -> bool:
    for key in ("registry_fallback", "registryFallback"):
        if key in payload:
            return _truthy(payload.get(key), True)
    return _truthy(os.getenv("ACPS_DISCOVERY_LEGACY_FALLBACK_ENABLED"), True)


def _payload_prefers_registry_public_recent(payload: Mapping[str, Any]) -> bool:
    source = str(payload.get("candidate_source") or payload.get("candidateSource") or "").strip().lower()
    return source in {"registry_public_recent", "public_recent", "square", "marketplace", "agent_square"}


def _registry_public_recent_fallback_enabled(payload: Mapping[str, Any]) -> bool:
    return _truthy(
        payload.get(
            "registry_public_recent_fallback",
            payload.get("registryPublicRecentFallback", payload.get("public_recent_fallback", payload.get("publicRecentFallback", True))),
        ),
        True,
    )


def _normalize_from_registry_public_recent(task: str, payload: Mapping[str, Any], registry_url: str) -> tuple[dict[str, Any], dict[str, Any]]:
    registry_response = call_registry_public_recent(
        registry_url,
        page_num=int(payload.get("registry_page_num", payload.get("registryPageNum", 1))),
        page_size=int(
            payload.get(
                "registry_page_size",
                payload.get("registryPageSize", payload.get("registry_limit", payload.get("registryLimit", payload.get("limit", 100)))),
            )
        ),
        auth_token=_registry_token_from_payload(payload),
        timeout=float(payload.get("registry_public_timeout", payload.get("registryPublicTimeout", payload.get("registry_timeout", payload.get("registryTimeout", 30))))),
        retries=int(payload.get("registry_public_retries", payload.get("registryPublicRetries", 0))),
        retry_backoff=float(payload.get("retry_backoff", payload.get("retryBackoff", 2))),
    )
    normalized = normalize_request_payload(
        {
            "task": task,
            "hints": payload.get("hints") or {},
            "config": payload.get("config") or {},
            "registry_discovery_response": registry_response,
        }
    )
    return normalized, {
        "candidate_source": "registry_public_recent",
        "registry_url": registry_url,
        "registry_public_recent_response": registry_response,
    }


def _normalize_from_registry(task: str, payload: Mapping[str, Any], registry_url: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        registry_response = call_registry_discovery(
            registry_url,
            limit=int(payload.get("registry_limit", payload.get("registryLimit", payload.get("limit", 25)))),
            requester_user_id=_requester_user_id_from_payload(payload),
            auth_token=_registry_token_from_payload(payload),
            timeout=float(payload.get("registry_timeout", payload.get("registryTimeout", payload.get("timeout", 120)))),
            retries=int(payload.get("registry_retries", payload.get("registryRetries", payload.get("retries", 1)))),
            retry_backoff=float(payload.get("retry_backoff", payload.get("retryBackoff", 2))),
        )
    except RegistryCallError as exc:
        if not _registry_public_recent_fallback_enabled(payload):
            raise
        normalized, context = _normalize_from_registry_public_recent(task, payload, registry_url)
        context["candidate_source"] = "registry_public_recent_after_registry_discovery_error"
        context["registry_discovery_error"] = str(exc)
        return normalized, context
    normalized = normalize_request_payload(
        {
            "task": task,
            "hints": payload.get("hints") or {},
            "config": payload.get("config") or {},
            "registry_discovery_response": registry_response,
        }
    )
    if not normalized["skills"] and _registry_public_recent_fallback_enabled(payload):
        public_normalized, context = _normalize_from_registry_public_recent(task, payload, registry_url)
        if public_normalized["skills"]:
            context["candidate_source"] = "registry_public_recent_after_empty_registry_discovery"
            context["registry_discovery_response"] = registry_response
            return public_normalized, context
    return normalized, {
        "candidate_source": "registry_discovery",
        "registry_url": registry_url,
        "registry_discovery_response": registry_response,
    }


def _discovery_payload_for_route(payload: Mapping[str, Any], route_classification: Mapping[str, Any] | None) -> dict[str, Any]:
    request_payload = dict(payload)
    if route_classification:
        request_payload.setdefault("route_label", route_classification.get("label"))
    label = str((route_classification or {}).get("label") or "").lower()
    if "multi" in label or "澶" in label:
        request_payload.setdefault("selection_mode", "multi_agent")
        request_payload.setdefault("min_agents", 2)
        request_payload.setdefault("limit", payload.get("discovery_limit", payload.get("discoveryLimit", payload.get("limit", 10))))
    elif label == "agent":
        request_payload.setdefault("selection_mode", "single_agent")
        request_payload.setdefault("min_agents", 1)
        request_payload.setdefault("limit", payload.get("discovery_limit", payload.get("discoveryLimit", payload.get("limit", 1))))
    else:
        request_payload.setdefault("limit", payload.get("discovery_limit", payload.get("discoveryLimit", payload.get("limit", 10))))
    return request_payload


def _normalize_execute_candidates(
    task: str,
    payload: Mapping[str, Any],
    route_classification: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if _has_candidate_payload(payload):
        candidate_payload = dict(payload)
        if "candidateSkills" in candidate_payload and "candidate_skills" not in candidate_payload:
            candidate_payload["candidate_skills"] = candidate_payload["candidateSkills"]
        return normalize_request_payload(candidate_payload), {"candidate_source": "request_payload"}

    prefer_discovery = _payload_prefers_discovery(payload)
    route_label = str((route_classification or {}).get("label") or "")
    registry_url = _registry_url_from_payload(payload) or DEFAULT_REGISTRY_URL
    if registry_url and _payload_prefers_registry_public_recent(payload):
        return _normalize_from_registry_public_recent(task, payload, registry_url)
    if registry_url and not prefer_discovery:
        return _normalize_from_registry(task, payload, registry_url)

    discovery_url = _discovery_url_from_payload(payload)
    discovery_payload = _discovery_payload_for_route(payload, route_classification)
    discovery_request = build_discovery_request(task, discovery_payload)
    try:
        discovery_response = call_discovery(
            discovery_url,
            discovery_request,
            timeout=float(payload.get("discovery_timeout", payload.get("discoveryTimeout", payload.get("timeout", 120)))),
            retries=int(payload.get("discovery_retries", payload.get("discoveryRetries", payload.get("retries", 1)))),
            retry_backoff=float(payload.get("retry_backoff", payload.get("retryBackoff", 2))),
        )
        normalized = normalize_request_payload(
            {
                "task": task,
                "hints": payload.get("hints") or {},
                "config": payload.get("config") or {},
                "discovery_response": discovery_response,
            }
        )
    except (DiscoveryCallError, ValueError) as exc:
        if not _registry_discovery_fallback_enabled(payload):
            raise
        fallback_registry_url = _registry_fallback_url_from_payload(payload)
        if not fallback_registry_url:
            raise
        normalized, context = _normalize_from_registry(task, payload, fallback_registry_url)
        context["candidate_source"] = "registry_fallback_after_discovery_error"
        context["discovery_error"] = str(exc)
        context["discovery_url"] = discovery_url
        context["discovery_request"] = discovery_request
        return normalized, context
    if not normalized["skills"] and _registry_discovery_fallback_enabled(payload):
        fallback_registry_url = _registry_fallback_url_from_payload(payload)
        if fallback_registry_url:
            fallback_normalized, context = _normalize_from_registry(task, payload, fallback_registry_url)
            if fallback_normalized["skills"]:
                context["candidate_source"] = "registry_fallback_after_empty_discovery"
                context["discovery_url"] = discovery_url
                context["discovery_request"] = discovery_request
                context["discovery_response"] = discovery_response
                return fallback_normalized, context
    return normalized, {
        "candidate_source": "discovery",
        "registry_url": registry_url,
        "discovery_url": discovery_url,
        "discovery_request": discovery_request,
        "discovery_response": discovery_response,
    }


def _skip_execution(plan: Mapping[str, Any], message: str) -> dict[str, Any]:
    return {
        "execution_id": "",
        "plan_id": plan.get("plan_id"),
        "status": "skipped",
        "mode": plan.get("mode"),
        "strategy": plan.get("strategy"),
        "dry_run": False,
        "group_chat": False,
        "runs": [],
        "message": message,
    }


def _blocked_execution(plan: Mapping[str, Any], message: str) -> dict[str, Any]:
    return {
        "execution_id": "",
        "plan_id": plan.get("plan_id"),
        "status": "blocked",
        "mode": plan.get("mode"),
        "strategy": plan.get("strategy"),
        "dry_run": False,
        "group_chat": False,
        "runs": [],
        "message": message,
    }


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


def _record_mode2_payload_traffic(
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
    group_chat: bool = False,
    transport: str = "http_jsonrpc",
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
            group_chat=group_chat,
            transport=transport,
            session_id=session_id,
            execution_id=execution_id,
            package_id=package_id,
            task_id=task_id,
        )
        return tokens
    except Exception:
        return 0


def _preferred_http_endpoint_from_acs(acs: Mapping[str, Any]) -> Mapping[str, Any]:
    endpoints = acs.get("endPoints") or acs.get("endpoints") or []
    if not isinstance(endpoints, list) or not endpoints:
        return {}
    priority = {"JSONRPC": 0, "HTTP_JSON": 1, "HTTP": 2, "": 3}
    candidates: list[tuple[int, int, Mapping[str, Any]]] = []
    for index, endpoint in enumerate(endpoints):
        if not isinstance(endpoint, Mapping):
            continue
        url = str(endpoint.get("url") or endpoint.get("href") or "").strip()
        transport = str(endpoint.get("transport") or "").strip().upper()
        if url.startswith(("http://", "https://")) and transport in priority:
            candidates.append((priority[transport], index, endpoint))
    return min(candidates, key=lambda item: (item[0], item[1]))[2] if candidates else {}


def _first_endpoint_url_from_acs(acs: Mapping[str, Any]) -> str:
    endpoint = _preferred_http_endpoint_from_acs(acs)
    return str(endpoint.get("url") or endpoint.get("href") or "").strip()


def _endpoint_index_from_skills(skills: list[Mapping[str, Any]]) -> dict[str, str]:
    endpoints: dict[str, str] = {}
    for skill in skills:
        if not isinstance(skill, Mapping):
            continue
        aic = str(skill.get("aic") or skill.get("agent_id") or "").strip()
        if not aic or aic in endpoints:
            continue
        acs = skill.get("acs") or skill.get("acp") or skill.get("parent_agent") or {}
        if isinstance(acs, Mapping):
            endpoint = _first_endpoint_url_from_acs(acs)
            if endpoint:
                endpoints[aic] = endpoint
    return endpoints


def _acs_index_from_skills(skills: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    acs_by_aic: dict[str, dict[str, Any]] = {}
    for skill in skills:
        if not isinstance(skill, Mapping):
            continue
        aic = str(skill.get("aic") or skill.get("agent_id") or "").strip()
        acs = skill.get("acs") or skill.get("acp") or skill.get("parent_agent") or {}
        if aic and aic not in acs_by_aic and isinstance(acs, Mapping):
            acs_by_aic[aic] = dict(acs)
    return acs_by_aic


def _agent_url_from_mapping(agent: Mapping[str, Any]) -> str:
    endpoint = str(agent.get("url") or agent.get("endpoint") or "").strip()
    if endpoint:
        return endpoint
    return _first_endpoint_url_from_acs(agent)


def _enrich_plan_agent_endpoints(plan: dict[str, Any], skills: list[Mapping[str, Any]]) -> dict[str, Any]:
    endpoint_by_aic = _endpoint_index_from_skills(skills)
    acs_by_aic = _acs_index_from_skills(skills)
    if not endpoint_by_aic and not acs_by_aic:
        return plan

    agents: list[dict[str, Any]] = []
    primary_agent = plan.get("primary_agent")
    if isinstance(primary_agent, dict):
        agents.append(primary_agent)
    for package in plan.get("work_packages") or []:
        if not isinstance(package, dict):
            continue
        agent = package.get("agent")
        if isinstance(agent, dict):
            agents.append(agent)

    for agent in agents:
        aic = str(agent.get("aic") or "").strip()
        if aic and not _agent_url_from_mapping(agent) and endpoint_by_aic.get(aic):
            agent["url"] = endpoint_by_aic[aic]
        if aic and "acs" not in agent and acs_by_aic.get(aic):
            agent["acs"] = dict(acs_by_aic[aic])
    return plan


def _mode1_agent_url(package: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    override = str(payload.get("agent_url") or payload.get("agentUrl") or "").strip()
    if override:
        return override
    agent = package.get("agent") if isinstance(package.get("agent"), Mapping) else {}
    endpoint = _agent_url_from_mapping(agent)
    if endpoint:
        return endpoint
    return str(package.get("url") or package.get("endpoint") or "").strip()


def _mode1_agent_name(package: Mapping[str, Any]) -> str:
    agent = package.get("agent") if isinstance(package.get("agent"), Mapping) else {}
    return str(agent.get("name") or agent.get("aic") or package.get("package_id") or "").strip()


def _mode1_agent_aic(package: Mapping[str, Any]) -> str:
    agent = package.get("agent") if isinstance(package.get("agent"), Mapping) else {}
    return str(agent.get("aic") or "").strip()


def _extract_text_from_items(items: Any) -> str:
    if not isinstance(items, list):
        return ""
    chunks: list[str] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        if item.get("text"):
            chunks.append(str(item["text"]))
        elif item.get("content"):
            chunks.append(str(item["content"]))
        elif item.get("data") is not None:
            chunks.append(json.dumps(item.get("data"), ensure_ascii=False, indent=2))
        elif item.get("uri"):
            chunks.append(str(item["uri"]))
    return "\n\n".join(chunk for chunk in chunks if chunk)


def _task_result_state(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        return ""
    result = payload.get("result") if isinstance(payload.get("result"), Mapping) else payload
    if not isinstance(result, Mapping):
        return ""
    status = result.get("status")
    if isinstance(status, Mapping):
        return str(status.get("state") or "").strip().lower()
    return ""


def _task_state_in_progress(state: str) -> bool:
    return str(state or "").strip().lower() in {
        "accepted",
        "assigned",
        "pending",
        "queued",
        "running",
        "working",
        "processing",
        "in-progress",
        "in_progress",
    }


def _task_state_terminal(state: str) -> bool:
    return str(state or "").strip().lower() in {
        "awaiting-completion",
        "completed",
        "failed",
        "rejected",
        "canceled",
        "cancelled",
    }


def _looks_like_process_note(text: str) -> bool:
    stripped = re.sub(r"\s+", " ", str(text or "")).strip().lower()
    if not stripped:
        return False
    process_starts = (
        "now i ",
        "now i'll ",
        "now let me ",
        "let me ",
        "i need to ",
        "i will ",
        "i'll ",
        "i have all the data",
    )
    return any(stripped.startswith(prefix) for prefix in process_starts) and len(stripped) < 800


def _extract_agent_output(payload: Any, *, include_status_text: bool = True) -> str:
    if not isinstance(payload, Mapping):
        return str(payload)
    if payload.get("error"):
        return "Agent RPC error: " + json.dumps(payload["error"], ensure_ascii=False)

    def _text_from_task_result(obj: Any) -> str:
        if not isinstance(obj, Mapping):
            return ""
        products = obj.get("products") or []
        if isinstance(products, list):
            for product in products:
                if isinstance(product, Mapping):
                    text = (
                        str(product.get("content"))
                        if product.get("content")
                        else _extract_text_from_items(product.get("dataItems") or product.get("data_items"))
                    )
                    if text:
                        return text
        text = _extract_text_from_items(obj.get("dataItems") or obj.get("data_items"))
        if text:
            return text
        if obj.get("content"):
            return str(obj["content"])
        if obj.get("text"):
            return str(obj["text"])
        if include_status_text:
            status = obj.get("status")
            if isinstance(status, Mapping):
                return _extract_text_from_items(status.get("dataItems") or status.get("data_items"))
        return ""

    result = payload.get("result")
    if isinstance(result, Mapping):
        text = _text_from_task_result(result)
        if text:
            return text
        products = result.get("products") or []
        if isinstance(products, list):
            for product in products:
                if not isinstance(product, Mapping):
                    continue
                content = product.get("content")
                if content:
                    return str(content)
                data_items = product.get("dataItems") or product.get("data_items") or []
                text = _extract_text_from_items(data_items)
                if text:
                    return text
        text = _extract_text_from_items(result.get("dataItems") or result.get("data_items") or [])
        if text:
            return text
        if result.get("content"):
            return str(result["content"])
        if result.get("text"):
            return str(result["text"])
        if include_status_text:
            status = result.get("status")
            if isinstance(status, Mapping):
                text = _extract_text_from_items(status.get("dataItems") or status.get("data_items"))
                if text:
                    return text
        if isinstance(result.get("status"), Mapping):
            return ""
        if result.get("type") == "task-result":
            return ""
        return json.dumps(result, ensure_ascii=False)
    text = _text_from_task_result(payload)
    if text:
        return text
    if payload.get("content"):
        return str(payload["content"])
    if payload.get("text"):
        return str(payload["text"])
    if payload.get("type") == "task-result":
        return ""
    return json.dumps(payload, ensure_ascii=False)


def _command_text_data_items(text: str) -> list[dict[str, str]]:
    return [{"type": "text", "text": str(text or "")}]


def _json_preview(value: Any, limit: int = 12000) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=2) if not isinstance(value, str) else str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]..."


def _package_role_contract(package: Mapping[str, Any]) -> str:
    roles = [str(role).lower() for role in list(package.get("inferred_roles") or [])]
    primary = roles[0] if roles else ""
    if primary == "collect":
        return "Output structured POI/source data only: names, categories, addresses, notes, and confidence/source notes. Do not create the final HTML."
    if primary == "geo":
        return "Output map-ready coordinates, route/geography facts, distances, and route notes. Do not create the final HTML."
    if primary == "itinerary":
        return "Output the itinerary plan only: days, time blocks, route order, meals, backup suggestions, and assumptions."
    if primary == "content":
        return "Output social-media copy only, especially route-related Xiaohongshu titles, body copy, and hashtags. Do not create the final HTML."
    if primary == "budget":
        return "Output budget/cost estimates only, with assumptions and ranges. Do not create the final HTML."
    if primary == "report":
        return "Output a travel guide/report artifact that integrates upstream findings. Do not create frontend code unless explicitly requested for this package."
    if primary == "frontend":
        return "Output the final visual artifact as a complete single-file HTML document. Integrate upstream POI, route, itinerary, and copywriting outputs. Put the full HTML source directly in the RPC result text/product; do not return only a local file path."
    if primary == "qa":
        return "Output a quality review only: issues, checks performed, and pass/fail notes. Do not rewrite the final artifact unless requested."
    return "Output only the artifact for this work package. Do not pretend to run other agents or replace the root orchestrator."


def _mode2_package_prompt(task: str, package: Mapping[str, Any], upstream_outputs: Mapping[str, str]) -> str:
    agent = package.get("agent") if isinstance(package.get("agent"), Mapping) else {}
    upstream_text = "\n\n".join(
        f"### {package_id}\n{output}"
        for package_id, output in upstream_outputs.items()
        if output
    )
    return (
        "You are being called by a generic multi-agent orchestrator through HTTP JSON-RPC.\n"
        "Complete only the current work package assigned to your registered agent capability.\n\n"
        f"Original user task:\n{task}\n\n"
        f"Current agent: {agent.get('name') or agent.get('aic') or 'unknown'}\n"
        f"Current package_id: {package.get('package_id') or ''}\n"
        f"Inferred package roles: {', '.join(str(role) for role in list(package.get('inferred_roles') or [])) or 'unknown'}\n"
        f"Current objective:\n{package.get('objective') or ''}\n\n"
        f"Selected skills:\n{_json_preview(package.get('skills') or [], limit=4000)}\n\n"
        f"Output contract:\n{_package_role_contract(package)}\n\n"
        f"Upstream outputs available to this package:\n{upstream_text if upstream_text else '(none)'}\n\n"
        "Return the actual deliverable content in your task result/product. If you create a file, also paste the complete user-facing content or source code into the RPC result. Avoid progress narration such as \"Now I will...\" unless it is followed by the deliverable."
    )


def _mode1_package_prompt(task: str, package: Mapping[str, Any]) -> str:
    agent = package.get("agent") if isinstance(package.get("agent"), Mapping) else {}
    return (
        "You are being called by a generic orchestrator through HTTP JSON-RPC.\n"
        "Complete the user task end-to-end with your registered capability.\n\n"
        f"Original user task:\n{task}\n\n"
        f"Current agent: {agent.get('name') or agent.get('aic') or 'unknown'}\n"
        f"Current objective:\n{package.get('objective') or ''}\n\n"
        f"Selected skills:\n{_json_preview(package.get('skills') or [], limit=4000)}\n\n"
        "Return the actual final deliverable in the RPC result text/product. If you create a file, also paste the complete user-facing content or source code into the RPC result; do not return only a local file path."
    )


def _agent_rpc_command(*, task_id: str, command: str, payload: Mapping[str, Any], text: str = "") -> dict[str, Any]:
    sender_role = str(
        payload.get("agent_sender_role")
        or payload.get("agentSenderRole")
        or payload.get("sender_role")
        or payload.get("senderRole")
        or "leader"
    )
    if sender_role not in {"leader", "partner"}:
        sender_role = "leader"
    command_payload: dict[str, Any] = {
        "type": "task-command",
        "id": f"{task_id}-{command}-{uuid4().hex[:8]}",
        "taskId": task_id,
        "sentAt": _utc_now(),
        "senderRole": sender_role,
        "senderId": str(payload.get("leader_aic") or payload.get("leaderAic") or "mode-router"),
        "command": command,
        "dataItems": _command_text_data_items(text) if text else [],
    }
    if command == "start":
        max_products_bytes = int(payload.get("max_products_bytes", payload.get("maxProductsBytes", 2_000_000)) or 2_000_000)
        command_payload["commandParams"] = {"maxProductsBytes": max_products_bytes}
    return {
        "jsonrpc": "2.0",
        "id": f"agent-{uuid4().hex[:10]}",
        "method": str(payload.get("agent_rpc_method") or payload.get("agentRpcMethod") or "rpc"),
        "params": {"command": command_payload},
    }


def _mode1_agent_rpc_payload(task: str, package: Mapping[str, Any], payload: Mapping[str, Any], task_id: str) -> dict[str, Any]:
    prompt = _mode1_package_prompt(task, package)
    request = _agent_rpc_command(task_id=task_id, command="start", payload=payload, text=prompt)
    request["params"].update(
        {
            "text": task,
            "task": task,
            "objective": package.get("objective") or "",
            "skills": list(package.get("skills") or []),
            "package": dict(package),
        }
    )
    return request


def _agent_rpc_payload(
    task: str,
    package: Mapping[str, Any],
    payload: Mapping[str, Any],
    task_id: str,
    upstream_outputs: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    upstream_outputs = upstream_outputs or {}
    upstream_text = "\n\n".join(
        f"### {package_id}\n{output}"
        for package_id, output in upstream_outputs.items()
        if output
    )
    command_text = task
    if upstream_text:
        command_text = f"{task}\n\n上游产物:\n{upstream_text}"
    sender_role = str(
        payload.get("agent_sender_role")
        or payload.get("agentSenderRole")
        or payload.get("sender_role")
        or payload.get("senderRole")
        or "leader"
    )
    if sender_role not in {"leader", "partner"}:
        sender_role = "leader"
    return {
        "jsonrpc": "2.0",
        "id": f"agent-{uuid4().hex[:10]}",
        "method": str(payload.get("agent_rpc_method") or payload.get("agentRpcMethod") or "rpc"),
        "params": {
            "command": {
                "type": "task-command",
                "id": task_id,
                "taskId": task_id,
                "sentAt": _utc_now(),
                "senderRole": sender_role,
                "senderId": str(payload.get("leader_aic") or payload.get("leaderAic") or "mode-router"),
                "command": "start",
                "dataItems": _command_text_data_items(command_text),
            },
            "text": task,
            "task": task,
            "objective": package.get("objective") or "",
            "skills": list(package.get("skills") or []),
            "package": dict(package),
            "upstream": upstream_text,
            "upstream_outputs": dict(upstream_outputs),
        },
    }


def _agent_rpc_payload(
    task: str,
    package: Mapping[str, Any],
    payload: Mapping[str, Any],
    task_id: str,
    upstream_outputs: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    upstream_outputs = upstream_outputs or {}
    command_text = _mode2_package_prompt(task, package, upstream_outputs)
    request = _agent_rpc_command(task_id=task_id, command="start", payload=payload, text=command_text)
    request["params"].update(
        {
            "text": task,
            "task": task,
            "objective": package.get("objective") or "",
            "skills": list(package.get("skills") or []),
            "package": dict(package),
            "upstream": command_text,
            "upstream_outputs": dict(upstream_outputs),
        }
    )
    return request


def _post_json(url: str, body: Mapping[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def _float_from_payload(payload: Mapping[str, Any], keys: Iterable[str], default: float | None) -> float | None:
    for key in keys:
        if key in payload and payload.get(key) not in (None, ""):
            raw = payload.get(key)
            if isinstance(raw, str) and raw.strip().lower() in {"none", "null", "unlimited", "infinite", "inf", "false"}:
                return None
            try:
                return float(raw)
            except (TypeError, ValueError):
                return default
    return default


def _agent_timeout_from_payload(payload: Mapping[str, Any], *, default: float | None = 480.0, max_default: float = 600.0) -> float | None:
    explicit_keys = (
        "agent_timeout",
        "agentTimeout",
        "mode_agent_timeout",
        "modeAgentTimeout",
    )
    if any(key in payload and payload.get(key) not in (None, "") for key in explicit_keys):
        explicit_timeout = _float_from_payload(payload, explicit_keys, default)
        if explicit_timeout is None or explicit_timeout <= 0:
            return None
        return max(1.0, explicit_timeout)
    generic_timeout = _float_from_payload(payload, ("timeout",), default)
    if generic_timeout is None or generic_timeout <= 0:
        return None
    return max(1.0, min(generic_timeout, max_default))


def _execution_timeout_from_payload(payload: Mapping[str, Any], *, default: float | None = 600.0, max_default: float = 1800.0) -> float | None:
    explicit_keys = (
        "execution_timeout",
        "executionTimeout",
        "mode_execution_timeout",
        "modeExecutionTimeout",
    )
    if any(key in payload and payload.get(key) not in (None, "") for key in explicit_keys):
        explicit_timeout = _float_from_payload(payload, explicit_keys, default)
        if explicit_timeout is None or explicit_timeout <= 0:
            return None
        return max(1.0, explicit_timeout)
    generic_timeout = _float_from_payload(payload, ("timeout",), default)
    if generic_timeout is None or generic_timeout <= 0:
        return None
    return max(1.0, min(generic_timeout, max_default))


def _format_number(value: float | int) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _safe_eval_math_node(node: ast.AST) -> float | int:
    if isinstance(node, ast.Expression):
        return _safe_eval_math_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _safe_eval_math_node(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)):
        left = _safe_eval_math_node(node.left)
        right = _safe_eval_math_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        return left % right
    raise ValueError("unsupported math expression")


def _simple_math_answer(task: str) -> str:
    expression = str(task or "").strip()
    expression = expression.replace("？", "?").replace("×", "*").replace("÷", "/")
    expression = re.sub(r"\s+", "", expression)
    expression = re.sub(r"[=?]+$", "", expression)
    if not expression or len(expression) > 80:
        return ""
    if not re.fullmatch(r"[0-9+\-*/().%]+", expression):
        return ""
    try:
        parsed = ast.parse(expression, mode="eval")
        return _format_number(_safe_eval_math_node(parsed))
    except Exception:
        return ""


def _llm_chat_url_from_payload(payload: Mapping[str, Any]) -> str:
    base = str(
        payload.get("direct_llm_url")
        or payload.get("directLlmUrl")
        or payload.get("llm_url")
        or payload.get("llmUrl")
        or payload.get("route_llm_url")
        or payload.get("routeLlmUrl")
        or os.getenv("DIRECT_LLM_URL")
        or os.getenv("ROUTER_LLM_URL")
        or os.getenv("LLM_API_URL")
        or ""
    ).strip()
    if not base:
        return ""
    if base.rstrip("/").endswith("/chat/completions"):
        return base.rstrip("/")
    return f"{base.rstrip('/')}/chat/completions"


def _llm_api_key_from_payload(payload: Mapping[str, Any]) -> str:
    return str(
        payload.get("direct_llm_api_key")
        or payload.get("directLlmApiKey")
        or payload.get("llm_api_key")
        or payload.get("llmApiKey")
        or payload.get("route_llm_api_key")
        or payload.get("routeLlmApiKey")
        or os.getenv("DIRECT_LLM_API_KEY")
        or os.getenv("ROUTER_LLM_API_KEY")
        or os.getenv("LLM_API_KEY")
        or os.getenv("DEEPSEEK_API_KEY")
        or ""
    ).strip()


def _llm_model_from_payload(payload: Mapping[str, Any]) -> str:
    return str(
        payload.get("direct_llm_model")
        or payload.get("directLlmModel")
        or payload.get("llm_model")
        or payload.get("llmModel")
        or payload.get("route_llm_model")
        or payload.get("routeLlmModel")
        or os.getenv("DIRECT_LLM_MODEL")
        or os.getenv("ROUTER_LLM_MODEL")
        or os.getenv("LLM_MODEL")
        or "deepseek-chat"
    ).strip()


def _extract_chat_completion_text(payload: Mapping[str, Any]) -> str:
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        message = (choices[0] or {}).get("message") if isinstance(choices[0], Mapping) else {}
        if isinstance(message, Mapping) and message.get("content"):
            return str(message["content"])
        if isinstance(choices[0], Mapping) and choices[0].get("text"):
            return str(choices[0]["text"])
    if payload.get("result"):
        result = payload["result"]
        if isinstance(result, str):
            return result
        if isinstance(result, Mapping) and result.get("content"):
            return str(result["content"])
    if payload.get("content"):
        return str(payload["content"])
    if payload.get("text"):
        return str(payload["text"])
    return ""


def _agent_poll_interval_from_payload(payload: Mapping[str, Any]) -> float:
    interval = _float_from_payload(payload, ("agent_poll_interval", "agentPollInterval"), 1.0)
    if interval is None or interval <= 0:
        return 1.0
    return max(0.2, min(interval, 5.0))


def _agent_poll_timeout_from_payload(payload: Mapping[str, Any], timeout: float | None) -> float:
    explicit = _float_from_payload(
        payload,
        ("agent_poll_timeout", "agentPollTimeout", "agent_poll_max_seconds", "agentPollMaxSeconds"),
        None,
    )
    if explicit is not None and explicit > 0:
        return explicit
    if timeout is None or timeout <= 0:
        return 480.0
    return max(1.0, timeout)


def _append_rpc_raw_response(raw_response: Any, key: str, value: Any) -> dict[str, Any]:
    if isinstance(raw_response, Mapping) and any(item in raw_response for item in ("start", "polls", "continue", "complete")):
        merged = dict(raw_response)
        merged[key] = value
        return merged
    return {"start": raw_response, key: value}


def _wait_for_agent_ready(
    endpoint: str,
    task_id: str,
    payload: Mapping[str, Any],
    timeout: float | None,
    start_response: Mapping[str, Any],
) -> tuple[Any, Mapping[str, Any], str]:
    final_state = _task_result_state(start_response)
    ready_response: Mapping[str, Any] = start_response
    raw_response: Any = start_response
    if not _task_state_in_progress(final_state):
        return raw_response, ready_response, final_state

    interval = _agent_poll_interval_from_payload(payload)
    deadline = time.perf_counter() + _agent_poll_timeout_from_payload(payload, timeout)
    polls: list[Mapping[str, Any]] = []
    while time.perf_counter() < deadline:
        time.sleep(interval)
        get_payload = _agent_rpc_command(task_id=task_id, command="get", payload=payload)
        get_response = _post_json(endpoint, get_payload, timeout)
        polls.append(get_response)
        ready_response = get_response
        state = _task_result_state(get_response)
        if state:
            final_state = state
        output_text = _extract_agent_output(get_response, include_status_text=True)
        if output_text.startswith("Agent RPC error:"):
            break
        if output_text and not _looks_like_process_note(output_text):
            break
        if _task_state_terminal(final_state) or not _task_state_in_progress(final_state):
            break

    if polls:
        raw_response = {"start": start_response, "polls": polls[-10:]}
    return raw_response, ready_response, final_state


def _call_direct_llm(task: str, payload: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    url = _llm_chat_url_from_payload(payload)
    api_key = _llm_api_key_from_payload(payload)
    if not url:
        raise RuntimeError("direct LLM URL is not configured")
    if not api_key:
        raise RuntimeError("direct LLM API key is not configured")
    system_prompt = str(
        payload.get("direct_llm_system")
        or payload.get("directLlmSystem")
        or "You are a helpful assistant. Answer the user's question directly and concisely. Use Chinese when the user writes Chinese."
    )
    body: dict[str, Any] = {
        "model": _llm_model_from_payload(payload),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ],
        "stream": False,
        "temperature": float(payload.get("direct_llm_temperature", payload.get("directLlmTemperature", 0))),
        "max_tokens": int(payload.get("direct_llm_max_tokens", payload.get("directLlmMaxTokens", 2048))),
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    timeout = float(payload.get("direct_llm_timeout", payload.get("directLlmTimeout", payload.get("timeout", 60))))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    text = _extract_chat_completion_text(parsed)
    if not text:
        raise RuntimeError("direct LLM response did not contain answer text")
    return text, parsed


def execute_plan_llm_direct(task: str, plan: Mapping[str, Any], *, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    execution_id = f"exec-{uuid4().hex[:12]}"
    started = time.perf_counter()
    answer = _simple_math_answer(task)
    raw_response: dict[str, Any] = {}
    executor = "local_deterministic"
    error = ""

    if not answer:
        executor = "direct_llm"
        try:
            answer, raw_response = _call_direct_llm(task, payload)
        except Exception as exc:
            error = str(exc)

    duration_ms = round((time.perf_counter() - started) * 1000)
    done = bool(answer)
    run = {
        "run_id": f"run-{uuid4().hex[:10]}",
        "package_id": "llm-direct",
        "task_id": str(payload.get("task_id") or payload.get("taskId") or f"mode0-{uuid4().hex[:8]}"),
        "executor": executor,
        "status": "completed" if done else "failed",
        "duration_ms": duration_ms,
        "output_length": len(answer),
        "output_text": answer,
    }
    if raw_response:
        run["usage"] = raw_response.get("usage") or {}
        run["model"] = raw_response.get("model") or _llm_model_from_payload(payload)
    if error:
        run["error"] = error
    return {
        "execution_id": execution_id,
        "plan_id": plan.get("plan_id"),
        "status": "done" if done else "failed",
        "mode": plan.get("mode"),
        "strategy": plan.get("strategy"),
        "dry_run": False,
        "group_chat": False,
        "agent_rpc_called": False,
        "llm_direct_called": executor == "direct_llm" and done,
        "runs": [run],
        "events": [
            {
                "timestamp": _utc_now(),
                "state": "done" if done else "failed",
                "stage": "llm_direct_execution",
                "executor": executor,
            }
        ],
        "final_result": answer,
        "message": "" if done else error,
    }


def _extract_html_document(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    fenced = re.search(r"```html\s*([\s\S]*?)```", raw, re.IGNORECASE)
    if not fenced:
        fenced = re.search(r"```\s*(<!doctype html[\s\S]*?|<html[\s\S]*?)```", raw, re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    match = re.search(r"<!doctype html|<html", raw, re.IGNORECASE)
    if not match:
        return ""
    from_doc = raw[match.start():]
    close_at = from_doc.lower().rfind("</html>")
    if close_at >= 0:
        return from_doc[: close_at + len("</html>")].strip()
    return from_doc.strip() if "</body>" in from_doc.lower() else ""


def _artifact_mime(filename: str = "", mime: str = "", content: str = "") -> str:
    explicit = str(mime or "").strip().lower()
    if explicit and "/" in explicit:
        return explicit.split(";", 1)[0]
    name = str(filename or "").strip().lower()
    if name.endswith(".html") or name.endswith(".htm") or _extract_html_document(content):
        return "text/html"
    if name.endswith(".json"):
        return "application/json"
    if name.endswith(".csv"):
        return "text/csv"
    if name.endswith(".txt"):
        return "text/plain"
    return "text/markdown"


def _artifact_filename(task: str, title: str, mime: str) -> str:
    ext_by_mime = {
        "text/html": "html",
        "application/json": "json",
        "text/csv": "csv",
        "text/plain": "txt",
        "text/markdown": "md",
    }
    ext = ext_by_mime.get(mime, "md")
    base = _slug(title or task or "artifact", 42)
    return f"{base}.{ext}"


def _artifact_from_content(
    *,
    task: str,
    run: Mapping[str, Any],
    content: str,
    title: str = "",
    filename: str = "",
    mime: str = "",
    source: str = "agent-output",
) -> dict[str, Any]:
    clean_content = str(content or "").strip()
    clean_filename = str(filename or "").strip()
    clean_title = str(title or clean_filename or run.get("agent_name") or run.get("package_id") or "文件产物").strip()
    clean_mime = _artifact_mime(clean_filename, mime, clean_content)
    if clean_mime == "text/html":
        html = _extract_html_document(clean_content)
        if html:
            clean_content = html
    if not clean_filename:
        clean_filename = _artifact_filename(task, clean_title, clean_mime)
    return {
        "id": f"artifact-{uuid4().hex[:10]}",
        "title": clean_title,
        "filename": clean_filename,
        "mime": clean_mime,
        "content": clean_content,
        "agent_name": run.get("agent_name") or run.get("package_id") or "agent",
        "package_id": run.get("package_id"),
        "source": source,
    }


def _artifact_candidates_from_payload(value: Any, *, task: str, run: Mapping[str, Any]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []

    def walk(item: Any) -> None:
        if isinstance(item, list):
            for child in item:
                walk(child)
            return
        if not isinstance(item, Mapping):
            return

        filename = str(
            item.get("filename")
            or item.get("file_name")
            or item.get("name")
            or item.get("path")
            or item.get("file_path")
            or ""
        ).strip()
        mime = str(item.get("mime") or item.get("mime_type") or item.get("contentType") or item.get("content_type") or "").strip()
        title = str(item.get("title") or item.get("name") or filename or "").strip()
        content = item.get("content")
        if content is None:
            content = item.get("text")
        if isinstance(content, (dict, list)):
            content = json.dumps(content, ensure_ascii=False, indent=2)
        content = str(content or "").strip()

        explicit_file = bool(filename or mime or item.get("file_path") or item.get("path"))
        has_text_file = bool(content and explicit_file and _artifact_mime(filename, mime, content).startswith(("text/", "application/json")))
        has_html = bool(content and _extract_html_document(content))
        if has_text_file or has_html:
            artifacts.append(
                _artifact_from_content(
                    task=task,
                    run=run,
                    content=content,
                    title=title,
                    filename=filename,
                    mime=mime,
                    source="agent-product",
                )
            )

        for key in ("products", "dataItems", "data_items", "files", "artifacts", "attachments", "result", "status"):
            child = item.get(key)
            if child is not None and child is not item:
                walk(child)

    walk(value)
    return artifacts


def _is_html_request(task: str) -> bool:
    lowered = str(task or "").lower()
    return any(marker in lowered for marker in ("html", "可视化", "网页", "页面", "preview", "download"))


def _has_frontend_package(packages: list[Mapping[str, Any]]) -> bool:
    for package in packages:
        roles = [str(role).lower() for role in list(package.get("inferred_roles") or [])]
        if "frontend" in roles:
            return True
        agent = package.get("agent") if isinstance(package.get("agent"), Mapping) else {}
        name = str(agent.get("name") or package.get("objective") or "").lower()
        if "前端" in name or "frontend" in name or "html" in name:
            return True
    return False


def _build_fallback_html_artifact(task: str, runs: list[Mapping[str, Any]]) -> str:
    completed = [run for run in runs if run.get("status") == "completed" and str(run.get("output_text") or "").strip()]
    if not completed:
        return ""
    title = "RenTA 可视化任务结果"
    summary_cards = []
    sections = []
    palette = ["#2E7AB8", "#D4906A", "#10B981", "#6366F1", "#E11D48"]
    for idx, run in enumerate(completed, start=1):
        agent_name = str(run.get("agent_name") or run.get("package_id") or f"Agent {idx}")
        text = str(run.get("output_text") or "").strip()
        summary = re.sub(r"\s+", " ", text)[:180]
        color = palette[(idx - 1) % len(palette)]
        summary_cards.append(
            f'<article class="summary-card" style="--accent:{color}">'
            f"<span>0{idx}</span><strong>{escape(agent_name)}</strong><p>{escape(summary)}</p></article>"
        )
        sections.append(
            f'<section><h2>{escape(agent_name)}</h2><pre>{escape(text)}</pre></section>'
        )
    created = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{ --ink:#172033; --muted:#667085; --paper:#fbfaf7; --line:#e6dfd4; --blue:#2E7AB8; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--paper); color:var(--ink); font-family:"Microsoft YaHei","PingFang SC",sans-serif; line-height:1.72; }}
    header {{ padding:44px clamp(20px,5vw,72px) 32px; background:#eef6fb; border-bottom:1px solid var(--line); }}
    h1 {{ margin:0; font-size:clamp(30px,6vw,64px); line-height:1.08; }}
    .meta {{ margin-top:10px; color:var(--muted); }}
    main {{ padding:28px clamp(16px,4vw,64px) 64px; }}
    .summary-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; margin-bottom:28px; }}
    .summary-card {{ background:#fff; border:1px solid var(--line); border-top:4px solid var(--accent); border-radius:8px; padding:16px; box-shadow:0 12px 32px rgba(43,36,27,.08); }}
    .summary-card span {{ color:var(--accent); font-weight:800; font-size:12px; }}
    .summary-card strong {{ display:block; margin:8px 0; }}
    .summary-card p {{ margin:0; color:var(--muted); font-size:13px; }}
    section {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:22px; margin:14px 0; }}
    h2 {{ margin:0 0 12px; font-size:22px; }}
    pre {{ white-space:pre-wrap; word-break:break-word; margin:0; font:14px/1.78 "Microsoft YaHei","PingFang SC",sans-serif; color:#263246; background:#f8fafc; border:1px solid #e7ecf2; border-radius:8px; padding:14px; }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(title)}</h1>
    <div class="meta">{escape(task)} · {escape(created)}</div>
  </header>
  <main>
    <div class="summary-grid">{''.join(summary_cards)}</div>
    {''.join(sections)}
  </main>
</body>
</html>"""


def _build_execution_artifacts(task: str, packages: list[Mapping[str, Any]], runs: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(artifact: Mapping[str, Any]) -> None:
        content = str(artifact.get("content") or "")
        filename = str(artifact.get("filename") or "")
        key = (filename, content[:500])
        if not content or key in seen:
            return
        seen.add(key)
        artifacts.append(dict(artifact))

    for run in runs:
        content = str(run.get("output_text") or "")
        html = _extract_html_document(content)
        if html:
            add(
                _artifact_from_content(
                    task=task,
                    run=run,
                    content=html,
                    title="可视化 HTML 文件",
                    filename=f"{_slug(task or 'visual_artifact', 36)}.html",
                    mime="text/html",
                    source="agent-output",
                )
            )
        raw_response = run.get("raw_response")
        if raw_response:
            for artifact in _artifact_candidates_from_payload(raw_response, task=task, run=run):
                add(artifact)

    if not artifacts and _is_html_request(task) and _has_frontend_package(packages):
        html = _build_fallback_html_artifact(task, runs)
        if html:
            add(
                _artifact_from_content(
                    task=task,
                    run={"agent_name": "Mode Router", "package_id": "fallback-html"},
                    content=html,
                    title="可视化 HTML 文件",
                    filename=f"{_slug(task or 'visual_artifact', 36)}.html",
                    mime="text/html",
                    source="orchestrator-fallback",
                )
            )
    return artifacts


def _truncate_for_synthesis(text: str, limit: int = 6000) -> str:
    clean = str(text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[:limit] + "\n...[truncated]..."


def _call_mode2_synthesis_llm(system_prompt: str, user_prompt: str, payload: Mapping[str, Any]) -> str:
    url = str(
        payload.get("synthesis_llm_url")
        or payload.get("synthesisLlmUrl")
        or _llm_chat_url_from_payload(payload)
    ).strip()
    api_key = str(
        payload.get("synthesis_llm_api_key")
        or payload.get("synthesisLlmApiKey")
        or _llm_api_key_from_payload(payload)
    ).strip()
    if not url:
        raise RuntimeError("mode2 synthesis LLM URL is not configured")
    if not api_key:
        raise RuntimeError("mode2 synthesis LLM API key is not configured")
    model = str(payload.get("synthesis_llm_model") or payload.get("synthesisLlmModel") or _llm_model_from_payload(payload)).strip()
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "temperature": float(payload.get("synthesis_llm_temperature", payload.get("synthesisLlmTemperature", 0.2))),
        "max_tokens": int(payload.get("synthesis_llm_max_tokens", payload.get("synthesisLlmMaxTokens", 2048))),
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    timeout = float(payload.get("synthesis_llm_timeout", payload.get("synthesisLlmTimeout", payload.get("timeout", 90))))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    text = _extract_chat_completion_text(parsed)
    if not text:
        raise RuntimeError("mode2 synthesis LLM response did not contain answer text")
    return text.strip()


def _mode2_fallback_answer(task: str, completed_runs: list[Mapping[str, Any]], failed_runs: list[Mapping[str, Any]], artifacts: list[Mapping[str, Any]]) -> str:
    if not completed_runs:
        return "这次多智能体任务没有拿到可用结果，请稍后重试或换一个更明确的问题。"
    snippets = []
    for run in completed_runs:
        text = _truncate_for_synthesis(str(run.get("output_text") or ""), 900)
        html = _extract_html_document(text)
        if html:
            text = "已生成 HTML 可视化文件。"
        if text:
            snippets.append(text)
    body = "\n\n".join(snippets[:3]).strip()
    lines = ["已完成多智能体协作，我将结果整理如下："]
    if body:
        lines.append(body)
    if artifacts:
        names = "、".join(str(item.get("filename") or item.get("title") or "文件") for item in artifacts[:3])
        lines.append(f"本次还生成了 {len(artifacts)} 个文件产物：{names}。可在下方文件卡片中预览或下载。")
    if failed_runs:
        lines.append(f"另有 {len(failed_runs)} 个 agent 执行失败，已忽略失败结果。")
    return "\n\n".join(lines)


def _synthesize_mode2_answer(
    *,
    task: str,
    completed_runs: list[Mapping[str, Any]],
    failed_runs: list[Mapping[str, Any]],
    artifacts: list[Mapping[str, Any]],
    payload: Mapping[str, Any],
) -> tuple[str, str, str]:
    if not _payload_bool(payload, ("mode2_synthesis", "mode2Synthesis", "synthesize_final_answer", "synthesizeFinalAnswer"), True):
        return _mode2_fallback_answer(task, completed_runs, failed_runs, artifacts), "fallback_disabled", ""

    file_lines = [
        f"- {item.get('filename') or item.get('title')}: {item.get('mime') or 'file'} from {item.get('agent_name') or item.get('source') or 'agent'}"
        for item in artifacts
    ]
    run_blocks = []
    for index, run in enumerate(completed_runs, start=1):
        output = str(run.get("output_text") or "").strip()
        if _extract_html_document(output):
            output = "[该 agent 生成了 HTML 文件产物，源码已作为附件提供，不要在回答正文中复述源码。]"
        run_blocks.append(
            "\n".join(
                [
                    f"### Run {index}",
                    f"agent: {run.get('agent_name') or run.get('package_id') or 'unknown'}",
                    f"objective: {run.get('objective') or ''}",
                    f"status: {run.get('status') or ''}",
                    "output:",
                    _truncate_for_synthesis(output),
                ]
            )
        )
    if failed_runs:
        run_blocks.append(
            "### Failed runs\n"
            + "\n".join(
                f"- {run.get('agent_name') or run.get('package_id')}: {run.get('error') or run.get('status')}"
                for run in failed_runs[:5]
            )
        )

    system_prompt = (
        "你是 RenTA 的 mode2 多智能体结果整合器。"
        "请基于多个 agent 的真实输出，给用户一条自然、完整、针对原问题的中文回答。"
        "不要逐个罗列 agent 原文，不要暴露编排日志、package_id 或内部路由细节。"
        "如果有文件产物，只需在正文中简短说明已附在回答下方，不能粘贴 HTML/代码全文。"
        "如果部分 agent 失败，只在影响结论时简洁说明。"
    )
    user_prompt = (
        f"用户原问题:\n{task}\n\n"
        f"可下载/预览文件产物:\n{chr(10).join(file_lines) if file_lines else '(none)'}\n\n"
        "agent 输出:\n"
        + "\n\n".join(run_blocks)
    )
    try:
        text = _call_mode2_synthesis_llm(system_prompt, user_prompt, payload)
        return text, "llm_synthesis", ""
    except Exception as exc:
        return _mode2_fallback_answer(task, completed_runs, failed_runs, artifacts), "fallback_after_llm_error", str(exc)


def execute_plan_single_agent(task: str, plan: Mapping[str, Any], *, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    execution_id = f"exec-{uuid4().hex[:12]}"
    packages = [package for package in list(plan.get("work_packages") or []) if isinstance(package, Mapping)]
    if plan.get("mode") != "mode_1":
        return _skip_execution(plan, "Single-agent execution only applies to mode_1 plans.")
    if not packages:
        return {
            "execution_id": execution_id,
            "plan_id": plan.get("plan_id"),
            "status": "failed",
            "mode": plan.get("mode"),
            "strategy": plan.get("strategy"),
            "dry_run": False,
            "group_chat": False,
            "agent_rpc_called": False,
            "runs": [],
            "message": "mode_1 plan has no work package to execute.",
            "final_result": "",
        }

    package = packages[0]
    package_id = str(package.get("package_id") or package.get("id") or f"pkg-{uuid4().hex[:8]}")
    task_id = str(payload.get("task_id") or payload.get("taskId") or f"mode1-{package_id}-{uuid4().hex[:8]}")
    endpoint = _mode1_agent_url(package, payload)
    agent = dict(package.get("agent") or {})
    started = time.perf_counter()
    timeout = _agent_timeout_from_payload(payload, default=480.0, max_default=600.0)

    if not endpoint:
        run = {
            "run_id": f"run-{uuid4().hex[:10]}",
            "package_id": package_id,
            "task_id": task_id,
            "agent": agent,
            "status": "failed",
            "duration_ms": 0,
            "agent_rpc_called": False,
            "error": "agent endpoint URL is missing",
            "output_text": "",
        }
        return {
            "execution_id": execution_id,
            "plan_id": plan.get("plan_id"),
            "status": "failed",
            "mode": plan.get("mode"),
            "strategy": plan.get("strategy"),
            "dry_run": False,
            "group_chat": False,
            "agent_rpc_called": False,
            "runs": [run],
            "message": "Cannot execute mode_1 because the selected agent has no endpoint URL.",
            "final_result": "",
        }

    request_payload = _mode1_agent_rpc_payload(task, package, payload, task_id)
    try:
        start_response = _post_json(endpoint, request_payload, timeout)
        raw_response, ready_response, final_state = _wait_for_agent_ready(endpoint, task_id, payload, timeout, start_response)
        output_text = ""
        if final_state == "awaiting-completion":
            awaiting_text = _extract_agent_output(ready_response, include_status_text=True)
            if awaiting_text and _looks_like_process_note(awaiting_text):
                continue_payload = _agent_rpc_command(
                    task_id=task_id,
                    command="continue",
                    payload=payload,
                    text="Continue and return the actual deliverable content now.",
                )
                continue_response = _post_json(endpoint, continue_payload, timeout)
                raw_response = _append_rpc_raw_response(raw_response, "continue", continue_response)
                ready_response = continue_response
                continued_text = _extract_agent_output(continue_response, include_status_text=True)
                if continued_text and not _looks_like_process_note(continued_text):
                    output_text = continued_text
                final_state = _task_result_state(continue_response) or final_state
            complete_payload = _agent_rpc_command(task_id=task_id, command="complete", payload=payload)
            complete_response = _post_json(endpoint, complete_payload, timeout)
            raw_response = _append_rpc_raw_response(raw_response, "complete", complete_response)
            final_state = _task_result_state(complete_response) or final_state
            if not output_text:
                output_text = _extract_agent_output(complete_response, include_status_text=False)
            if not output_text:
                awaiting_text = _extract_agent_output(ready_response, include_status_text=True)
                if awaiting_text and not _looks_like_process_note(awaiting_text):
                    output_text = awaiting_text
        else:
            output_text = _extract_agent_output(ready_response, include_status_text=final_state not in {"completed", "failed", "rejected", "canceled", "cancelled"})
        failed = output_text.startswith("Agent RPC error:") or not output_text or _looks_like_process_note(output_text)
        status = "failed" if failed else "completed"
        if output_text.startswith("Agent RPC error:"):
            error = output_text
        elif not output_text:
            error = f"agent returned empty output (state={final_state or 'unknown'})"
        elif _looks_like_process_note(output_text):
            error = f"agent returned progress text without a deliverable (state={final_state or 'unknown'})"
        else:
            error = ""
    except Exception as exc:
        raw_response = {}
        output_text = ""
        status = "failed"
        error = str(exc)

    duration_ms = round((time.perf_counter() - started) * 1000)
    run = {
        "run_id": f"run-{uuid4().hex[:10]}",
        "package_id": package_id,
        "task_id": task_id,
        "agent": agent,
        "agent_aic": _mode1_agent_aic(package),
        "agent_name": _mode1_agent_name(package),
        "endpoint": endpoint,
        "status": status,
        "duration_ms": duration_ms,
        "objective": package.get("objective") or "",
        "skills": list(package.get("skills") or []),
        "agent_rpc_called": True,
        "request_method": "JSON-RPC",
        "output_length": len(output_text),
        "output_text": output_text,
        "raw_response": raw_response,
    }
    if error:
        run["error"] = error

    done = status == "completed"
    return {
        "execution_id": execution_id,
        "plan_id": plan.get("plan_id"),
        "status": "done" if done else "failed",
        "mode": plan.get("mode"),
        "strategy": plan.get("strategy"),
        "dry_run": False,
        "group_chat": False,
        "agent_rpc_called": True,
        "runs": [run],
        "events": [
            {
                "timestamp": _utc_now(),
                "state": "done" if done else "failed",
                "stage": "single_agent_execution",
                "package_id": package_id,
                "agent_aic": _mode1_agent_aic(package),
                "endpoint": endpoint,
            }
        ],
        "final_result": output_text if done else "",
        "message": "" if done else error,
    }


def _package_id(package: Mapping[str, Any]) -> str:
    return str(package.get("package_id") or package.get("id") or f"pkg-{uuid4().hex[:8]}")


def _mode2_package_url(package: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    endpoint_overrides = payload.get("agent_urls") or payload.get("agentUrls") or {}
    agent = package.get("agent") if isinstance(package.get("agent"), Mapping) else {}
    aic = str(agent.get("aic") or "").strip()
    if isinstance(endpoint_overrides, Mapping) and aic and endpoint_overrides.get(aic):
        return str(endpoint_overrides[aic]).strip()
    endpoint = _agent_url_from_mapping(agent)
    if endpoint:
        return endpoint
    return str(package.get("url") or package.get("endpoint") or "").strip()


def _mode2_dependencies(packages: list[Mapping[str, Any]]) -> dict[str, list[str]]:
    package_ids = {_package_id(package) for package in packages}
    dependencies: dict[str, list[str]] = {}
    for package in packages:
        package_id = _package_id(package)
        raw_deps = [str(item) for item in list(package.get("depends_on") or []) if str(item) in package_ids]
        dependencies[package_id] = raw_deps
    return dependencies


def execute_plan_http_agents(task: str, plan: Mapping[str, Any], *, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    execution_id = f"exec-{uuid4().hex[:12]}"
    packages = [package for package in list(plan.get("work_packages") or []) if isinstance(package, Mapping)]
    if plan.get("mode") != "mode_2":
        return _skip_execution(plan, "HTTP multi-agent execution only applies to mode_2 plans.")
    if not packages:
        return {
            "execution_id": execution_id,
            "plan_id": plan.get("plan_id"),
            "status": "failed",
            "mode": plan.get("mode"),
            "strategy": plan.get("strategy"),
            "dry_run": False,
            "group_chat": False,
            "agent_rpc_called": False,
            "runs": [],
            "events": [],
            "message": "mode_2 plan has no work package to execute.",
            "final_result": "",
        }

    dependencies = _mode2_dependencies(packages)
    package_by_id = {_package_id(package): package for package in packages}
    pending = [_package_id(package) for package in packages]
    completed: set[str] = set()
    outputs: dict[str, str] = {}
    run_by_package: dict[str, dict[str, Any]] = {}
    timeout = _agent_timeout_from_payload(payload, default=480.0, max_default=600.0)
    execution_timeout = _execution_timeout_from_payload(payload, default=600.0, max_default=1800.0)
    execution_deadline = (time.perf_counter() + execution_timeout) if execution_timeout is not None else None
    session_id = str(payload.get("session_id") or payload.get("sessionId") or f"http-{uuid4().hex[:10]}")
    leader_aic = str(payload.get("leader_aic") or payload.get("leaderAic") or "mode-router")
    traffic_enabled = _traffic_enabled(payload)
    events: list[dict[str, Any]] = [
        {
            "timestamp": _utc_now(),
            "state": "running",
            "stage": "http_multi_agent_start",
            "package_count": len(packages),
            "session_id": session_id,
        }
    ]

    def _timeout_run(package_id: str, message: str) -> dict[str, Any]:
        package = package_by_id[package_id]
        agent = dict(package.get("agent") or {})
        return {
            "run_id": f"run-{uuid4().hex[:10]}",
            "package_id": package_id,
            "task_id": str(payload.get("task_id") or payload.get("taskId") or f"mode2-{package_id}-{uuid4().hex[:8]}"),
            "agent": agent,
            "agent_aic": agent.get("aic", ""),
            "agent_name": agent.get("name", ""),
            "endpoint": _mode2_package_url(package, payload),
            "status": "failed",
            "duration_ms": 0,
            "depends_on": dependencies.get(package_id, []),
            "objective": package.get("objective") or "",
            "skills": list(package.get("skills") or []),
            "agent_rpc_called": False,
            "request_method": "JSON-RPC",
            "output_length": 0,
            "output_text": "",
            "error": message,
        }

    def _dispatch_package(package_id: str) -> dict[str, Any]:
        package = package_by_id[package_id]
        agent = dict(package.get("agent") or {})
        endpoint = _mode2_package_url(package, payload)
        task_id = str(payload.get("task_id") or payload.get("taskId") or f"mode2-{package_id}-{uuid4().hex[:8]}")
        upstream = {
            dep: outputs.get(dep, "")
            for dep in dependencies.get(package_id, [])
            if outputs.get(dep)
        }
        started = time.perf_counter()
        status = "failed"
        output_text = ""
        error = ""
        raw_response: dict[str, Any] = {}
        dispatch_tokens = 0
        response_tokens = 0
        if not endpoint:
            error = "agent endpoint URL is missing"
        else:
            request_payload = _agent_rpc_payload(task, package, payload, task_id, upstream_outputs=upstream)
            dispatch_tokens = _record_mode2_payload_traffic(
                enabled=traffic_enabled,
                source=leader_aic,
                target=str(agent.get("aic") or agent.get("name") or package_id),
                payload=request_payload,
                edge_type="http_task_dispatch",
                session_id=session_id,
                execution_id=execution_id,
                package_id=package_id,
                task_id=task_id,
                transport="http_jsonrpc",
            )
            try:
                start_response = _post_json(endpoint, request_payload, timeout)
                raw_response, ready_response, final_state = _wait_for_agent_ready(endpoint, task_id, payload, timeout, start_response)
                if final_state == "awaiting-completion":
                    awaiting_text = _extract_agent_output(ready_response, include_status_text=True)
                    if awaiting_text and _looks_like_process_note(awaiting_text):
                        continue_payload = _agent_rpc_command(
                            task_id=task_id,
                            command="continue",
                            payload=payload,
                            text="Continue and return the actual deliverable content for this work package now.",
                        )
                        continue_response = _post_json(endpoint, continue_payload, timeout)
                        raw_response = _append_rpc_raw_response(raw_response, "continue", continue_response)
                        ready_response = continue_response
                        continued_state = _task_result_state(continue_response)
                        continued_text = _extract_agent_output(continue_response, include_status_text=True)
                        if continued_text and not _looks_like_process_note(continued_text):
                            output_text = continued_text
                        if continued_state:
                            final_state = continued_state
                    complete_payload = _agent_rpc_command(task_id=task_id, command="complete", payload=payload)
                    complete_response = _post_json(endpoint, complete_payload, timeout)
                    raw_response = _append_rpc_raw_response(raw_response, "complete", complete_response)
                    final_state = _task_result_state(complete_response) or final_state
                    if not output_text:
                        output_text = _extract_agent_output(complete_response, include_status_text=False)
                    if not output_text:
                        awaiting_text = _extract_agent_output(ready_response, include_status_text=True)
                        if awaiting_text and not _looks_like_process_note(awaiting_text):
                            output_text = awaiting_text
                else:
                    output_text = _extract_agent_output(ready_response, include_status_text=final_state not in {"completed", "failed", "rejected", "canceled", "cancelled"})
                if output_text.startswith("Agent RPC error:"):
                    error = output_text
                elif output_text and not _looks_like_process_note(output_text):
                    status = "completed"
                elif output_text:
                    error = f"agent returned progress text without a deliverable (state={final_state or 'unknown'})"
                else:
                    error = f"agent returned empty output (state={final_state or 'unknown'})"
            except Exception as exc:
                error = str(exc)
            response_tokens = _record_mode2_payload_traffic(
                enabled=traffic_enabled,
                source=str(agent.get("aic") or agent.get("name") or package_id),
                target=leader_aic,
                payload={
                    "task_id": task_id,
                    "status": status,
                    "output_text": output_text,
                    "error": error,
                    "raw_response": raw_response,
                },
                edge_type="http_agent_result",
                session_id=session_id,
                execution_id=execution_id,
                package_id=package_id,
                task_id=task_id,
                transport="http_jsonrpc",
            )
        duration_ms = round((time.perf_counter() - started) * 1000)
        run = {
            "run_id": f"run-{uuid4().hex[:10]}",
            "package_id": package_id,
            "task_id": task_id,
            "agent": agent,
            "agent_aic": agent.get("aic", ""),
            "agent_name": agent.get("name", ""),
            "endpoint": endpoint,
            "status": status,
            "duration_ms": duration_ms,
            "depends_on": dependencies.get(package_id, []),
            "objective": package.get("objective") or "",
            "skills": list(package.get("skills") or []),
            "agent_rpc_called": bool(endpoint),
            "request_method": "JSON-RPC",
            "output_length": len(output_text),
            "output_text": output_text,
            "traffic_prompt_tokens": dispatch_tokens,
            "traffic_output_tokens": response_tokens,
            "raw_response": raw_response,
        }
        if error:
            run["error"] = error
        return run

    while pending:
        ready = [package_id for package_id in pending if all(dep in completed for dep in dependencies.get(package_id, []))]
        if not ready:
            import sys
            print('[V2B-LOG] fallback triggered: ready=[] pending=%s completed=%s' % (pending, completed), file=sys.stderr, flush=True)
            ready = pending[:1]
            print('[V2B-LOG] fallback selected: %s (deps=%s)' % (ready[0], dependencies.get(ready[0], [])), file=sys.stderr, flush=True)
        if execution_deadline is not None and time.perf_counter() >= execution_deadline:
            for package_id in ready:
                run = _timeout_run(package_id, "execution timeout reached before dispatch")
                run_by_package[package_id] = run
                events.append(
                    {
                        "timestamp": _utc_now(),
                        "state": "failed",
                        "stage": "http_multi_agent_timeout",
                        "package_id": package_id,
                        "error": "execution timeout reached before dispatch",
                    }
                )
                pending.remove(package_id)
            continue

        dispatch_ids = list(ready)
        for package_id in dispatch_ids:
            package = package_by_id[package_id]
            agent = dict(package.get("agent") or {})
            events.append(
                {
                    "timestamp": _utc_now(),
                    "state": "assigned",
                    "stage": "agent_http_dispatch",
                    "package_id": package_id,
                    "agent_aic": agent.get("aic", ""),
                    "agent_name": agent.get("name", ""),
                    "endpoint": _mode2_package_url(package, payload),
                }
            )

        max_workers = max(1, min(len(dispatch_ids), int(payload.get("max_concurrent_agents", payload.get("maxConcurrentAgents", 8)) or 8)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_by_package = {executor.submit(_dispatch_package, package_id): package_id for package_id in dispatch_ids}
            remaining = None if execution_deadline is None else max(0.1, execution_deadline - time.perf_counter())
            done_futures, pending_futures = concurrent.futures.wait(
                future_by_package,
                timeout=remaining,
                return_when=concurrent.futures.ALL_COMPLETED,
            )
            for future in done_futures:
                package_id = future_by_package[future]
                try:
                    run = future.result()
                except Exception as exc:
                    run = _timeout_run(package_id, str(exc))
                run_by_package[package_id] = run
                if run.get("status") == "completed":
                    outputs[package_id] = str(run.get("output_text") or "")
                completed.add(package_id)
                events.append(
                    {
                        "timestamp": _utc_now(),
                        "state": "done" if run.get("status") == "completed" else "failed",
                        "stage": "agent_http_result",
                        "package_id": package_id,
                        "agent_aic": run.get("agent_aic", ""),
                        "endpoint": run.get("endpoint", ""),
                        "error": run.get("error", ""),
                    }
                )
            for future in pending_futures:
                package_id = future_by_package[future]
                future.cancel()
                run = _timeout_run(package_id, "execution timeout reached while agent was running")
                run["agent_rpc_called"] = bool(run.get("endpoint"))
                run["duration_ms"] = round(max(0, timeout or 0) * 1000)
                run_by_package[package_id] = run
                completed.add(package_id)
                events.append(
                    {
                        "timestamp": _utc_now(),
                        "state": "failed",
                        "stage": "agent_http_result",
                        "package_id": package_id,
                        "agent_aic": run.get("agent_aic", ""),
                        "endpoint": run.get("endpoint", ""),
                        "error": run.get("error", ""),
                    }
                )
        for package_id in dispatch_ids:
            if package_id in pending:
                pending.remove(package_id)

    runs = [run_by_package[_package_id(package)] for package in packages if _package_id(package) in run_by_package]
    completed_runs = [run for run in runs if run.get("status") == "completed"]
    failed_runs = [run for run in runs if run.get("status") != "completed"]
    artifacts = _build_execution_artifacts(task, packages, runs)
    final_result, final_result_source, final_result_error = _synthesize_mode2_answer(
        task=task,
        completed_runs=completed_runs,
        failed_runs=failed_runs,
        artifacts=artifacts,
        payload=payload,
    )
    status = "done" if not failed_runs and len(completed_runs) == len(packages) else ("partial" if completed_runs else "failed")
    final_result_tokens = _record_mode2_payload_traffic(
        enabled=traffic_enabled,
        source=leader_aic,
        target="client",
        payload={"execution_id": execution_id, "session_id": session_id, "status": status, "final_result": final_result},
        edge_type="http_final_result",
        session_id=session_id,
        execution_id=execution_id,
        transport="http_jsonrpc",
    )
    events.append(
        {
            "timestamp": _utc_now(),
            "state": status,
            "stage": "http_multi_agent_complete",
            "completed_packages": len(completed_runs),
            "failed_packages": len(failed_runs),
            "traffic_tokens": final_result_tokens,
            "artifact_count": len(artifacts),
            "final_result_source": final_result_source,
            "final_result_error": final_result_error,
        }
    )
    return {
        "execution_id": execution_id,
        "plan_id": plan.get("plan_id"),
        "status": status,
        "mode": plan.get("mode"),
        "strategy": plan.get("strategy"),
        "dry_run": False,
        "group_chat": False,
        "session_id": session_id,
        "agent_rpc_called": True,
        "runs": runs,
        "events": events,
        "traffic_snapshot": get_traffic_snapshot() if traffic_enabled else {"enabled": False},
        "artifacts": artifacts,
        "final_result": final_result,
        "final_result_source": final_result_source,
        "final_result_error": final_result_error,
        "message": "" if status == "done" else f"{len(failed_runs)} agent run(s) failed during HTTP JSON-RPC execution.",
    }


def _build_orchestrator_execute_response(task: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    route_classification = classify_task_route(task, payload=payload).to_dict()
    if route_classification["label"] == ROUTE_LLM:
        decision = _classification_decision(task, route_classification)
        response = _response_shell("route_classifier", 0, decision.to_dict())
        plan = build_execution_plan(task, [], decision=decision)
        execution = execute_plan_dry_run(plan) if bool(payload.get("dry_run", payload.get("dryRun", False))) else execute_plan_llm_direct(task, plan, payload=payload)
        response["route_classification"] = route_classification
        response["plan"] = plan
        response["execution"] = execution
        response["final_result"] = execution.get("final_result", "")
        response["zh"]["plan"] = summarize_plan_zh(plan)
        response["zh"]["execution"] = summarize_execution_zh(execution)
        return response

    normalized, discovery_context = _normalize_execute_candidates(task, payload, route_classification)
    if not normalized["skills"]:
        raise ValueError("no executable agents were discovered for the task")

    decision = _decide_with_route_classification(
        normalized["task"],
        normalized["skills"],
        normalized["hints"],
        normalized["config"],
        route_classification,
    )
    response = _response_shell(normalized["source"], len(normalized["skills"]), decision.to_dict())
    response["route_classification"] = route_classification
    response.update(discovery_context)

    plan = build_execution_plan(
        normalized["task"],
        normalized["skills"],
        hints=normalized["hints"],
        config=normalized["config"],
        decision=decision,
    )
    plan = _enrich_plan_agent_endpoints(plan, normalized["skills"])
    registry_url = str(discovery_context.get("registry_url") or _registry_url_from_payload(payload))
    dispatch_views = _dispatch_views_for_plan(registry_url, plan, payload)
    if dispatch_views:
        plan = annotate_plan_with_dispatch_guards(plan, dispatch_views)
    response["dispatch_views"] = dispatch_views
    response["plan"] = plan
    response["zh"]["plan"] = summarize_plan_zh(plan)

    if plan.get("status") == "dispatch_blocked":
        execution = _blocked_execution(plan, "Registry dispatch guard blocked one or more agents; generic mode_2 execution was not started.")
    elif bool(payload.get("dry_run", payload.get("dryRun", False))):
        execution = execute_plan_dry_run(plan)
    elif decision.mode == "mode_1":
        execution = execute_plan_single_agent(normalized["task"], plan, payload=payload)
    elif decision.mode == "mode_2":
        default_execution_transport = (
            "mq_inbox"
            if _truthy(os.getenv("ACPS_MQ_INBOX_ENABLED"), False)
            else (os.getenv("MODE2_EXECUTION_TRANSPORT") or "rabbitmq_group_chat")
        )
        execution_transport = str(
            payload.get("execution_transport")
            or payload.get("executionTransport")
            or payload.get("mode2_execution_transport")
            or payload.get("mode2ExecutionTransport")
            or default_execution_transport
        ).strip().lower()
        if execution_transport in {"http", "http_jsonrpc", "jsonrpc", "direct_http"}:
            execution = execute_plan_http_agents(normalized["task"], plan, payload=payload)
        elif execution_transport in {"mq", "amqp", "amqps", "mq_inbox", "inbox"}:
            mq_payload = dict(payload)
            mq_config = mq_payload.get("mq_inbox") or mq_payload.get("mqInbox") or {}
            mq_config = dict(mq_config) if isinstance(mq_config, Mapping) else {}
            mq_config["enabled"] = True
            mq_payload["mq_inbox"] = mq_config
            try:
                execution = execute_plan_group_chat(normalized["task"], plan, payload=mq_payload)
            except Exception as exc:
                fallback_enabled = _truthy(
                    payload.get(
                        "mq_legacy_fallback_enabled",
                        payload.get(
                            "mqLegacyFallbackEnabled",
                            os.getenv("ACPS_MQ_LEGACY_FALLBACK_ENABLED", "true"),
                        ),
                    ),
                    True,
                )
                if not fallback_enabled:
                    raise
                execution = execute_plan_http_agents(normalized["task"], plan, payload=payload)
                execution["fallback_from"] = "mq_inbox"
                execution["fallback_reason"] = str(exc)
        else:
            execution = execute_plan_group_chat(normalized["task"], plan, payload=payload)
    else:
        execution = _skip_execution(plan, f"{decision.mode} selected; no executor is configured for this mode.")

    _settle_completed_agent_runs(registry_url, payload, execution)
    response["execution"] = execution
    response["final_result"] = execution.get("final_result", "")
    response["zh"]["execution"] = summarize_execution_zh(execution)
    return response


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str, limit: int = 48) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "_", text or "").strip("_")
    return (cleaned or "platform_task")[:limit]


def _write_json_file(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _platform_run_dir(task: str) -> Path:
    PLATFORM_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = PLATFORM_RUNS_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{_slug(task)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _append_flow(flow: list[dict[str, Any]], *, stage: str, status: str, message: str, evidence: Mapping[str, Any] | None = None) -> None:
    flow.append(
        {
            "time": _utc_now(),
            "stage": stage,
            "status": status,
            "message": message,
            "evidence": dict(evidence or {}),
        }
    )


def _plain_get_json(url: str, timeout: float = 5.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _registry_items_from_response(registry_response: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    result = registry_response.get("result") or registry_response
    if isinstance(result, Mapping):
        items = result.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, Mapping)]
        return [result]
    if isinstance(result, list):
        return [item for item in result if isinstance(item, Mapping)]
    return []


def _first_agent_endpoint(item: Mapping[str, Any]) -> str:
    acs = item.get("acs") or item.get("acp") or {}
    return _first_endpoint_url_from_acs(acs) if isinstance(acs, Mapping) else ""


def _public_agent_aic(item: Mapping[str, Any]) -> str:
    acs = item.get("acs") or item.get("acp") or {}
    return str(item.get("agentAic") or item.get("aic") or acs.get("aic") or item.get("id") or "")


def _agent_search_text(item: Mapping[str, Any]) -> str:
    acs = item.get("acs") or item.get("acp") or {}
    skills = acs.get("skills") or item.get("declaredSkills") or []
    skill_text = json.dumps(skills, ensure_ascii=False) if skills else ""
    parts = [
        item.get("name"),
        item.get("description"),
        acs.get("name"),
        acs.get("description"),
        _first_agent_endpoint(item),
        skill_text,
    ]
    return " ".join(str(part or "") for part in parts).lower()


def _candidate_agent_summary(item: Mapping[str, Any]) -> dict[str, Any]:
    acs = item.get("acs") or item.get("acp") or {}
    skills = acs.get("skills") or item.get("declaredSkills") or []
    endpoint = _preferred_http_endpoint_from_acs(acs) if isinstance(acs, Mapping) else {}
    return {
        "aic": _public_agent_aic(item),
        "name": item.get("name") or acs.get("name") or "",
        "description": item.get("description") or acs.get("description") or "",
        "endpoint": _first_agent_endpoint(item),
        "transport": endpoint.get("transport", ""),
        "active": acs.get("active"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "skill_count": len(skills) if isinstance(skills, list) else 0,
    }


def _build_platform_processing_flow(
    *,
    task: str,
    registry_url: str,
    discovery_url: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    run_dir = _platform_run_dir(task)
    flow: list[dict[str, Any]] = []
    started_at = _utc_now()
    registry_response: dict[str, Any] = {}
    discovery_request: dict[str, Any] = {}
    discovery_response: dict[str, Any] = {}
    discovery_stats: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []

    _append_flow(flow, stage="receive_task", status="done", message="Mode Router accepted the task.", evidence={"entrypoint": "/platform/tasks/dry-run"})
    _write_json_file(run_dir / "01_request.json", {"task": task, "payload": dict(payload), "received_at": started_at})

    registry_token = _registry_token_from_payload(payload)
    if registry_url:
        try:
            registry_response = call_registry_public_recent(
                registry_url,
                page_num=int(payload.get("registry_page_num", payload.get("registryPageNum", 1))),
                page_size=int(payload.get("registry_page_size", payload.get("registryPageSize", 100))),
                auth_token=registry_token,
                timeout=float(payload.get("registry_timeout", payload.get("registryTimeout", 15))),
                retries=int(payload.get("registry_retries", payload.get("registryRetries", 0))),
                retry_backoff=float(payload.get("retry_backoff", payload.get("retryBackoff", 2))),
            )
            items = _registry_items_from_response(registry_response)
            _append_flow(
                flow,
                stage="registry_discovery",
                status="done",
                message="Queried Registry public recent agent list.",
                evidence={
                    "url": f"{registry_url}/api/agent/public/recent",
                    "items": len(items),
                    "total": registry_response.get("total"),
                    "agent_rpc_called": False,
                },
            )
        except Exception as exc:
            errors.append({"stage": "registry_discovery", "message": str(exc)})
            _append_flow(flow, stage="registry_discovery", status="error", message=str(exc), evidence={"url": registry_url})
    else:
        items = []
        _append_flow(flow, stage="registry_discovery", status="skipped", message="No Registry URL was provided.")

    if discovery_url:
        discovery_request = build_discovery_request(task, {**dict(payload), "limit": payload.get("discovery_limit", payload.get("limit", 9))})
        try:
            discovery_response = call_discovery(
                discovery_url,
                discovery_request,
                timeout=float(payload.get("discovery_timeout", payload.get("discoveryTimeout", 8))),
                retries=int(payload.get("discovery_retries", payload.get("discoveryRetries", 0))),
                retry_backoff=float(payload.get("retry_backoff", payload.get("retryBackoff", 2))),
            )
            normalized_discovery = normalize_request_payload({"task": task, "discovery_response": discovery_response})
            _append_flow(
                flow,
                stage="discovery_query",
                status="done",
                message="Queried Discovery for task-related agents.",
                evidence={
                    "url": discovery_url,
                    "normalized_skill_count": len(normalized_discovery["skills"]),
                    "agent_rpc_called": False,
                },
            )
        except Exception as exc:
            errors.append({"stage": "discovery_query", "message": str(exc)})
            _append_flow(flow, stage="discovery_query", status="error", message=str(exc), evidence={"url": discovery_url})

        stats_url = discovery_url.rsplit("/", 1)[0] + "/stats" if discovery_url.endswith("/discover") else discovery_url.rstrip("/") + "/stats"
        try:
            discovery_stats = _plain_get_json(stats_url, timeout=float(payload.get("stats_timeout", payload.get("statsTimeout", 5))))
            _append_flow(flow, stage="discovery_stats", status="done", message="Read Discovery stats.", evidence={"url": stats_url})
        except Exception as exc:
            errors.append({"stage": "discovery_stats", "message": str(exc)})
            _append_flow(flow, stage="discovery_stats", status="error", message=str(exc), evidence={"url": stats_url})
    else:
        _append_flow(flow, stage="discovery_query", status="skipped", message="No Discovery URL was provided.")

    normalized = normalize_request_payload(
        {
            "task": task,
            "hints": payload.get("hints") or {},
            "config": payload.get("config") or {},
            "registry_discovery_response": registry_response,
        }
    )
    route_classification = classify_task_route(task, payload=payload).to_dict()
    decision = _decide_with_route_classification(
        normalized["task"],
        normalized["skills"],
        normalized["hints"],
        normalized["config"],
        route_classification,
    )
    plan = build_execution_plan(normalized["task"], normalized["skills"], hints=normalized["hints"], config=normalized["config"], decision=decision)
    plan = _enrich_plan_agent_endpoints(plan, normalized["skills"])
    execution = execute_plan_dry_run(plan)
    _append_flow(
        flow,
        stage="mode_router_plan",
        status="done",
        message="Built a Mode Router dry-run execution plan.",
        evidence={
            "mode": decision.mode,
            "plan_id": plan.get("plan_id"),
            "work_packages": len(plan.get("work_packages") or []),
            "agent_rpc_called": False,
        },
    )

    process_steps = []
    for index, package in enumerate(plan.get("work_packages") or [], start=1):
        agent = package.get("agent") if isinstance(package.get("agent"), Mapping) else {}
        process_steps.append(
            {
                "order": index,
                "package_id": package.get("package_id"),
                "status": package.get("status", "planned"),
                "dispatch_mode": package.get("dispatch_mode", ""),
                "depends_on": list(package.get("depends_on") or []),
                "agent_name": agent.get("name", ""),
                "aic": agent.get("aic", ""),
                "would_call_endpoint": _agent_url_from_mapping(agent),
                "agent_rpc_called": False,
                "next_action_when_started": "POST JSON-RPC to the registered agent endpoint",
            }
        )

    result = {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "status": "planned",
        "dry_run": True,
        "agent_rpc_called": False,
        "run_directory": str(run_dir),
        "task": task,
        "platform_servers_used": {
            "mode_router": {"entrypoint": "/platform/tasks/dry-run", "base_url": "http://127.0.0.1:18080"},
            "registry": {"base_url": registry_url, "query": "/api/agent/public/recent"},
            "discovery": {"url": discovery_url, "stats_checked": bool(discovery_stats)},
        },
        "flow": flow,
        "processing_steps": process_steps,
        "summary": {
            "registry_candidates": len(items),
            "normalized_skill_count": len(normalized["skills"]),
            "work_package_count": len(plan.get("work_packages") or []),
            "discovery_error_count": len([err for err in errors if err["stage"].startswith("discovery")]),
            "registry_error_count": len([err for err in errors if err["stage"].startswith("registry")]),
        },
        "route_classification": route_classification,
        "decision": decision.to_dict(),
        "plan": plan,
        "execution": execution,
        "registry_response_meta": {
            "total": registry_response.get("total"),
            "page_num": registry_response.get("page_num"),
            "page_size": registry_response.get("page_size"),
        },
        "discovery_request": discovery_request,
        "discovery_stats": discovery_stats,
        "errors": errors,
    }

    _write_json_file(run_dir / "02_registry_public_recent.json", registry_response)
    _write_json_file(run_dir / "03_discovery_request.json", discovery_request)
    _write_json_file(run_dir / "04_discovery_response.json", discovery_response)
    _write_json_file(run_dir / "05_discovery_stats.json", discovery_stats)
    _write_json_file(run_dir / "06_processing_steps.json", process_steps)
    _write_json_file(run_dir / "07_mode_router_plan.json", plan)
    _write_json_file(run_dir / "08_processing_flow.json", result)
    return result


def build_handler():
    class ModeRouterHandler(BaseHTTPRequestHandler):
        server_version = f"{SERVICE_NAME}/{SERVICE_VERSION}"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_json(self, status_code: int, payload: Mapping[str, Any]) -> None:
            body = _json_bytes(payload)
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            if getattr(self, "_event_method", "") != "POST":
                return
            path = getattr(self, "_event_path", "")
            task = getattr(self, "_event_task", "")
            started = getattr(self, "_event_started", None)
            duration_ms = round((time.perf_counter() - started) * 1000) if started else None
            decision = payload.get("decision") if isinstance(payload.get("decision"), Mapping) else {}
            plan = payload.get("plan") if isinstance(payload.get("plan"), Mapping) else {}
            route_classification = payload.get("route_classification") if isinstance(payload.get("route_classification"), Mapping) else {}
            level = "success" if int(status_code) < 400 else "error"
            title = "Mode Router 处理完成" if level == "success" else "Mode Router 处理失败"
            message = f"{path} 返回 HTTP {int(status_code)}。"
            if task:
                message = f"{message} task={task[:60]}"
            _post_runtime_event(
                event_type="mode_router.request.completed" if level == "success" else "mode_router.request.failed",
                level=level,
                title=title,
                message=message,
                extra={
                    "stage": "http-post",
                    "path": path,
                    "statusCode": int(status_code),
                    "durationMs": duration_ms,
                    "task": task,
                    "route": route_classification.get("label") or decision.get("label") or "",
                    "mode": decision.get("mode") or "",
                    "source": payload.get("source") or "",
                    "normalizedSkillCount": payload.get("normalized_skill_count"),
                    "planSteps": len(plan.get("steps") or []) if plan else 0,
                    "error": payload.get("error") or "",
                },
            )

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/health":
                self._send_json(HTTPStatus.OK, {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION})
                return
            if path == "/traffic/snapshot":
                self._send_json(HTTPStatus.OK, get_traffic_snapshot())
                return
            if path in {"/traffic/mode2", "/traffic/platform/mode2"}:
                snapshot = get_traffic_snapshot()
                platform = dict(snapshot.get("platform_mode2_group_chat") or {})
                platform["window"] = {
                    "tokens_total": snapshot.get("global_tokens_total", 0),
                    "messages_total": snapshot.get("messages_total", 0),
                    "global_tps": snapshot.get("global_tps", 0),
                    "window_seconds": snapshot.get("window_seconds", 0),
                    "edges": snapshot.get("edges", []),
                }
                self._send_json(HTTPStatus.OK, platform)
                return
            if path in {"/workflow/monitor", "/monitor"}:
                snapshot = _latest_run_snapshot()
                body = _monitor_page(snapshot).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path in {"/workflow/latest", "/workflow/status"}:
                self._send_json(HTTPStatus.OK, _latest_run_snapshot())
                return
            if path == "/workflow/latest/events":
                snapshot = _latest_run_snapshot()
                self._send_json(HTTPStatus.OK, {"events": snapshot.get("events", [])})
                return
            if path == "/platform/tasks/latest":
                self._send_json(HTTPStatus.OK, _latest_platform_snapshot())
                return
            if path == "/orchestrator/contract":
                self._send_json(HTTPStatus.OK, {"service": SERVICE_NAME, "version": SERVICE_VERSION, "connector_contract": get_placeholder_connector_contract()})
                return

            if path.startswith("/reports/"):
                parts = path.split("/", 3)
                if len(parts) != 4 or not parts[2] or not parts[3]:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_path"})
                    return
                _, _, report_id, filename = parts
                reports_root = (Path(__file__).resolve().parent / "reports").resolve()
                safe_path = (reports_root / report_id / filename).resolve()
                if safe_path.parent != reports_root / report_id:
                    self._send_json(HTTPStatus.FORBIDDEN, {"error": "path_traversal"})
                    return
                if not safe_path.is_file():
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "file_not_found", "path": str(safe_path)})
                    return
                mime_map = {
                    ".json": "application/json; charset=utf-8",
                    ".md": "text/markdown; charset=utf-8",
                    ".html": "text/html; charset=utf-8",
                    ".txt": "text/plain; charset=utf-8",
                }
                mime = mime_map.get(safe_path.suffix.lower(), "application/octet-stream")
                body = safe_path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            if path == "/fetch_agent_file":
                # GET /fetch_agent_file?endpoint=<rpc_url>&path=<file_path>
                # Forwards a file fetch to the partner agent's /files/{path} endpoint.
                # The agent (e.g. frontend_engineer on .1:8026) must expose a
                # GET /files/{path:path} route. The chat view uses this when the
                # user clicks the "📥 下载" button on a file-path artifact.
                from urllib.parse import parse_qsl
                qs = urlparse(self.path).query
                params = dict(parse_qsl(qs))
                endpoint = (params.get("endpoint") or "").strip()
                file_path = (params.get("path") or "").strip()
                if not endpoint or not file_path:
                    self._send_json(HTTPStatus.BAD_REQUEST, {
                        "error": "missing_params",
                        "message": "endpoint and path query parameters are required",
                    })
                    return
                endpoint_match = re.match(r"^(https?://[^/]+)/agents/.*$", endpoint)
                if not endpoint_match:
                    self._send_json(HTTPStatus.BAD_REQUEST, {
                        "error": "bad_endpoint",
                        "message": "endpoint must look like http(s)://host:port/agents/<name>/rpc",
                    })
                    return
                base = endpoint_match.group(1)
                if not file_path.startswith("/"):
                    file_path = "/" + file_path
                file_url = base + "/files" + file_path
                try:
                    fetch_req = urllib.request.Request(file_url, method="GET")
                    with urllib.request.urlopen(fetch_req, timeout=10) as upstream:
                        body = upstream.read()
                        upstream_ct = upstream.headers.get("Content-Type", "application/octet-stream")
                except urllib.error.HTTPError as up_err:
                    self._send_json(up_err.code, {
                        "error": "agent_fetch_failed",
                        "agent_url": file_url,
                        "agent_status": up_err.code,
                    })
                    return
                except Exception as up_exc:
                    self._send_json(HTTPStatus.BAD_GATEWAY, {
                        "error": "agent_fetch_error",
                        "agent_url": file_url,
                        "message": str(up_exc),
                    })
                    return
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", upstream_ct or "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Expose-Headers", "Content-Type, Content-Length")
                self.end_headers()
                self.wfile.write(body)
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            self._event_method = "POST"
            self._event_path = path
            self._event_started = time.perf_counter()
            self._event_task = ""
            try:
                payload = _read_json(self)
                if isinstance(payload, Mapping):
                    self._event_task = str(payload.get("task") or payload.get("task_description") or payload.get("query") or "")
                save_report = bool(payload.get("save_report", True))

                if path == "/platform/tasks/dry-run":
                    task = payload.get("task") or payload.get("task_description") or payload.get("query") or ""
                    if not task:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "missing_task", "message": "task/task_description/query is required."})
                        return
                    registry_url = _registry_url_from_payload(payload) or "http://127.0.0.1:8001"
                    discovery_url = str(
                        payload.get("discovery_url")
                        or payload.get("discoveryUrl")
                        or "http://127.0.0.1:8005/acps-adp-v2/discover"
                    ).rstrip("/")
                    response = _build_platform_processing_flow(
                        task=task,
                        registry_url=registry_url,
                        discovery_url=discovery_url,
                        payload=payload,
                    )
                    self._send_json(HTTPStatus.OK, response)
                    return

                if path == "/mode/classify":
                    task = payload.get("task") or payload.get("task_description") or payload.get("query") or ""
                    if not task:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "missing_task", "message": "task/task_description/query is required."})
                        return
                    route_classification = classify_task_route(task, payload=payload).to_dict()
                    decision = _classification_decision(task, route_classification)
                    response = _response_shell("route_classifier", 0, decision.to_dict())
                    response["route_classification"] = route_classification
                    if route_classification["label"] == ROUTE_LLM:
                        response["plan"] = build_execution_plan(task, [], decision=decision)
                        response["zh"]["plan"] = summarize_plan_zh(response["plan"])
                    self._send_json(HTTPStatus.OK, _finalize_response(response, save_report))
                    return

                if path == "/pipeline/registry":
                    task = payload.get("task") or payload.get("task_description") or payload.get("query") or ""
                    registry_url = _registry_url_from_payload(payload)
                    registry_token = _registry_token_from_payload(payload)
                    registry_response = payload.get("registry_discovery_response") or payload.get("registryDiscoveryResponse")
                    if not task:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "missing_task", "message": "task/task_description/query is required."})
                        return

                    route_classification = classify_task_route(task, payload=payload).to_dict()
                    if route_classification["label"] == ROUTE_LLM:
                        decision = _classification_decision(task, route_classification)
                        response = _response_shell("registry_pipeline", 0, decision.to_dict())
                        response["route_classification"] = route_classification
                        response["registry_discovery_response"] = registry_response or {}
                        response["plan"] = build_execution_plan(task, [], decision=decision)
                        response["dispatch_views"] = {}
                        response["zh"]["plan"] = summarize_plan_zh(response["plan"])
                        self._send_json(HTTPStatus.OK, _finalize_response(response, save_report))
                        return

                    if not registry_response and not registry_url:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "missing_registry_url", "message": "registry_url/registry_base_url is required unless registry_discovery_response is provided."})
                        return

                    if not registry_response:
                        try:
                            registry_response = call_registry_discovery(
                                registry_url,
                                limit=int(payload.get("limit", 25)),
                                requester_user_id=_requester_user_id_from_payload(payload),
                                auth_token=registry_token,
                                timeout=float(payload.get("timeout", 120)),
                                retries=int(payload.get("retries", 1)),
                                retry_backoff=float(payload.get("retry_backoff", payload.get("retryBackoff", 2))),
                            )
                            normalized = normalize_request_payload(
                                {
                                    "task": task,
                                    "hints": payload.get("hints") or {},
                                    "config": payload.get("config") or {},
                                    "registry_discovery_response": registry_response,
                                }
                            )
                            if not normalized["skills"] and _registry_public_recent_fallback_enabled(payload):
                                normalized, public_context = _normalize_from_registry_public_recent(task, payload, registry_url)
                                public_context["candidate_source"] = "registry_public_recent_after_empty_registry_discovery"
                                public_context["registry_discovery_response"] = registry_response
                                registry_response = public_context["registry_public_recent_response"]
                        except RegistryCallError as exc:
                            if not _registry_public_recent_fallback_enabled(payload):
                                raise
                            normalized, public_context = _normalize_from_registry_public_recent(task, payload, registry_url)
                            public_context["candidate_source"] = "registry_public_recent_after_registry_discovery_error"
                            public_context["registry_discovery_error"] = str(exc)
                            registry_response = public_context["registry_public_recent_response"]
                    else:
                        normalized = normalize_request_payload(
                            {
                                "task": task,
                                "hints": payload.get("hints") or {},
                                "config": payload.get("config") or {},
                                "registry_discovery_response": registry_response,
                            }
                        )
                    decision = _decide_with_route_classification(
                        normalized["task"],
                        normalized["skills"],
                        normalized["hints"],
                        normalized["config"],
                        route_classification,
                    )
                    response = _response_shell("registry_pipeline", len(normalized["skills"]), decision.to_dict())
                    response["route_classification"] = route_classification
                    response["registry_discovery_response"] = registry_response
                    plan = build_execution_plan(normalized["task"], normalized["skills"], hints=normalized["hints"], config=normalized["config"], decision=decision)
                    dispatch_views = _dispatch_views_for_plan(registry_url, plan, payload)
                    if dispatch_views:
                        plan = annotate_plan_with_dispatch_guards(plan, dispatch_views)
                    response["plan"] = plan
                    response["dispatch_views"] = dispatch_views
                    response["zh"]["plan"] = summarize_plan_zh(plan)
                    self._send_json(HTTPStatus.OK, _finalize_response(response, save_report))
                    return

                if path == "/orchestrator/dispatch/check":
                    registry_url = _registry_url_from_payload(payload)
                    registry_token = _registry_token_from_payload(payload)
                    requester_user_id = _requester_user_id_from_payload(payload)
                    aics = payload.get("aics") or payload.get("agents") or []
                    if not registry_url:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "missing_registry_url", "message": "registry_url/registry_base_url is required."})
                        return
                    dispatch_views = {
                        str(aic): call_registry_dispatch(
                            registry_url,
                            str(aic),
                            requester_user_id=requester_user_id,
                            auth_token=registry_token,
                            timeout=float(payload.get("timeout", 120)),
                            retries=int(payload.get("retries", 1)),
                            retry_backoff=float(payload.get("retry_backoff", payload.get("retryBackoff", 2))),
                        )
                        for aic in aics
                    }
                    blocked = []
                    for aic, view in dispatch_views.items():
                        result = view.get("result") if isinstance(view.get("result"), Mapping) else view
                        if not bool((result or {}).get("eligibleForDispatch")):
                            blocked.append({"aic": aic, "reasons": list((result or {}).get("reasons") or [])})
                    self._send_json(HTTPStatus.OK, {"status": "blocked" if blocked else "passed", "blocked": blocked, "dispatch_views": dispatch_views})
                    return

                if path == "/registry/runtime-review/schedule":
                    registry_url = _registry_url_from_payload(payload)
                    registry_token = _registry_token_from_payload(payload)
                    if not registry_url:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "missing_registry_url", "message": "registry_url/registry_base_url is required."})
                        return
                    schedule_payload = dict(payload.get("schedule") or {})
                    if "syncCertificates" in payload:
                        schedule_payload["syncCertificates"] = payload["syncCertificates"]
                    if "sync_certificates" in payload:
                        schedule_payload["syncCertificates"] = payload["sync_certificates"]
                    registry_response = call_registry_runtime_review_schedule(
                        registry_url,
                        schedule_payload,
                        auth_token=registry_token,
                        timeout=float(payload.get("timeout", 120)),
                        retries=int(payload.get("retries", 1)),
                        retry_backoff=float(payload.get("retry_backoff", payload.get("retryBackoff", 2))),
                    )
                    self._send_json(HTTPStatus.OK, registry_response)
                    return

                if path == "/pipeline/discovery":
                    discovery_url = payload.get("discovery_url") or payload.get("discoveryUrl")
                    task = payload.get("task") or payload.get("task_description") or payload.get("query") or ""
                    if not discovery_url:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "missing_discovery_url", "message": "discovery_url is required."})
                        return
                    if not task:
                        self._send_json(HTTPStatus.BAD_REQUEST, {"error": "missing_task", "message": "task/task_description/query is required."})
                        return

                    discovery_request = build_discovery_request(task, payload)
                    discovery_response = call_discovery(
                        discovery_url,
                        discovery_request,
                        timeout=float(payload.get("timeout", 120)),
                        retries=int(payload.get("retries", 1)),
                        retry_backoff=float(payload.get("retry_backoff", 2)),
                    )
                    normalized = normalize_request_payload(
                        {
                            "task": task,
                            "hints": payload.get("hints") or {},
                            "config": payload.get("config") or {},
                            "discovery_response": discovery_response,
                        }
                    )
                    decision = decide_mode(normalized["task"], normalized["skills"], hints=normalized["hints"], config=normalized["config"])
                    response = _response_shell("discovery_pipeline", len(normalized["skills"]), decision.to_dict())
                    response["discovery_request"] = discovery_request
                    response["discovery_response"] = discovery_response
                    plan = build_execution_plan(normalized["task"], normalized["skills"], hints=normalized["hints"], config=normalized["config"], decision=decision)
                    response["plan"] = plan
                    response["zh"]["plan"] = summarize_plan_zh(plan)
                    self._send_json(HTTPStatus.OK, _finalize_response(response, save_report))
                    return

                normalized = normalize_request_payload(payload)
                task = normalized["task"]
                skills = normalized["skills"]
                hints = normalized["hints"]
                config = normalized["config"]

                if path not in {"/mode/decide", "/orchestrator/plan", "/orchestrator/execute"}:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found", "path": path})
                    return
                if not task:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "missing_task", "message": "task/task_description/query is required."})
                    return

                if path == "/orchestrator/execute":
                    response = _build_orchestrator_execute_response(task, payload)
                    self._send_json(HTTPStatus.OK, _finalize_response(response, save_report))
                    return

                decision = decide_mode(task, skills, hints=hints, config=config)
                response = _response_shell(normalized["source"], len(skills), decision.to_dict())

                if path == "/mode/decide":
                    self._send_json(HTTPStatus.OK, _finalize_response(response, save_report))
                    return

                plan = build_execution_plan(task, skills, hints=hints, config=config, decision=decision)
                response["plan"] = plan
                response["zh"]["plan"] = summarize_plan_zh(plan)

                if path == "/orchestrator/plan":
                    self._send_json(HTTPStatus.OK, _finalize_response(response, save_report))
                    return

            except DiscoveryCallError as exc:
                self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "discovery_call_failed", "message": str(exc)})
            except RegistryCallError as exc:
                self._send_json(HTTPStatus.BAD_GATEWAY, {"error": "registry_call_failed", "message": str(exc)})
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request", "message": str(exc)})
            except json.JSONDecodeError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json", "message": str(exc)})
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error", "message": str(exc)})

    return ModeRouterHandler


def create_server(host: str = "127.0.0.1", port: int = 18080) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), build_handler())


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the mode router standalone HTTP service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args()
    server = create_server(args.host, args.port)
    print(f"{SERVICE_NAME} listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
