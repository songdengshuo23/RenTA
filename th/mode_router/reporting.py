\
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4


def _reports_dir() -> Path:
    root = Path(__file__).resolve().parent / "reports"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_report_bundle(payload: Mapping[str, Any]) -> dict[str, str]:
    report_id = f"report_{_timestamp()}_{uuid4().hex[:6]}"
    root = _reports_dir() / report_id
    root.mkdir(parents=True, exist_ok=True)

    json_path = root / "result.json"
    md_path = root / "result_zh.md"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_markdown_report(payload), encoding="utf-8")

    return {
        "report_id": report_id,
        "directory": str(root),
        "json": str(json_path),
        "markdown": str(md_path),
    }


def build_markdown_report(payload: Mapping[str, Any]) -> str:
    decision = payload.get("decision") or {}
    plan = payload.get("plan") or {}
    zh = payload.get("zh") or {}
    zh_decision = zh.get("decision") or {}
    zh_plan = zh.get("plan") or {}
    lines = []
    lines.append("# ??????")
    lines.append("")
    lines.append(f"- ?????`{payload.get('version', '')}`")
    lines.append(f"- ???`{payload.get('source', '')}`")
    lines.append(f"- ??????`{payload.get('normalized_skill_count', 0)}`")
    lines.append("")
    lines.append("## ????")
    lines.append("")
    lines.append(f"- ???{zh_decision.get('??', decision.get('mode', ''))}")
    lines.append(f"- ????{zh_decision.get('???', decision.get('next_step', ''))}")
    lines.append(f"- ???{zh_decision.get('??', decision.get('summary', ''))}")
    lines.append("")
    lines.append("### ????")
    lines.append("")
    for item in zh_decision.get('??', []) or decision.get('reasoning', []):
        lines.append(f"- {item}")
    lines.append("")
    evidence = zh_decision.get('??', {})
    if evidence:
        lines.append("### ????")
        lines.append("")
        lines.append(f"- ??????{evidence.get('?????', '')}")
        lines.append(f"- ??Agent??{evidence.get('??Agent?', '')}")
        best = evidence.get('???Agent', {})
        if best:
            lines.append(f"- ???Agent?{best.get('??', '')}?AIC: `{best.get('AIC', '')}`????: {best.get('???', '')}?")
        lines.append("")

    if plan:
        lines.append("## ????")
        lines.append("")
        lines.append(f"- ?????{zh_plan.get('????', plan.get('strategy', ''))}")
        lines.append(f"- ???{zh_plan.get('??', plan.get('summary', ''))}")
        coord = zh_plan.get('???', {})
        if coord:
            lines.append(f"- ????{coord.get('??', '')}?AIC: `{coord.get('AIC', '')}`?")
        lines.append(f"- ??????{zh_plan.get('?????', len(plan.get('work_packages', [])))}")
        lines.append("")
        lines.append("### ??")
        lines.append("")
        for phase in zh_plan.get('??', []):
            lines.append(f"- `{phase.get('??', '')}`?{phase.get('??', '')}?????{phase.get('???', '')}")
        lines.append("")

    execution = payload.get('execution')
    zh_execution = zh.get('execution') or {}
    if execution:
        lines.append("## ????")
        lines.append("")
        lines.append(f"- ?????{zh_execution.get('????', execution.get('status', ''))}")
        lines.append(f"- ?????{zh_execution.get('????', execution.get('dry_run', ''))}")
        lines.append(f"- ?????{zh_execution.get('????', len(execution.get('runs', [])))}")
        lines.append(f"- ?????{zh_execution.get('????', '')}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"
