from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

ROUTE_LLM = "LLM"
ROUTE_AGENT = "Agent"
ROUTE_MULTI_AGENT = "多Agent"
ROUTE_LABELS = (ROUTE_LLM, ROUTE_AGENT, ROUTE_MULTI_AGENT)

ROUTE_TO_MODE = {
    ROUTE_LLM: "mode_0",
    ROUTE_AGENT: "mode_1",
    ROUTE_MULTI_AGENT: "mode_2",
}


@dataclass(frozen=True)
class RouteClassification:
    scores: dict[str, float]
    label: str
    mode: str
    next_step: str
    summary: str
    reasoning: list[str]
    prompt_source: str
    llm_used: bool
    model: str
    raw_response: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scores": self.scores,
            "label": self.label,
            "mode": self.mode,
            "next_step": self.next_step,
            "summary": self.summary,
            "reasoning": self.reasoning,
            "prompt_source": self.prompt_source,
            "llm_used": self.llm_used,
            "model": self.model,
            "raw_response": self.raw_response,
        }


class RouteClassifierError(RuntimeError):
    pass


def classify_task_route(
    task: str,
    *,
    prompt_path: str | Path | None = None,
    payload: Mapping[str, Any] | None = None,
) -> RouteClassification:
    payload = payload or {}
    task = str(task or "").strip()
    if not task:
        raise ValueError("task is required for route classification")

    prompt_path = _prompt_path(prompt_path or payload.get("route_prompt_path") or payload.get("routePromptPath"))
    prompt_text = _read_prompt(prompt_path)

    override_scores = _scores_from_mapping(payload.get("route_scores") or payload.get("routeScores"))
    if override_scores:
        return _build_classification(override_scores, prompt_path, llm_used=False, model="override", raw_response=None)

    fallback_reasons: list[str] = []
    try:
        llm_result = _call_route_llm(task, prompt_text, payload)
    except RouteClassifierError:
        llm_result = None
        fallback_reasons.append("Route LLM unavailable; local rule fallback used.")
    if llm_result is not None:
        scores, raw_response, model = llm_result
        return _build_classification(scores, prompt_path, llm_used=True, model=model, raw_response=raw_response)

    scores, reasons = _fallback_scores(task)
    classification = _build_classification(scores, prompt_path, llm_used=False, model="local-rule-fallback", raw_response=None)
    return RouteClassification(
        **{
            **classification.to_dict(),
            "reasoning": classification.reasoning + reasons + fallback_reasons,
        }
    )


def build_llm_direct_plan(task: str, classification: Mapping[str, Any] | None = None) -> dict[str, Any]:
    from datetime import datetime, timezone
    from uuid import uuid4

    return {
        "plan_id": f"plan-{uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": ROUTE_TO_MODE[ROUTE_LLM],
        "strategy": "llm_direct_answer",
        "status": "planned",
        "summary": "LLM direct-answer route selected; no Registry agent dispatch is required.",
        "route_classification": dict(classification or {}),
        "work_packages": [],
        "phases": [
            {
                "phase": "answer",
                "owner": {"type": "llm"},
                "description": "Answer the user task directly with the base model without external tools.",
            }
        ],
        "task": task,
    }


def _prompt_path(value: Any) -> Path:
    if value:
        return Path(str(value))
    base_dir = Path(__file__).resolve().parent
    prompt_path = base_dir / "路由prompt.md"
    if prompt_path.exists():
        return prompt_path
    return base_dir / "模式路由.md"


def _read_prompt(path: Path) -> str:
    if not path.exists():
        raise RouteClassifierError(f"route prompt document not found: {path}")
    return _extract_prompt_body(path.read_text(encoding="utf-8"))


def _extract_prompt_body(document: str) -> str:
    fenced_blocks = re.findall(r"```(?:[^\n`]*)\n(.*?)```", document, re.DOTALL)
    for block in fenced_blocks:
        if "{question}" in block:
            return block.strip()
    return document.strip()


def _scores_from_mapping(raw: Any) -> dict[str, float] | None:
    if not isinstance(raw, Mapping):
        return None
    scores: dict[str, float] = {}
    for label in ROUTE_LABELS:
        if label not in raw:
            return None
        try:
            scores[label] = max(0.0, min(1.0, float(raw[label])))
        except (TypeError, ValueError):
            return None
    return scores


def _call_route_llm(task: str, prompt_text: str, payload: Mapping[str, Any]) -> tuple[dict[str, float], Any, str] | None:
    endpoint = str(
        payload.get("route_llm_url")
        or payload.get("routeLlmUrl")
        or os.getenv("ROUTER_LLM_URL")
        or os.getenv("LLM_API_URL")
        or ""
    ).strip()
    api_key = str(
        payload.get("route_llm_api_key")
        or payload.get("routeLlmApiKey")
        or os.getenv("ROUTER_LLM_API_KEY")
        or os.getenv("LLM_API_KEY")
        or os.getenv("DEEPSEEK_API_KEY")
        or ""
    ).strip()
    model = str(
        payload.get("route_llm_model")
        or payload.get("routeLlmModel")
        or os.getenv("ROUTER_LLM_MODEL")
        or os.getenv("LLM_MODEL")
        or "deepseek-chat"
    ).strip()
    if not endpoint or not api_key:
        return None

    if endpoint.rstrip("/").endswith("/chat/completions"):
        url = endpoint.rstrip("/")
    else:
        url = f"{endpoint.rstrip('/')}/chat/completions"

    prompt = _route_prompt(prompt_text, task)
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    timeout = float(payload.get("route_llm_timeout", payload.get("routeLlmTimeout", 60)))
    retries = int(payload.get("route_llm_retries", payload.get("routeLlmRetries", 1)))

    last_error = ""
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw_response = json.loads(response.read().decode("utf-8"))
            scores = _extract_scores(raw_response)
            if scores:
                return scores, raw_response, model
            last_error = "LLM response did not contain route scores"
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='ignore')}"
        except Exception as exc:
            last_error = str(exc)
        if attempt < retries:
            time.sleep(1 + attempt)

    raise RouteClassifierError(last_error or "route LLM call failed")


def _route_prompt(prompt_text: str, task: str) -> str:
    if "{question}" in prompt_text:
        return prompt_text.replace("{question}", task)
    return (
        f"{prompt_text}\n\n"
        "请只根据上面的三档定义输出一个 JSON 对象，字段必须是 "
        '{"LLM": float, "Agent": float, "多Agent": float}。\n\n'
        f"用户任务：\n{task}"
    )


def _extract_scores(raw_response: Any) -> dict[str, float] | None:
    if isinstance(raw_response, Mapping):
        direct = _scores_from_mapping(raw_response)
        if direct:
            return direct
        choices = raw_response.get("choices")
        if isinstance(choices, list) and choices:
            content = ((choices[0] or {}).get("message") or {}).get("content")
            if isinstance(content, str):
                return _parse_scores_from_text(content)
    if isinstance(raw_response, str):
        return _parse_scores_from_text(raw_response)
    return None


def _parse_scores_from_text(text: str) -> dict[str, float] | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return _scores_from_mapping(parsed)


def _fallback_scores(task: str) -> tuple[dict[str, float], list[str]]:
    text = task.lower()
    multi_terms = [
        "multi-agent",
        "multi agent",
        "multiple agents",
        "multiple specialist",
        "specialist agents",
        "specialist roles",
        "independent roles",
        "independent verification",
        "work together",
        "collaborate",
        "collaboration",
        "backend services",
        "message queue",
        "registry discovery",
        "service health",
        "operations report",
        "多角色",
        "多agent",
        "多 agent",
        "跨角色",
        "协作",
        "前端",
        "后端",
        "运维",
        "法务",
        "财务",
        "安全",
        "审查",
        "验证",
        "架构",
        "系统设计",
        "分工",
    ]
    agent_terms = [
        "搜索",
        "联网",
        "最新",
        "运行",
        "执行",
        "代码",
        "文件",
        "api",
        "接口",
        "数据库",
        "部署",
        "读取",
        "写入",
    ]
    llm_terms = ["解释", "改写", "翻译", "总结", "创意", "推理", "概念", "定义"]

    multi_hits = [term for term in multi_terms if term in text]
    agent_hits = [term for term in agent_terms if term in text]
    llm_hits = [term for term in llm_terms if term in text]
    reasons: list[str] = []

    if multi_hits:
        reasons.append(f"Local fallback matched multi-role terms: {', '.join(multi_hits[:5])}.")
        return {ROUTE_LLM: 0.05, ROUTE_AGENT: 0.15, ROUTE_MULTI_AGENT: 0.90}, reasons
    if agent_hits:
        reasons.append(f"Local fallback matched tool-use terms: {', '.join(agent_hits[:5])}.")
        return {ROUTE_LLM: 0.10, ROUTE_AGENT: 0.88, ROUTE_MULTI_AGENT: 0.22}, reasons
    if llm_hits:
        reasons.append(f"Local fallback matched direct-LLM terms: {', '.join(llm_hits[:5])}.")
    else:
        reasons.append("Local fallback found no external-tool or multi-role signal.")
    return {ROUTE_LLM: 0.90, ROUTE_AGENT: 0.20, ROUTE_MULTI_AGENT: 0.05}, reasons


def _build_classification(
    scores: Mapping[str, float],
    prompt_path: Path,
    *,
    llm_used: bool,
    model: str,
    raw_response: Any,
) -> RouteClassification:
    normalized = {label: max(0.0, min(1.0, float(scores[label]))) for label in ROUTE_LABELS}
    label = max(ROUTE_LABELS, key=lambda item: normalized[item])
    mode = ROUTE_TO_MODE[label]
    next_step = {
        ROUTE_LLM: "llm_direct",
        ROUTE_AGENT: "skill_router",
        ROUTE_MULTI_AGENT: "orchestrator",
    }[label]
    summary = {
        ROUTE_LLM: "Route as LLM because the task can be answered without external tools.",
        ROUTE_AGENT: "Route as Agent because the task needs tools but one professional role can complete it.",
        ROUTE_MULTI_AGENT: "Route as multi-agent because the task requires multiple specialist roles or independent verification.",
    }[label]
    reasoning = [
        "Classification follows 模式路由.md: LLM means no external tools, Agent means one tool-using professional role, 多Agent means multiple roles or independent verification.",
        f"Top route score is {label}={normalized[label]:.2f}.",
    ]
    return RouteClassification(
        scores=normalized,
        label=label,
        mode=mode,
        next_step=next_step,
        summary=summary,
        reasoning=reasoning,
        prompt_source=str(prompt_path),
        llm_used=llm_used,
        model=model,
        raw_response=raw_response,
    )
