from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
WORKSPACE_ROOT = HERE.parent.parent
SDK_PATH = WORKSPACE_ROOT / 'ACPs_update_code' / 'ACPs-SDK'
DEFAULT_ENV_FILE = WORKSPACE_ROOT / 'yhl' / 'ACPs-Discovery-Server' / '.env'
RUNS_DIR = HERE / 'literature_runs'
DISCOVERY_URL = 'http://127.0.0.1:8005/acps-adp-v2/discover'

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from adapters import normalize_request_payload
from discovery_client import build_discovery_request, call_discovery
from mode_selector import MODE_2, decide_mode
from orchestrator import build_execution_plan, build_orchestration_spec

ROLE_ORDER = ['search', 'analysis', 'writing']
ROLE_GROUP_KEYS = {
    'search': 'search',
    'analysis': 'analysis',
    'writing': 'writing',
}
ROLE_KEYWORDS = {
    'search': ['literature_search', 'search'],
    'analysis': ['literature_analysis', 'analysis', 'deep-reading'],
    'writing': ['literature_writing', 'writing'],
}
LITERATURE_KEYWORDS = ['literature_', 'literature search', 'literature analysis', 'literature writing', 'academic review', 'survey writing']


@dataclass
class AgentRef:
    role: str
    aic: str
    name: str
    url: str
    skill_ids: list[str]
    skill_names: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GroupAgentRef:
    role: str
    aic: str
    name: str
    url: str
    skill_ids: list[str]
    skill_names: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_value(state: Any) -> str:
    return getattr(state, 'value', str(state))


def _slug(text: str, limit: int = 40) -> str:
    cleaned = re.sub(r'[^0-9A-Za-z一-鿿]+', '_', text).strip('_')
    return (cleaned or 'task')[:limit]


def _ensure_run_dir(task: str) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = RUNS_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{_slug(task)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding='utf-8')


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + '\n')


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _serialize_task(task: Any) -> dict[str, Any]:
    if hasattr(task, 'model_dump'):
        return task.model_dump(mode='json', exclude_none=True)
    return {'repr': repr(task)}


def _extract_text(task: Any) -> str:
    status = getattr(task, 'status', None)
    if status:
        for item in getattr(status, 'dataItems', []) or []:
            text = getattr(item, 'text', None)
            if text:
                return text
    for product in getattr(task, 'products', []) or []:
        for item in getattr(product, 'dataItems', []) or []:
            text = getattr(item, 'text', None)
            if text:
                return text
    return ''


def _load_env_defaults(env_file: Path = DEFAULT_ENV_FILE) -> dict[str, str]:
    env: dict[str, str] = {}
    if not env_file.exists():
        return env
    for line in env_file.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def _planner_config() -> dict[str, str]:
    defaults = _load_env_defaults()
    api_url = os.getenv('LITERATURE_LLM_URL') or os.getenv('LLM_API_URL')
    api_key = os.getenv('LITERATURE_LLM_KEY') or os.getenv('LLM_API_KEY')
    model = os.getenv('LITERATURE_LLM_MODEL') or os.getenv('LLM_MODEL')

    if not api_url:
        base_url = defaults.get('OPENAI_BASE_URL')
        if base_url:
            api_url = base_url.rstrip('/') + '/chat/completions'
        else:
            api_url = defaults.get('DASHSCOPE_API_URL', '')
    if not api_key:
        api_key = defaults.get('OPENAI_API_KEY') or defaults.get('DASHSCOPE_API_KEY', '')
    if not model:
        model = defaults.get('LITERATURE_LLM_MODEL') or 'GLM-4.7-Flash'

    return {'api_url': api_url, 'api_key': api_key, 'model': model}


def _fallback_decomposition(task: str) -> dict[str, Any]:
    return {
        'method': 'fallback',
        'topic': task,
        'objective': '围绕用户主题完成文献检索、脉络分析和综述初稿。',
        'search_scope': '覆盖近年高相关论文、综述、关键方法和代表性应用。',
        'analysis_focus': ['研究背景', '关键方法', '主要结论', '争议与不足', '未来方向'],
        'writing_requirements': ['结构清晰', '证据充分', '引用线索明确', '保留局限性讨论'],
        'expected_sections': ['摘要', '背景', '方法进展', '核心发现', '争议与挑战', '未来方向', '结论'],
        'recommended_skill_count': 3,
        'requires_independent_roles': True,
        'parallelizable': False,
        'notes': 'LLM 不可用时使用保守默认拆解。',
    }


def _parse_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


async def decompose_requirement(task: str) -> dict[str, Any]:
    planner = _planner_config()
    if not planner['api_url'] or not planner['api_key']:
        result = _fallback_decomposition(task)
        result['llm_used'] = False
        return result

    prompt = f'''你是文献综述工作流的任务拆解器。
请把用户任务拆解为检索、分析、写作三个智能体可执行的结构化计划。

用户任务：
{task}

请只返回 JSON，不要输出额外说明：
{{
  "topic": "研究主题",
  "objective": "最终目标",
  "search_scope": "检索范围与时间边界",
  "analysis_focus": ["需要分析的关键问题"],
  "writing_requirements": ["写作要求"],
  "expected_sections": ["建议章节"],
  "recommended_skill_count": 3,
  "requires_independent_roles": true,
  "parallelizable": false,
  "notes": "给 orchestrator 的补充提示"
}}'''

    try:
        import httpx

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                planner['api_url'],
                headers={
                    'Authorization': f"Bearer {planner['api_key']}",
                    'Content-Type': 'application/json',
                },
                json={
                    'model': planner['model'],
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.1,
                    'max_tokens': 2048,
                },
            )
            response.raise_for_status()
            payload = response.json()

        content = payload['choices'][0]['message']['content']
        parsed = _parse_json_object(content) or _fallback_decomposition(task)
        parsed['llm_used'] = True
        parsed['llm_model'] = planner['model']
        parsed['raw_response'] = content
        return parsed
    except Exception as exc:
        result = _fallback_decomposition(task)
        result['llm_used'] = False
        result['llm_error'] = str(exc)
        return result
    return parsed


def _skill_text(skill: Mapping[str, Any]) -> str:
    acs = skill.get('acs') or {}
    skill_blob = json.dumps(acs.get('skills', []), ensure_ascii=False)
    values = [
        skill.get('agent_name', ''),
        skill.get('skillid', ''),
        skill.get('skill_name', ''),
        skill.get('memo', ''),
        acs.get('name', ''),
        acs.get('description', ''),
        skill_blob,
    ]
    return ' '.join(values).lower()


def filter_literature_skills(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered = []
    for skill in skills:
        skillid = str(skill.get('skillid') or '').lower()
        agent_name = str(skill.get('agent_name') or '').lower()
        description = str((skill.get('acs') or {}).get('description') or '').lower()
        if skillid.startswith('literature_'):
            filtered.append(skill)
            continue
        text = ' '.join([agent_name, description, _skill_text(skill)])
        if any(keyword.lower() in text for keyword in LITERATURE_KEYWORDS):
            filtered.append(skill)
    return filtered or list(skills)


def collect_agents(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_agent: dict[str, dict[str, Any]] = {}
    for skill in skills:
        aic = str(skill.get('aic') or '')
        if not aic:
            continue
        acs = skill.get('acs') or {}
        endpoints = acs.get('endPoints') or [{}]
        agent = by_agent.setdefault(
            aic,
            {
                'aic': aic,
                'name': skill.get('agent_name') or acs.get('name') or aic,
                'url': endpoints[0].get('url', ''),
                'skills': [],
            },
        )
        agent['skills'].append(skill)
        if not agent['url']:
            agent['url'] = endpoints[0].get('url', '')
    return list(by_agent.values())


def _agent_average_score(agent: Mapping[str, Any]) -> float:
    scores: list[float] = []
    for skill in agent.get('skills', []) or []:
        score = skill.get('score')
        try:
            if score is not None:
                scores.append(float(score))
        except (TypeError, ValueError):
            continue
    return sum(scores) / len(scores) if scores else -1.0


def _agent_priority_key(agent: Mapping[str, Any]) -> tuple[int, float, str, str]:
    return (
        -len(agent.get('skills', []) or []),
        -_agent_average_score(agent),
        str(agent.get('name') or '').lower(),
        str(agent.get('aic') or ''),
    )


def _agent_to_ref(role: str, agent: Mapping[str, Any]) -> AgentRef:
    return AgentRef(
        role=role,
        aic=str(agent.get('aic') or ''),
        name=str(agent.get('name') or agent.get('aic') or ''),
        url=str(agent.get('url') or ''),
        skill_ids=[str(item.get('skillid') or '') for item in agent.get('skills', []) or [] if item.get('skillid')],
        skill_names=[str(item.get('skill_name') or '') for item in agent.get('skills', []) or [] if item.get('skill_name')],
    )


def resolve_role_agents(skills: list[dict[str, Any]]) -> dict[str, AgentRef]:
    agents = collect_agents(skills)
    if not agents:
        raise ValueError('No candidate agents were returned by discovery.')

    chosen: dict[str, AgentRef] = {}
    used: set[str] = set()
    role_skill_prefix = {
        'search': 'literature_search.',
        'analysis': 'literature_analysis.',
        'writing': 'literature_writing.',
    }

    for role in ROLE_ORDER:
        prefix = role_skill_prefix[role]
        for agent in agents:
            if agent['aic'] in used:
                continue
            skillids = [str(item.get('skillid') or '').lower() for item in agent['skills']]
            if any(skillid.startswith(prefix) for skillid in skillids):
                chosen[role] = _agent_to_ref(role, agent)
                used.add(agent['aic'])
                break

    for role in ROLE_ORDER:
        if role in chosen:
            continue
        keywords = ROLE_KEYWORDS[role]
        for agent in agents:
            text = ' '.join([agent['name'], json.dumps(agent['skills'], ensure_ascii=False)]).lower()
            if agent['aic'] in used:
                continue
            if any(keyword.lower() in text for keyword in keywords):
                chosen[role] = _agent_to_ref(role, agent)
                used.add(agent['aic'])
                break

    missing = [role for role in ROLE_ORDER if role not in chosen]
    if missing:
        fallback_agents = sorted((agent for agent in agents if agent['aic'] not in used), key=_agent_priority_key)
        for role, agent in zip(missing, fallback_agents):
            chosen[role] = _agent_to_ref(role, agent)
            used.add(agent['aic'])

        missing = [role for role in ROLE_ORDER if role not in chosen]
        if missing:
            ordered_agents = sorted(agents, key=_agent_priority_key)
            for index, role in enumerate(missing):
                agent = ordered_agents[index % len(ordered_agents)]
                chosen[role] = _agent_to_ref(role, agent)

    missing = [role for role in ROLE_ORDER if role not in chosen]
    if missing:
        raise ValueError(f'Unable to resolve role agents: {missing}')
    return chosen


def build_tree_plan(task: str, role_agents: Mapping[str, AgentRef], decision: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    orchestration_tree = dict(plan.get('orchestration_tree') or {})
    root_package = dict(plan.get('root_package') or orchestration_tree.get('root') or {})
    raw_children = list(orchestration_tree.get('children') or [])

    if not root_package:
        root_package = {
            'package_id': 'root-main-agent',
            'agent': {
                'aic': (plan.get('coordinator') or {}).get('aic', ''),
                'name': (plan.get('coordinator') or {}).get('name', 'Coordinator'),
            },
            'objective': 'Own the user task, coordinate child agents, and merge the final result.',
            'dispatch_mode': 'orchestrated',
            'children': [],
            'status': 'planned',
        }

    children_by_aic = {}
    for child in raw_children:
        agent = child.get('agent') or {}
        aic = agent.get('aic', '')
        if aic:
            children_by_aic[aic] = dict(child)

    children = []
    for role in ROLE_ORDER:
        role_agent = role_agents[role]
        child = children_by_aic.get(role_agent.aic, {})
        node_id = child.get('node_id') or f'child-{role}'
        parent_node = child.get('parent_node') or root_package.get('package_id', 'root-main-agent')
        child_record = {
            'node_id': node_id,
            'parent_node': parent_node,
            'role': role,
            'agent_name': role_agent.name,
            'agent_aic': role_agent.aic,
            'endpoint': role_agent.url,
            'input_from': child.get('input_from') or ('user_requirement' if role == 'search' else 'root_agent'),
            'output_to': child.get('output_to') or 'root_agent',
            'dispatch_mode': child.get('dispatch_mode') or ('parallel' if plan.get('strategy') == 'tree_root_parallel_children' else 'sequential'),
            'depends_on': [],
            'depends_on_roles': [],
            'source_depends_on': list(child.get('depends_on') or []),
            'objective': child.get('objective') or '',
            'skills': child.get('skills') or [],
        }
        children.append(child_record)

    role_by_node_id = {child['node_id']: child['role'] for child in children}
    node_id_by_role = {child['role']: child['node_id'] for child in children}
    previous_role = None
    for child in children:
        raw_role_deps = []
        for dep_node in child.get('source_depends_on') or []:
            dep_role = role_by_node_id.get(dep_node)
            if dep_role and dep_role != child['role'] and dep_role not in raw_role_deps:
                raw_role_deps.append(dep_role)

        if plan.get('strategy') == 'tree_root_sequential_children':
            role_deps = [previous_role] if previous_role else []
        elif raw_role_deps:
            role_deps = raw_role_deps
        elif child['role'] == 'writing':
            role_deps = [item['role'] for item in children if item['role'] != child['role']]
        else:
            role_deps = []

        child['depends_on_roles'] = role_deps
        child['depends_on'] = [node_id_by_role[role] for role in role_deps if role in node_id_by_role]
        previous_role = child['role']

    root = {
        'node_id': root_package.get('package_id', 'root-main-agent'),
        'name': (root_package.get('agent') or {}).get('name', 'Coordinator'),
        'agent_aic': (root_package.get('agent') or {}).get('aic', ''),
        'responsibility': root_package.get('objective') or '统一拆解任务、分发角色并汇总最终结果',
        'task': task,
        'mode': decision.get('mode', ''),
        'strategy': plan.get('strategy', ''),
        'dispatch_mode': root_package.get('dispatch_mode', 'orchestrated'),
        'children': [child['node_id'] for child in children],
    }
    return {
        'root': root,
        'children': children,
    }

def _status_event(
    *,
    trace_id: str,
    run_dir: Path,
    stage: str,
    state: str,
    message: str,
    role: str = '',
    agent_name: str = '',
    step_index: int | None = None,
    task_id: str = '',
) -> dict[str, Any]:
    event = {
        'timestamp': _utc_now(),
        'trace_id': trace_id,
        'stage': stage,
        'state': state,
        'message': message,
        'role': role,
        'agent_name': agent_name,
        'step_index': step_index,
        'task_id': task_id,
    }
    _append_jsonl(run_dir / '12_state_events.jsonl', event)
    print(
        f"[{state}] {stage}"
        f"{f' | role={role}' if role else ''}"
        f"{f' | agent={agent_name}' if agent_name else ''}"
        f"{f' | task_id={task_id}' if task_id else ''}"
        f" - {message}",
        flush=True,
    )
    return event
def build_workflow_hints(decomposition: Mapping[str, Any]) -> dict[str, Any]:
    return {
        'estimated_skill_count': int(decomposition.get('recommended_skill_count') or 3),
        'requires_independent_roles': bool(decomposition.get('requires_independent_roles', True)),
        'parallelizable': bool(decomposition.get('parallelizable', False)),
    }


def build_step_prompt(role: str, decomposition: Mapping[str, Any], upstream_text: str | None = None) -> str:
    topic = decomposition.get('topic') or decomposition.get('objective') or ''
    search_scope = decomposition.get('search_scope') or ''
    analysis_focus = '\n'.join(f'- {item}' for item in (decomposition.get('analysis_focus') or []))
    writing_requirements = '\n'.join(f'- {item}' for item in (decomposition.get('writing_requirements') or []))
    expected_sections = '\n'.join(f'- {item}' for item in (decomposition.get('expected_sections') or []))

    if role == 'search':
        return (
            f"请围绕“{topic}”执行文献检索与初筛。\n"
            f"检索范围：{search_scope or '优先覆盖近年高相关论文、综述和代表性方法'}\n"
            "输出 15-20 篇高相关文献，按主题、方法、结论和局限性整理。\n"
            "请保留可追踪的题名、年份、来源和简短选择理由。"
        )

    if role == 'analysis':
        return (
            "请基于上游检索结果完成文献精读与脉络归纳。\n\n"
            f"{upstream_text or ''}\n\n"
            f"分析重点：\n{analysis_focus}\n"
            "请比较主要方法、证据强度、共识与分歧，并提炼可供写作智能体使用的结构化结论。\n"
            "输出要包含关键发现、证据链和仍需谨慎表述的地方。"
        )

    return (
        "请基于上游检索和分析结果撰写综述初稿。\n\n"
        f"{upstream_text or ''}\n\n"
        f"写作要求：\n{writing_requirements}\n"
        f"建议章节：\n{expected_sections}\n"
        "请输出 Markdown 结构，包含标题、分节、关键论点和可补引用的位置。"
    )


def _role_text(role: str) -> str:
    return {
        'search': '文献检索与初筛智能体',
        'analysis': '文献精读与脉络归纳智能体',
        'writing': '综述架构撰写与润色定稿智能体',
    }.get(role, role)


def _to_group_rpc_url(agent_url: str) -> str:
    if not agent_url:
        return agent_url
    if '/agents/' in agent_url and agent_url.endswith('/rpc'):
        base = agent_url.split('/agents/')[0]
        return base.rstrip('/') + '/group/rpc'
    return agent_url.replace('/rpc', '/group/rpc') if agent_url.endswith('/rpc') else agent_url


def build_group_prompt(role: str, decomposition: Mapping[str, Any], upstream_text: str | None = None) -> str:
    base = build_step_prompt(role, decomposition, upstream_text)
    return (
        f"你是{_role_text(role)}。请只处理分配给你的角色任务，并把结果写成可被主智能体继续消费的结构化文本。\n\n"
        f"{base}\n\n"
        "输出末尾请保留一个简短的角色标签，便于主智能体追踪。"
    )


def compress_upstream_context(role: str, upstream_text: str | None, max_chars: int | None = None) -> dict[str, Any]:
    raw_text = (upstream_text or '').strip()
    if not raw_text:
        return {
            'raw_text': '',
            'compressed_text': '',
            'raw_length': 0,
            'compressed_length': 0,
            'compression_ratio': 1.0,
            'method': 'empty',
        }

    if '[REJECTED]' in raw_text:
        return {
            'raw_text': raw_text,
            'compressed_text': raw_text,
            'raw_length': len(raw_text),
            'compressed_length': len(raw_text),
            'compression_ratio': 1.0,
            'method': 'pass_through_rejected',
        }

    if role != 'writing':
        return {
            'raw_text': raw_text,
            'compressed_text': raw_text,
            'raw_length': len(raw_text),
            'compressed_length': len(raw_text),
            'compression_ratio': 1.0,
            'method': 'pass_through_non_writing',
        }

    if max_chars is None:
        max_chars = 2600

    lines = [line.rstrip() for line in raw_text.splitlines()]
    prioritized = []
    remainder = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('#') or stripped.startswith('##') or stripped.startswith('###'):
            prioritized.append(stripped)
        elif stripped.startswith('-') or stripped.startswith('*') or stripped[:2].isdigit():
            prioritized.append(stripped)
        elif '结论' in stripped or '摘要' in stripped or '关键' in stripped or '争议' in stripped:
            prioritized.append(stripped)
        else:
            remainder.append(stripped)

    seen = set()
    ordered_lines = []
    for line in prioritized + remainder:
        if line not in seen:
            ordered_lines.append(line)
            seen.add(line)

    compressed_lines = []
    current_len = 0
    for line in ordered_lines:
        extra = len(line) + (1 if compressed_lines else 0)
        if current_len + extra > max_chars:
            break
        compressed_lines.append(line)
        current_len += extra

    compressed_text = '\n'.join(compressed_lines).strip()
    if not compressed_text:
        compressed_text = raw_text[:max_chars]

    if compressed_text != raw_text and len(compressed_text) < len(raw_text):
        compressed_text = (
            "以下为上游结果压缩摘要，请优先基于这些关键信息继续执行：\n\n"
            + compressed_text
        )

    raw_length = len(raw_text)
    compressed_length = len(compressed_text)
    return {
        'raw_text': raw_text,
        'compressed_text': compressed_text,
        'raw_length': raw_length,
        'compressed_length': compressed_length,
        'compression_ratio': round((compressed_length / raw_length), 4) if raw_length else 1.0,
        'method': 'heuristic_summary_then_truncate',
    }


def build_feedback_note(role: str, previous_steps: list[Mapping[str, Any]]) -> dict[str, Any]:
    if not previous_steps:
        return {
            'has_feedback': False,
            'feedback_source_roles': [],
            'feedback_summary': '',
            'feedback_payloads': [],
        }

    payloads = []
    for step in previous_steps:
        payloads.append(
            {
                'source_role': step.get('role', ''),
                'source_agent': ((step.get('agent') or {}).get('name', '')),
                'output_length': step.get('output_length', 0),
                'final_state': step.get('final_state', ''),
                'summary': (step.get('output_text') or '')[:400],
            }
        )
    return {
        'has_feedback': True,
        'feedback_source_roles': [item['source_role'] for item in payloads if item['source_role']],
        'feedback_summary': ' | '.join(
            f"{item['source_role']}->{item['source_agent']} ({item['output_length']} chars)"
            for item in payloads
        ),
        'feedback_payloads': payloads,
    }


def build_call_graph(task: str, tree_plan: Mapping[str, Any], step_results: list[Mapping[str, Any]]) -> dict[str, Any]:
    children = list((tree_plan.get('children') or []))
    result_by_role = {item.get('role'): item for item in step_results}
    edges = []
    nodes = []

    root = tree_plan.get('root') or {}
    nodes.append(
        {
            'node_id': root.get('node_id', 'root'),
            'node_type': 'coordinator',
            'name': root.get('name', ''),
            'role': 'root',
            'dispatch_mode': root.get('dispatch_mode', ''),
            'task': task,
        }
    )

    for child in children:
        role = child.get('role', '')
        result = result_by_role.get(role, {})
        nodes.append(
            {
                'node_id': child.get('node_id', ''),
                'node_type': 'agent',
                'name': child.get('agent_name', ''),
                'role': role,
                'endpoint': child.get('endpoint', ''),
                'dispatch_mode': child.get('dispatch_mode', ''),
                'depends_on': child.get('depends_on', []),
                'status': result.get('final_state', ''),
                'duration_ms': result.get('duration_ms', 0),
                'output_length': result.get('output_length', 0),
            }
        )
        edges.append(
            {
                'from': child.get('parent_node', root.get('node_id', 'root')),
                'to': child.get('node_id', ''),
                'edge_type': 'dispatch',
                'input_from': child.get('input_from', ''),
                'output_to': child.get('output_to', ''),
            }
        )
        for dep in child.get('depends_on', []) or []:
            edges.append(
                {
                    'from': dep,
                    'to': child.get('node_id', ''),
                    'edge_type': 'dependency',
                    'input_from': dep,
                    'output_to': child.get('node_id', ''),
                }
            )
    return {'nodes': nodes, 'edges': edges}


def build_feedback_log(step_results: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    feedback_events = []
    for item in step_results:
        feedback = item.get('feedback') or {}
        feedback_events.append(
            {
                'role': item.get('role', ''),
                'agent_name': ((item.get('agent') or {}).get('name', '')),
                'received_feedback': bool(feedback.get('has_feedback')),
                'feedback_source_roles': feedback.get('feedback_source_roles', []),
                'feedback_summary': feedback.get('feedback_summary', ''),
                'feedback_in_prompt': bool(item.get('feedback_in_prompt')),
                'prompt_length': item.get('prompt_length', 0),
                'output_length': item.get('output_length', 0),
            }
        )
    return feedback_events


def _summarize_text_diff(before_text: str, after_text: str, max_lines: int = 20) -> list[str]:
    diff_lines = list(
        difflib.unified_diff(
            before_text.splitlines(),
            after_text.splitlines(),
            fromfile='without_feedback',
            tofile='with_feedback',
            lineterm='',
        )
    )
    if len(diff_lines) > max_lines:
        return diff_lines[:max_lines] + ['...diff truncated...']
    return diff_lines


def build_feedback_diff_records(step_results: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for item in step_results:
        base_prompt = item.get('base_prompt') or ''
        final_prompt = item.get('final_prompt') or ''
        feedback = item.get('feedback') or {}
        records.append(
            {
                'role': item.get('role', ''),
                'agent_name': ((item.get('agent') or {}).get('name', '')),
                'received_feedback': bool(feedback.get('has_feedback')),
                'feedback_source_roles': feedback.get('feedback_source_roles', []),
                'base_prompt_length': len(base_prompt),
                'final_prompt_length': len(final_prompt),
                'injected_prompt_chars': max(0, len(final_prompt) - len(base_prompt)),
                'base_prompt_preview': base_prompt[:300],
                'final_prompt_preview': final_prompt[:300],
                'prompt_diff_excerpt': _summarize_text_diff(base_prompt, final_prompt),
                'upstream_raw_length': item.get('upstream_raw_length', 0),
                'upstream_compressed_length': item.get('upstream_compressed_length', 0),
                'compression_ratio': item.get('upstream_compression_ratio', 1.0),
                'output_length': item.get('output_length', 0),
            }
        )
    return records


def build_compression_log(step_results: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            'role': item.get('role', ''),
            'agent_name': ((item.get('agent') or {}).get('name', '')),
            'upstream_raw_length': item.get('upstream_raw_length', 0),
            'upstream_compressed_length': item.get('upstream_compressed_length', 0),
            'compression_ratio': item.get('upstream_compression_ratio', 1.0),
            'compression_method': item.get('compression_method', ''),
            'compressed_context_preview': (item.get('compressed_upstream_text') or '')[:400],
        }
        for item in step_results
    ]


def build_workflow_checklist(task: str, plan: Mapping[str, Any], tree_plan: Mapping[str, Any], step_results: list[Mapping[str, Any]]) -> dict[str, Any]:
    children = list(tree_plan.get('children') or [])
    steps = [
        {'stage': 'user_input', 'status': 'done', 'description': 'Receive user task', 'artifact': '01_user_request.json'},
        {'stage': 'llm_decompose', 'status': 'done', 'description': 'Decompose requirement with LLM', 'artifact': '02_llm_decomposition.json'},
        {'stage': 'discovery', 'status': 'done', 'description': 'Query discovery and normalize candidate skills', 'artifact': '03_discovery_request.json + 04_discovery_response.json'},
        {'stage': 'mode_decision', 'status': 'done', 'description': 'Decide mode_1 / mode_2', 'artifact': '06_mode_decision.json'},
        {'stage': 'orchestrator_plan', 'status': 'done', 'description': 'Build execution plan and orchestration tree', 'artifact': '07_orchestrator_plan.json + 07b_orchestration_spec.json + 08b_tree_plan.json'},
    ]
    for child in children:
        role = child.get('role', '')
        result = next((item for item in step_results if item.get('role') == role), {})
        steps.append(
            {
                'stage': f'agent_{role}',
                'status': 'done' if result else 'missing',
                'description': f"Dispatch and collect output for {role}",
                'artifact': f"step*_{role}_*.json",
                'depends_on': child.get('depends_on', []),
                'feedback_in_prompt': bool(result.get('feedback_in_prompt')) if result else False,
            }
        )
    steps.extend(
        [
            {'stage': 'call_graph', 'status': 'done', 'description': 'Record call graph for debugging', 'artifact': '08c_call_graph.json'},
            {'stage': 'feedback_log', 'status': 'done', 'description': 'Record feedback injection chain', 'artifact': '08d_feedback_log.json'},
            {'stage': 'context_compression', 'status': 'done', 'description': 'Record upstream context compression before child agent prompting', 'artifact': '08h_context_compression.json'},
            {'stage': 'feedback_diff', 'status': 'done', 'description': 'Record prompt differences before and after feedback injection', 'artifact': '08g_feedback_diff.json'},
            {'stage': 'final_bundle', 'status': 'done', 'description': 'Write final artifacts', 'artifact': '09_full_data_flow.json + 10_final_review.md + 11_summary_zh.md'},
        ]
    )
    return {
        'task': task,
        'strategy': plan.get('strategy', ''),
        'total_steps': len(steps),
        'steps': steps,
    }


def build_workflow_checklist_zh(checklist: Mapping[str, Any]) -> str:
    lines = [
        '# 全流程检查清单',
        '',
        f"- 任务：{checklist.get('task', '')}",
        f"- 策略：{checklist.get('strategy', '')}",
        '',
        '## 清单',
        '',
    ]
    for index, item in enumerate(checklist.get('steps', []), start=1):
        depends_on = item.get('depends_on') or []
        feedback_note = ''
        if 'feedback_in_prompt' in item:
            feedback_note = f" | 反馈注入：{'是' if item.get('feedback_in_prompt') else '否'}"
        dep_text = f" | 依赖：{', '.join(depends_on)}" if depends_on else ''
        lines.append(
            f"{index}. [{item.get('status', '')}] {item.get('stage', '')} - {item.get('description', '')}{dep_text}{feedback_note} | 产物：{item.get('artifact', '')}"
        )
    lines.append('')
    return '\n'.join(lines)


def _load_status_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding='utf-8').splitlines():
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


def _workflow_progress(checklist: Mapping[str, Any]) -> dict[str, Any]:
    steps = list(checklist.get('steps') or [])
    total = len(steps)
    done = sum(1 for item in steps if item.get('status') == 'done')
    missing = sum(1 for item in steps if item.get('status') == 'missing')
    return {
        'total_steps': total,
        'done_steps': done,
        'missing_steps': missing,
        'percent': round((done / total) * 100, 1) if total else 0,
    }


def build_run_status_summary(
    *,
    task: str,
    plan: Mapping[str, Any],
    tree_plan: Mapping[str, Any],
    step_results: list[Mapping[str, Any]],
    checklist: Mapping[str, Any],
    events: list[Mapping[str, Any]],
) -> dict[str, Any]:
    state_counts: dict[str, int] = {}
    for event in events:
        state = str(event.get('state') or 'unknown')
        state_counts[state] = state_counts.get(state, 0) + 1

    result_by_role = {str(item.get('role') or ''): item for item in step_results}
    latest_by_role: dict[str, Mapping[str, Any]] = {}
    for event in events:
        role = str(event.get('role') or '')
        if role:
            latest_by_role[role] = event

    roles: list[dict[str, Any]] = []
    seen_roles: set[str] = set()
    for child in list(tree_plan.get('children') or []):
        role = str(child.get('role') or '')
        if not role:
            continue
        seen_roles.add(role)
        result = result_by_role.get(role, {})
        latest = latest_by_role.get(role, {})
        agent = result.get('agent') or {}
        roles.append(
            {
                'role': role,
                'agent_name': agent.get('name') or child.get('agent_name', ''),
                'state': latest.get('state') or result.get('final_state') or 'pending',
                'stage': latest.get('stage', ''),
                'message': latest.get('message', ''),
                'task_id': latest.get('task_id') or result.get('task_id', ''),
                'final_state': result.get('final_state', ''),
                'output_length': result.get('output_length', 0),
                'depends_on_roles': result.get('depends_on_roles') or child.get('depends_on_roles') or [],
                'feedback_in_prompt': bool(result.get('feedback_in_prompt')),
                'compression_ratio': result.get('upstream_compression_ratio', 1.0),
            }
        )

    for result in step_results:
        role = str(result.get('role') or '')
        if not role or role in seen_roles:
            continue
        agent = result.get('agent') or {}
        latest = latest_by_role.get(role, {})
        roles.append(
            {
                'role': role,
                'agent_name': agent.get('name', ''),
                'state': latest.get('state') or result.get('final_state') or 'pending',
                'stage': latest.get('stage', ''),
                'message': latest.get('message', ''),
                'task_id': latest.get('task_id') or result.get('task_id', ''),
                'final_state': result.get('final_state', ''),
                'output_length': result.get('output_length', 0),
                'depends_on_roles': result.get('depends_on_roles') or [],
                'feedback_in_prompt': bool(result.get('feedback_in_prompt')),
                'compression_ratio': result.get('upstream_compression_ratio', 1.0),
            }
        )

    latest_event = dict(events[-1]) if events else {}
    progress = _workflow_progress(checklist)
    return {
        'task': task,
        'status': 'done' if latest_event.get('state') == 'done' and progress['missing_steps'] == 0 else 'running',
        'strategy': plan.get('strategy', ''),
        'current': {
            'stage': latest_event.get('stage', ''),
            'state': latest_event.get('state', ''),
            'message': latest_event.get('message', ''),
            'timestamp': latest_event.get('timestamp', ''),
        },
        'progress': progress,
        'state_counts': state_counts,
        'roles': roles,
        'recent_events': [dict(event) for event in events[-20:]],
    }


def build_run_status_summary_zh(summary: Mapping[str, Any]) -> str:
    progress = summary.get('progress') or {}
    current = summary.get('current') or {}
    lines = [
        '# 运行状态摘要',
        '',
        f"- 任务：{summary.get('task', '')}",
        f"- 状态：{summary.get('status', '')}",
        f"- 策略：{summary.get('strategy', '')}",
        f"- 进度：{progress.get('done_steps', 0)}/{progress.get('total_steps', 0)} ({progress.get('percent', 0)}%)",
        f"- 当前阶段：{current.get('stage', '')} / {current.get('state', '')}",
        f"- 当前消息：{current.get('message', '')}",
        '',
        '## 角色进度',
        '',
    ]
    for role in summary.get('roles', []) or []:
        deps = ', '.join(role.get('depends_on_roles') or []) or '无'
        lines.append(
            f"- {role.get('role', '')} | {role.get('agent_name', '')} | 状态：{role.get('state', '')} | "
            f"输出：{role.get('output_length', 0)} 字符 | 依赖：{deps} | 反馈注入：{'是' if role.get('feedback_in_prompt') else '否'}"
        )
    lines.append('')
    return '\n'.join(lines)


def build_state_timeline_markdown(task: str, trace_id: str, summary: Mapping[str, Any], events: list[Mapping[str, Any]]) -> str:
    progress = summary.get('progress') or {}
    lines = [
        '# 状态流时间线',
        '',
        f'- trace_id: {trace_id}',
        f'- task: {task}',
        f"- progress: {progress.get('done_steps', 0)}/{progress.get('total_steps', 0)} ({progress.get('percent', 0)}%)",
        '',
        '| # | 时间 | 状态 | 阶段 | 角色 | 智能体 | 消息 |',
        '|---:|---|---|---|---|---|---|',
    ]
    for index, event in enumerate(events, start=1):
        message = str(event.get('message', '')).replace('|', '\\|').replace('\n', ' ')
        lines.append(
            f"| {index} | {event.get('timestamp', '')} | {event.get('state', '')} | "
            f"{event.get('stage', '')} | {event.get('role', '')} | {event.get('agent_name', '')} | {message} |"
        )
    lines.append('')
    return '\n'.join(lines)


async def execute_agent_step(
    agent: AgentRef,
    prompt: str,
    run_dir: Path,
    step_index: int,
    session_id: str,
    trace_id: str,
) -> dict[str, Any]:
    if str(SDK_PATH) not in sys.path:
        sys.path.insert(0, str(SDK_PATH))

    import httpx
    from acps_sdk.aip import AipRpcClient
    from acps_sdk.aip.aip_base_model import TaskState

    step_name = f"step{step_index}_{agent.role}_{_slug(agent.name, 24)}"
    _write_text(run_dir / f"{step_name}_input.txt", prompt)

    async def _build_client() -> AipRpcClient:
        rpc_client = AipRpcClient(agent.url, leader_id='th-literature-orchestrator')
        await rpc_client.http_client.aclose()
        rpc_client.http_client = httpx.AsyncClient(timeout=300.0)
        return rpc_client

    client = await _build_client()
    started_at = time.time()
    history: list[dict[str, Any]] = []

    try:
        _status_event(
            trace_id=trace_id,
            run_dir=run_dir,
            stage='agent_dispatch',
            state='running',
            role=agent.role,
            agent_name=agent.name,
            step_index=step_index,
            message='已发起任务，等待智能体开始执行。',
        )
        task = await client.start_task(session_id=session_id, user_input=prompt)
        history.append({'state': _state_value(task.status.state), 'at': _utc_now()})
        _status_event(
            trace_id=trace_id,
            run_dir=run_dir,
            stage='agent_dispatch',
            state='running',
            role=agent.role,
            agent_name=agent.name,
            step_index=step_index,
            task_id=task.taskId,
            message='智能体已接受任务，开始轮询执行状态。',
        )
        poll_errors = 0
        while task.status.state == TaskState.Working:
            await asyncio.sleep(1.0)
            try:
                task = await client.get_task(task.taskId, session_id)
                history.append({'state': _state_value(task.status.state), 'at': _utc_now()})
                poll_errors = 0
            except Exception as exc:
                poll_errors += 1
                history.append({'state': 'poll_error', 'at': _utc_now(), 'error': str(exc), 'retry': poll_errors})
                if poll_errors >= 5:
                    raise
                await client.close()
                client = await _build_client()
                await asyncio.sleep(min(5 * poll_errors, 15))

        output_text = _extract_text(task)
        if task.status.state == TaskState.AwaitingCompletion:
            await client.complete_task(task.taskId, session_id)

        _status_event(
            trace_id=trace_id,
            run_dir=run_dir,
            stage='agent_complete',
            state='done',
            role=agent.role,
            agent_name=agent.name,
            step_index=step_index,
            task_id=task.taskId,
            message='智能体输出已收集，进入下一步。',
        )

        result = {
            'role': agent.role,
            'parent_node': 'root-main-agent',
            'agent': agent.to_dict(),
            'task_id': task.taskId,
            'session_id': session_id,
            'final_state': _state_value(task.status.state),
            'duration_ms': int((time.time() - started_at) * 1000),
            'history': history,
            'prompt_length': len(prompt),
            'output_length': len(output_text),
            'output_text': output_text,
            'raw_task': _serialize_task(task),
        }
        _write_json(run_dir / f"{step_name}_result.json", result)
        _write_text(run_dir / f"{step_name}_output.txt", output_text)
        return result
    finally:
        await client.close()


async def execute_group_workflow(
    task: str,
    decomposition: Mapping[str, Any],
    role_agents: Mapping[str, AgentRef],
    tree_plan: Mapping[str, Any],
    run_dir: Path,
    session_id: str,
    trace_id: str,
) -> list[dict[str, Any]]:
    if str(SDK_PATH) not in sys.path:
        sys.path.insert(0, str(SDK_PATH))

    from acps_sdk.aip import GroupLeader, ACSObject, TaskState

    leader = GroupLeader(
        leader_aic='th-literature-orchestrator',
        rabbitmq_config={
            'host': os.getenv('RABBITMQ_HOST', 'localhost'),
            'port': 5672,
            'user': os.getenv('RABBITMQ_USER', 'guest'),
            'password': os.getenv('RABBITMQ_PASSWORD', 'guest'),
            'vhost': os.getenv('RABBITMQ_VHOST', '/'),
        },
    )

    group_session = await leader.create_group_session(
        session_id=session_id,
        initial_partners=[],
    )

    role_to_agent = {
        role: GroupAgentRef(
            role=role,
            aic=agent.aic,
            name=agent.name,
            url=agent.url,
            skill_ids=agent.skill_ids,
            skill_names=agent.skill_names,
        )
        for role, agent in role_agents.items()
    }

    for role, agent in role_to_agent.items():
        _status_event(
            trace_id=trace_id,
            run_dir=run_dir,
            stage='agent_assigned',
            state='assigned',
            role=role,
            agent_name=agent.name,
            message='已邀请群聊成员加入会话。',
        )
        await leader.invite_partner(
            session_id=session_id,
            partner_acs=ACSObject(aic=agent.aic),
            partner_rpc_url=_to_group_rpc_url(agent.url),
        )

    task_id = f"lit-{session_id}"
    tree_children = list(tree_plan.get('children') or [])
    child_meta = {child.get('role'): child for child in tree_children}
    role_by_node_id = {
        child.get('node_id'): child.get('role')
        for child in tree_children
        if child.get('node_id') and child.get('role')
    }
    role_results: dict[str, dict[str, Any]] = {}
    role_outputs: dict[str, str] = {}
    index_by_role = {child.get('role'): idx + 1 for idx, child in enumerate(tree_children)}

    def _role_dependencies(node: Mapping[str, Any]) -> list[str]:
        own_role = str(node.get('role') or '')
        role_deps: list[str] = []
        for dep_role in list(node.get('depends_on_roles') or []):
            dep_role = str(dep_role)
            if dep_role in role_to_agent and dep_role != own_role and dep_role not in role_deps:
                role_deps.append(dep_role)
        if role_deps:
            return role_deps

        for dep_node in list(node.get('depends_on') or []):
            dep_role = role_by_node_id.get(dep_node)
            if dep_role and dep_role in role_to_agent and dep_role != own_role and dep_role not in role_deps:
                role_deps.append(dep_role)
        return role_deps

    async def _dispatch_role(role: str) -> None:
        agent = role_to_agent[role]
        node = child_meta.get(role) or {}
        depends_on_roles = _role_dependencies(node)
        upstream_text = '\n\n'.join(
            role_outputs.get(dep_role, '')
            for dep_role in depends_on_roles
            if role_outputs.get(dep_role)
        )
        completed_results = [role_results[r] for r in role_results]
        feedback = build_feedback_note(role, completed_results)
        base_prompt = build_step_prompt(role, decomposition, None)
        compression = compress_upstream_context(role, upstream_text or None)
        prompt = build_group_prompt(role, decomposition, compression['compressed_text'])
        step_index = index_by_role.get(role, 0)
        step_name = f"step{step_index}_{role}_{_slug(agent.name, 24)}"

        _write_text(run_dir / f"{step_name}_input_without_feedback.txt", base_prompt)
        if compression['raw_text']:
            _write_text(run_dir / f"{step_name}_upstream_raw.txt", compression['raw_text'])
            _write_text(run_dir / f"{step_name}_upstream_compressed.txt", compression['compressed_text'])

        _status_event(
            trace_id=trace_id,
            run_dir=run_dir,
            stage='agent_dispatch',
            state='assigned',
            role=role,
            agent_name=agent.name,
            step_index=step_index,
            message='已向群聊成员分发角色任务。',
        )
        await group_session.leader_mq_client.start_task(
            session_id=session_id,
            text_content=prompt,
            task_id=f"{task_id}-{role}",
            mentions=[agent.aic],
        )

        observed = None
        poll_round = 0
        max_poll_rounds = int(os.getenv('GROUP_AGENT_MAX_POLLS', '480'))
        while True:
            snap = group_session.get_partner_task_snapshot(f"{task_id}-{role}", agent.aic)
            if snap:
                observed = snap
                state = snap.get('state')
                _status_event(
                    trace_id=trace_id,
                    run_dir=run_dir,
                    stage='agent_dispatch',
                    state='running' if state != TaskState.AwaitingCompletion else 'waiting_summary',
                    role=role,
                    agent_name=agent.name,
                    step_index=step_index,
                    task_id=f"{task_id}-{role}",
                    message=f'成员状态：{state}',
                )
                if state == TaskState.AwaitingCompletion or state in {TaskState.Completed, TaskState.Failed, TaskState.Rejected, TaskState.Canceled}:
                    break
            poll_round += 1
            if poll_round > max_poll_rounds:
                break
            await asyncio.sleep(0.5)

        final_state = str(observed.get('state') if observed else 'unknown')
        output_text = ''
        if observed:
            output_text = observed.get('product_text') or observed.get('awaiting_prompt') or ''
        if not output_text:
            output_text = f"[GROUP_OUTPUT]{role}"

        step_result = {
            'role': role,
            'parent_node': 'root-main-agent',
            'agent': agent.to_dict(),
            'task_id': f"{task_id}-{role}",
            'session_id': session_id,
            'final_state': final_state,
            'duration_ms': 0,
            'history': [],
            'prompt_length': len(prompt),
            'output_length': len(output_text),
            'output_text': output_text,
            'raw_task': {},
            'feedback': feedback,
            'feedback_in_prompt': bool(feedback.get('has_feedback') and upstream_text),
            'base_prompt': base_prompt,
            'final_prompt': prompt,
            'upstream_raw_length': compression['raw_length'],
            'upstream_compressed_length': compression['compressed_length'],
            'upstream_compression_ratio': compression['compression_ratio'],
            'compression_method': compression['method'],
            'compressed_upstream_text': compression['compressed_text'],
            'group_mode': True,
            'depends_on_roles': depends_on_roles,
            'depends_on_nodes': list(node.get('depends_on') or []),
        }
        _write_json(run_dir / f"{step_name}_result.json", step_result)
        _write_text(run_dir / f"{step_name}_output.txt", output_text)
        role_results[role] = step_result
        role_outputs[role] = output_text

        if observed and observed.get('state') == TaskState.AwaitingCompletion:
            await group_session.leader_mq_client.complete_task(
                task_id=f"{task_id}-{role}",
                session_id=session_id,
                mentions=[agent.aic],
            )

    dependencies = {child.get('role'): _role_dependencies(child) for child in tree_children}
    pending_roles = [role for role in role_to_agent if role in dependencies]
    completed_roles: set[str] = set()

    while pending_roles:
        ready_roles = [role for role in pending_roles if all(dep in completed_roles for dep in dependencies.get(role, []))]
        if not ready_roles:
            ready_roles = pending_roles[:1]

        await asyncio.gather(*(_dispatch_role(role) for role in ready_roles))
        for role in ready_roles:
            completed_roles.add(role)
            pending_roles.remove(role)

    return [role_results[role] for role in role_results]


def summarize_zh(run_result: Mapping[str, Any]) -> str:
    tree = run_result.get('orchestration_tree') or {}
    root = tree.get('root') or {}
    children = tree.get('children') or []
    status_summary = run_result.get('run_status_summary') or {}
    progress = status_summary.get('progress') or {}
    lines = [
        '# 群聊式多智能体编排运行总结',
        '',
        f"- 任务：{run_result.get('task', '')}",
        f"- 模式：{run_result.get('decision', {}).get('mode', '')}",
        f"- 策略：{run_result.get('plan', {}).get('strategy', '')}",
        f"- 运行目录：{run_result.get('run_directory', '')}",
        f"- 进度：{progress.get('done_steps', 0)}/{progress.get('total_steps', 0)} ({progress.get('percent', 0)}%)",
        '',
        '## 编排结构',
        '',
        f"- 主智能体：{root.get('name', '未命名')} ({root.get('node_id', 'root')})",
        f"- 分发方式：{root.get('dispatch_mode', 'orchestrated')}",
        f"- 子智能体数量：{len(children)}",
    ]
    for child in children:
        dependency_text = ', '.join(child.get('depends_on', []) or []) or '无'
        lines.append(
            f"  - 角色：{child.get('role', '')} | 智能体：{child.get('agent_name', '')} | 输入来源：{child.get('input_from', 'root')} | 依赖：{dependency_text}"
        )
    lines.extend([
        '',
        '## 执行链路',
        '',
        '1. 接收用户任务',
        '2. 通过 LLM 拆解需求',
        '3. 调用 discovery 匹配 agent / skill',
        '4. 决策 mode 并生成编排计划',
        '5. 通过群聊会话分发角色任务并收集结果',
        '6. 汇总最终结果、状态时间线和运行摘要',
        '',
        '## 子任务结果',
        '',
    ])
    for item in run_result.get('steps', []):
        lines.append(
            f"- {item['role']} | {item['agent']['name']} | 父节点：{item.get('parent_node', 'root')} | 状态：{item['final_state']} | 输出长度：{item['output_length']}"
        )
    if status_summary.get('roles'):
        lines.extend(['', '## 角色状态摘要', ''])
        for role in status_summary.get('roles', []):
            deps = ', '.join(role.get('depends_on_roles') or []) or '无'
            lines.append(
                f"- {role.get('role', '')} | {role.get('agent_name', '')} | 当前状态：{role.get('state', '')} | 依赖：{deps} | 反馈注入：{'是' if role.get('feedback_in_prompt') else '否'}"
            )
    lines.extend(['', '## 最终结果预览', ''])
    preview = (run_result.get('final_result') or '')[:1200]
    lines.append(preview if preview else '(空)')
    lines.append('')
    return '\n'.join(lines)

async def run_literature_workflow(task: str, discovery_url: str = DISCOVERY_URL, limit: int = 10) -> dict[str, Any]:
    run_dir = _ensure_run_dir(task)
    session_id = f"lit-{int(time.time())}"
    trace_id = session_id

    state_events_path = run_dir / '12_state_events.jsonl'
    state_events_path.write_text('', encoding='utf-8')

    _status_event(
        trace_id=trace_id,
        run_dir=run_dir,
        stage='workflow_start',
        state='running',
        message='工作流已启动，开始进行需求拆解。',
    )

    request_payload = {
        'task': task,
        'discovery_url': discovery_url,
        'limit': limit,
        'requested_at': _utc_now(),
    }
    _write_json(run_dir / '01_user_request.json', request_payload)

    decomposition = await decompose_requirement(task)
    _write_json(run_dir / '02_llm_decomposition.json', decomposition)

    hints = build_workflow_hints(decomposition)
    discovery_request = build_discovery_request(task, {'type': 'explicit', 'limit': limit})
    discovery_response = call_discovery(discovery_url, discovery_request, timeout=120.0, retries=1, retry_backoff=2.0)
    _write_json(run_dir / '03_discovery_request.json', discovery_request)
    _write_json(run_dir / '04_discovery_response.json', discovery_response)

    normalized = normalize_request_payload(
        {
            'task': task,
            'hints': hints,
            'discovery_response': discovery_response,
        }
    )
    filtered_skills = filter_literature_skills(list(normalized['skills']))
    _write_json(run_dir / '05_filtered_skills.json', filtered_skills)

    decision = decide_mode(task, filtered_skills, hints=hints)
    plan = build_execution_plan(task, filtered_skills, hints=hints, decision=decision)
    orchestration_spec = build_orchestration_spec(task, filtered_skills, hints=hints, decision=decision)
    _write_json(run_dir / '06_mode_decision.json', decision.to_dict())
    _write_json(run_dir / '07_orchestrator_plan.json', plan)
    _write_json(run_dir / '07b_orchestration_spec.json', orchestration_spec)

    if decision.mode != MODE_2:
        raise RuntimeError(f'文献综述工作流要求 mode_2，实际得到 {decision.mode}')

    role_agents = resolve_role_agents(filtered_skills)
    _write_json(run_dir / '08_role_agents.json', {role: agent.to_dict() for role, agent in role_agents.items()})
    tree_plan = build_tree_plan(task, role_agents, decision.to_dict(), plan)
    _write_json(run_dir / '08b_tree_plan.json', tree_plan)

    step_results = await execute_group_workflow(
        task=task,
        decomposition=decomposition,
        role_agents=role_agents,
        tree_plan=tree_plan,
        run_dir=run_dir,
        session_id=session_id,
        trace_id=trace_id,
    )

    _status_event(
        trace_id=trace_id,
        run_dir=run_dir,
        stage='workflow_summary',
        state='waiting_summary',
        message='子智能体执行完成，主智能体开始汇总与收口。',
    )

    writing_result = next((item for item in step_results if item.get('role') == 'writing'), None)
    final_result = (writing_result or step_results[-1])['output_text'] if step_results else ''
    call_graph = build_call_graph(task, tree_plan, step_results)
    feedback_log = build_feedback_log(step_results)
    feedback_diff = build_feedback_diff_records(step_results)
    compression_log = build_compression_log(step_results)
    checklist = build_workflow_checklist(task, plan, tree_plan, step_results)
    final_payload = {
        'task': task,
        'run_directory': str(run_dir),
        'decomposition': decomposition,
        'decision': decision.to_dict(),
        'plan': plan,
        'orchestration_spec': orchestration_spec,
        'orchestration_tree': tree_plan,
        'call_graph': call_graph,
        'feedback_log': feedback_log,
        'feedback_diff': feedback_diff,
        'compression_log': compression_log,
        'workflow_checklist': checklist,
        'steps': step_results,
        'final_result': final_result,
        'completed_at': _utc_now(),
    }
    _write_json(run_dir / '08c_call_graph.json', call_graph)
    _write_json(run_dir / '08d_feedback_log.json', feedback_log)
    _write_json(run_dir / '08e_workflow_checklist.json', checklist)
    _write_text(run_dir / '08f_workflow_checklist_zh.md', build_workflow_checklist_zh(checklist))
    _write_json(run_dir / '08g_feedback_diff.json', feedback_diff)
    _write_json(run_dir / '08h_context_compression.json', compression_log)
    _write_text(run_dir / '10_final_review.md', final_result)
    _status_event(
        trace_id=trace_id,
        run_dir=run_dir,
        stage='workflow_complete',
        state='done',
        message='工作流已完成，结果已写入运行目录。',
    )
    status_events = _load_status_events(state_events_path)
    run_status_summary = build_run_status_summary(
        task=task,
        plan=plan,
        tree_plan=tree_plan,
        step_results=step_results,
        checklist=checklist,
        events=status_events,
    )
    final_payload['run_status_summary'] = run_status_summary
    _write_json(run_dir / '09_full_data_flow.json', final_payload)
    _write_text(run_dir / '11_summary_zh.md', summarize_zh(final_payload))
    _write_text(run_dir / '12_state_timeline.md', build_state_timeline_markdown(task, trace_id, run_status_summary, status_events))
    _write_json(run_dir / '13_run_status_summary.json', run_status_summary)
    _write_text(run_dir / '13_run_status_summary.md', build_run_status_summary_zh(run_status_summary))
    return final_payload


async def _async_main(args: argparse.Namespace) -> int:
    result = await run_literature_workflow(task=args.task, discovery_url=args.discovery_url, limit=args.limit)
    print(
        json.dumps(
            {
                'run_directory': result['run_directory'],
                'mode': result['decision']['mode'],
                'strategy': result['plan']['strategy'],
                'final_length': len(result['final_result']),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='运行群聊式文献综述多智能体编排')
    parser.add_argument('--task', required=True)
    parser.add_argument('--discovery-url', default=DISCOVERY_URL)
    parser.add_argument('--limit', type=int, default=10)
    args = parser.parse_args()
    return asyncio.run(_async_main(args))


if __name__ == '__main__':
    raise SystemExit(main())
