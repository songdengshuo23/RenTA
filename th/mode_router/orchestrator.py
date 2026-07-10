from __future__ import annotations

import copy
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping
from uuid import uuid4

from mode_selector import CandidateSkill, MODE_1, MODE_2, ModeDecision, decide_mode
from route_classifier import build_llm_direct_plan
from topology_catalog import select_topology_template, topology_catalog_dict


PLACEHOLDER_CONNECTOR_CONTRACT = {
    "version": "0.2",
    "description": "Minimal downstream agent executor contract for mode_2 work dispatch.",
    "required_endpoints": [
        {
            "method": "GET",
            "path": "/health",
            "purpose": "Readiness and reachability check before dispatch.",
            "response_fields": ["status", "service", "version"],
        },
        {
            "method": "POST",
            "path": "/tasks",
            "purpose": "Submit one orchestrated work package to an execution-capable agent endpoint.",
            "request_fields": [
                "run_id",
                "task",
                "objective",
                "agent",
                "skills",
                "context",
                "deadline_ms",
                "callback_url"
            ],
            "response_fields": ["accepted", "run_id", "status", "message"],
        },
        {
            "method": "GET",
            "path": "/tasks/{run_id}",
            "purpose": "Poll task status when no callback channel is available.",
            "response_fields": ["run_id", "status", "updated_at", "result", "error"],
        }
    ],
    "optional_endpoints": [
        {
            "method": "POST",
            "path": "/callbacks/result",
            "purpose": "Push final results back to the orchestrator instead of polling.",
            "request_fields": ["run_id", "status", "result", "error", "finished_at"],
        }
    ],
    "group_chat_protocol": {
        "transport": "RabbitMQ via ACPs-SDK GroupLeader/GroupPartner",
        "agent_group_endpoint": "/group/rpc",
        "session_fields": ["session_id", "leader_aic", "partner_aic", "partner_rpc_url"],
        "message_flow": [
            "create_group_session(session_id)",
            "invite_partner(session_id, partner_acs, partner_rpc_url)",
            "start_task(session_id, task_id, text_content, mentions=[partner_aic])",
            "poll partner task snapshot until terminal state",
            "complete_task(session_id, task_id, mentions=[partner_aic]) when awaiting completion",
        ],
        "state_fields": ["task_id", "state", "product_text", "awaiting_prompt", "error"],
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_skills(skills: Iterable[Mapping[str, Any] | CandidateSkill]) -> list[CandidateSkill]:
    normalized: list[CandidateSkill] = []
    for item in skills:
        normalized.append(item if isinstance(item, CandidateSkill) else CandidateSkill.from_mapping(item))
    return normalized


def _skill_sort_key(skill: CandidateSkill) -> tuple[float, float]:
    score = skill.score if skill.score is not None else -1.0
    ranking_score = 1.0 / skill.ranking if skill.ranking else 0.0
    return (score, ranking_score)


def _ordered_selected_skills(decision: ModeDecision, normalized_skills: list[CandidateSkill]) -> list[CandidateSkill]:
    selected_keys = {
        (item.get("aic"), item.get("skillid"), item.get("skill_name", ""))
        for item in decision.evidence.get("selected_skills", [])
    }
    selected = []
    for skill in normalized_skills:
        key = (skill.aic, skill.skillid, skill.skill_name)
        if key in selected_keys:
            selected.append(skill)
    if not selected:
        best_agent = decision.evidence.get("best_agent") if isinstance(decision.evidence.get("best_agent"), Mapping) else {}
        best_aic = str(best_agent.get("aic") or "").strip()
        if best_aic:
            selected = [skill for skill in normalized_skills if skill.aic == best_aic]
    if not selected and decision.mode == MODE_1 and normalized_skills:
        selected = [sorted(normalized_skills, key=_skill_sort_key, reverse=True)[0]]
    return sorted(selected, key=_skill_sort_key, reverse=True)


def _compact_skill_label(skill: CandidateSkill) -> str:
    return skill.skill_name or skill.skillid or "unnamed-skill"


def _first_endpoint_url(skill: CandidateSkill) -> str:
    acs = skill.raw.get("acs") or skill.raw.get("acp") or {}
    endpoints = acs.get("endPoints") or acs.get("endpoints") or []
    if not endpoints:
        return ""
    endpoint = endpoints[0] or {}
    if not isinstance(endpoint, Mapping):
        return ""
    return str(endpoint.get("url") or endpoint.get("href") or "").strip()


def _make_agent_stub(skill: CandidateSkill) -> dict[str, str]:
    agent = {"aic": skill.aic, "name": skill.agent_name or skill.aic}
    endpoint_url = _first_endpoint_url(skill)
    if endpoint_url:
        agent["url"] = endpoint_url
    return agent


def _package_objective(agent_name: str, skills: list[CandidateSkill]) -> str:
    labels = ", ".join(_compact_skill_label(skill) for skill in skills[:3])
    if len(skills) > 3:
        labels += ", ..."
    return f"{agent_name} handles the subtask using skills: {labels}."


_ROLE_ALIASES: dict[str, tuple[str, ...]] = {
    "collect": (
        "collect", "collector", "crawl", "search", "retrieve", "fetch", "poi",
        "\u91c7\u96c6", "\u641c\u7d22", "\u68c0\u7d22", "\u83b7\u53d6", "\u666f\u70b9",
    ),
    "geo": (
        "map", "geo", "geocode", "coordinate", "amap", "route", "navigation",
        "\u5730\u56fe", "\u5750\u6807", "\u9ad8\u5fb7", "\u5bfc\u822a", "\u8def\u7ebf",
    ),
    "itinerary": (
        "itinerary", "schedule", "plan", "planner", "travel",
        "\u884c\u7a0b", "\u65e5\u7a0b", "\u89c4\u5212", "\u65c5\u884c", "\u65b9\u6848",
    ),
    "budget": (
        "budget", "cost", "price", "expense", "estimate",
        "\u9884\u7b97", "\u8d39\u7528", "\u6210\u672c", "\u4ef7\u683c", "\u4f30\u7b97",
    ),
    "data": (
        "data", "compress", "clean", "normalize", "structure", "json",
        "\u6570\u636e", "\u538b\u7f29", "\u6e05\u6d17", "\u7ed3\u6784\u5316",
    ),
    "content": (
        "content", "copy", "copywriting", "social", "media", "post", "xiaohongshu",
        "\u5185\u5bb9", "\u6587\u6848", "\u793e\u4ea4", "\u5c0f\u7ea2\u4e66", "\u79cd\u8349",
    ),
    "report": (
        "report", "guide", "document", "summary", "markdown",
        "\u62a5\u544a", "\u653b\u7565", "\u6587\u6863", "\u603b\u7ed3",
    ),
    "frontend": (
        "frontend", "front-end", "html", "web", "page", "visual", "visualization", "ui",
        "\u524d\u7aef", "\u53ef\u89c6\u5316", "\u9875\u9762", "\u7f51\u9875", "\u5c55\u793a",
    ),
    "qa": (
        "qa", "test", "review", "quality", "check", "audit", "validate",
        "\u8d28\u91cf", "\u6d4b\u8bd5", "\u5ba1\u67e5", "\u6821\u9a8c", "\u9a8c\u8bc1",
    ),
}


_ROLE_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "geo": ("collect",),
    "itinerary": ("collect", "geo", "data"),
    "budget": ("collect", "geo", "itinerary", "data"),
    "data": ("collect", "geo"),
    "content": ("collect", "geo", "itinerary", "data", "budget"),
    "report": ("collect", "geo", "itinerary", "budget", "data", "content"),
    "frontend": ("collect", "geo", "itinerary", "budget", "data", "content", "report"),
    "qa": ("frontend", "report", "content"),
}


def _agent_skill_text(agent: Mapping[str, Any], skills: list[CandidateSkill]) -> str:
    chunks: list[str] = [
        str(agent.get("name") or ""),
        str(agent.get("aic") or ""),
        str(agent.get("url") or ""),
    ]
    for skill in skills:
        acs = skill.raw.get("acs") or skill.raw.get("acp") or {}
        chunks.extend(
            [
                skill.agent_name,
                skill.skill_name,
                skill.skillid,
                skill.memo,
                str(acs.get("name") or ""),
                str(acs.get("description") or ""),
                str(skill.raw.get("description") or ""),
            ]
        )
    return " ".join(chunk for chunk in chunks if chunk).lower()


def _infer_package_roles(agent: Mapping[str, Any], skills: list[CandidateSkill]) -> list[str]:
    text = _agent_skill_text(agent, skills)
    scored: list[tuple[int, int, str]] = []
    for order, (role, aliases) in enumerate(_ROLE_ALIASES.items()):
        score = sum(1 for alias in aliases if alias.lower() in text)
        if score:
            scored.append((score, -order, role))
    return [role for _, _, role in sorted(scored, reverse=True)]


def _assign_inferred_dependencies(work_packages: list[dict[str, Any]], package_roles: dict[str, list[str]], *, sequential_fallback: bool) -> None:
    packages_by_role: dict[str, list[str]] = defaultdict(list)
    for package in work_packages:
        package_id = str(package.get("package_id") or "")
        primary_role = (package_roles.get(package_id, []) or [""])[0]
        for role in [primary_role] if primary_role else []:
            packages_by_role[role].append(package_id)

    seen_ids: list[str] = []
    for package in work_packages:
        package_id = str(package.get("package_id") or "")
        inferred: list[str] = []
        primary_role = (package_roles.get(package_id, []) or [""])[0]
        for upstream_role in _ROLE_DEPENDENCIES.get(primary_role, ()):
            for upstream_id in packages_by_role.get(upstream_role, []):
                if upstream_id != package_id and upstream_id not in inferred:
                    inferred.append(upstream_id)

        if not inferred and sequential_fallback and seen_ids:
            inferred.append(seen_ids[-1])

        package["depends_on"] = inferred
        seen_ids.append(package_id)


def _root_objective(task_description: str, child_count: int) -> str:
    return (
        f"Own the user task, decompose it, delegate to {child_count} child agents, "
        f"relay intermediate outputs through the root agent boundary, and merge the final answer for: {task_description}"
    )


def build_execution_plan(task_description: str, skills: Iterable[Mapping[str, Any] | CandidateSkill], hints: Mapping[str, Any] | None = None, config: Mapping[str, Any] | None = None, decision: ModeDecision | None = None) -> dict[str, Any]:
    normalized_skills = _normalize_skills(skills)
    routing_decision = decision or decide_mode(task_description, normalized_skills, hints=hints, config=config)
    selected_skills = _ordered_selected_skills(routing_decision, normalized_skills)

    if routing_decision.mode == "mode_0":
        return build_llm_direct_plan(task_description, routing_decision.to_dict())
    if routing_decision.mode == MODE_1:
        return _build_mode1_plan(routing_decision, selected_skills)
    if routing_decision.mode == MODE_2:
        return _build_mode2_plan(routing_decision, selected_skills)

    return {
        "plan_id": f"plan-{uuid4().hex[:12]}",
        "created_at": _utc_now(),
        "mode": routing_decision.mode,
        "strategy": "blocked",
        "status": "insufficient_info",
        "summary": "The router could not build a plan because there were not enough candidate skills.",
        "decision": routing_decision.to_dict(),
        "work_packages": [],
        "phases": []
    }


def _build_mode1_plan(decision: ModeDecision, selected_skills: list[CandidateSkill]) -> dict[str, Any]:
    if not selected_skills:
        return {
            "plan_id": f"plan-{uuid4().hex[:12]}",
            "created_at": _utc_now(),
            "mode": MODE_1,
            "strategy": "single_agent_multi_skill",
            "status": "insufficient_info",
            "summary": "mode_1 was selected, but no concrete skills were available for planning.",
            "decision": decision.to_dict(),
            "work_packages": [],
            "phases": []
        }

    best_agent = decision.evidence.get("best_agent") if isinstance(decision.evidence.get("best_agent"), Mapping) else {}
    primary_aic = str(best_agent.get("aic") or (selected_skills[0].aic if selected_skills else "")).strip()
    primary_skills = [skill for skill in selected_skills if skill.aic == primary_aic] or selected_skills
    primary_agent = _make_agent_stub(primary_skills[0])

    work_package = {
        "package_id": f"pkg-{uuid4().hex[:8]}",
        "agent": primary_agent,
        "objective": f"Complete the task end-to-end with one agent using {len(primary_skills)} selected skills.",
        "dispatch_mode": "sequential",
        "skills": [
            {"skillid": skill.skillid, "skill_name": skill.skill_name, "score": skill.score, "ranking": skill.ranking}
            for skill in primary_skills
        ],
        "depends_on": [],
        "status": "planned"
    }

    phases = [
        {"phase": "prepare", "owner": primary_agent, "description": "Load context and prepare any local data required by the selected skills."},
        {"phase": "execute_skills", "owner": primary_agent, "description": "Invoke the selected skills in sequence and keep intermediate state within one agent boundary.", "skills": work_package["skills"]},
        {"phase": "validate", "owner": primary_agent, "description": "Validate outputs against the original task and perform consistency checks."},
        {"phase": "deliver", "owner": primary_agent, "description": "Prepare the final deliverable for the caller."}
    ]

    return {
        "plan_id": f"plan-{uuid4().hex[:12]}",
        "created_at": _utc_now(),
        "mode": MODE_1,
        "strategy": "single_agent_multi_skill",
        "status": "planned",
        "summary": f"Single-agent plan centered on {primary_agent['name']}.",
        "decision": decision.to_dict(),
        "primary_agent": primary_agent,
        "work_packages": [work_package],
        "phases": phases
    }


def _build_mode2_plan(decision: ModeDecision, selected_skills: list[CandidateSkill]) -> dict[str, Any]:
    grouped: dict[str, list[CandidateSkill]] = defaultdict(list)
    for skill in selected_skills:
        grouped[skill.aic].append(skill)

    if not grouped:
        return {
            "plan_id": f"plan-{uuid4().hex[:12]}",
            "created_at": _utc_now(),
            "mode": MODE_2,
            "strategy": "tree_root_delegate",
            "status": "insufficient_info",
            "summary": "mode_2 was selected, but no concrete agent skill assignments were available.",
            "decision": decision.to_dict(),
            "work_packages": [],
            "phases": [],
            "connector_contract": PLACEHOLDER_CONNECTOR_CONTRACT
        }

    coordinator_aic = decision.evidence["best_agent"]["aic"]
    coordinator_skills = grouped.get(coordinator_aic)
    if coordinator_skills:
        coordinator = _make_agent_stub(coordinator_skills[0])
    else:
        first_group = next(iter(grouped.values()))
        coordinator = _make_agent_stub(first_group[0])

    work_packages = []
    parallelizable = bool(decision.evidence.get("hints", {}).get("parallelizable", True))
    dispatch_mode = "parallel" if parallelizable else "sequential"
    root_package_id = f"pkg-root-{uuid4().hex[:8]}"
    ordered_groups = sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)

    for index, (aic, agent_skills) in enumerate(ordered_groups, start=1):
        agent = _make_agent_stub(agent_skills[0])
        package_id = f"pkg-{uuid4().hex[:8]}"
        inferred_roles = _infer_package_roles(agent, agent_skills)
        child_package = {
            "package_id": package_id,
            "parent_package_id": root_package_id,
            "agent": agent,
            "objective": _package_objective(agent["name"], agent_skills),
            "dispatch_mode": dispatch_mode,
            "skills": [
                {"skillid": skill.skillid, "skill_name": skill.skill_name, "score": skill.score, "ranking": skill.ranking}
                for skill in sorted(agent_skills, key=_skill_sort_key, reverse=True)
            ],
            "depends_on": [],
            "input_from": "root_agent",
            "output_to": "root_agent",
            "execution_order": index,
            "inferred_roles": inferred_roles,
            "status": "planned",
        }
        if not parallelizable and work_packages:
            child_package["depends_on"] = [work_packages[-1]["package_id"]]
        work_packages.append(
            child_package
        )

    package_roles = {
        str(package.get("package_id") or ""): list(package.get("inferred_roles") or [])
        for package in work_packages
    }
    _assign_inferred_dependencies(work_packages, package_roles, sequential_fallback=not parallelizable)

    root_package = {
        "package_id": root_package_id,
        "agent": coordinator,
        "objective": _root_objective(decision.evidence.get("task", "") or "the user task", len(work_packages)),
        "dispatch_mode": "orchestrated",
        "skills": [],
        "depends_on": [],
        "children": [package["package_id"] for package in work_packages],
        "status": "planned",
    }
    group_chat = {
        "protocol": "rabbitmq_group_chat",
        "session_id": "",
        "leader_aic": "th-generic-orchestrator",
        "agent_group_endpoint": "/group/rpc",
        "dispatch_mode": dispatch_mode,
        "session_management": {
            "create": "GroupLeader.create_group_session(session_id)",
            "invite": "GroupLeader.invite_partner(session_id, partner_acs, partner_rpc_url)",
            "complete": "leader_mq_client.complete_task(task_id, session_id, mentions=[agent_aic])",
        },
        "message_contract": {
            "task_fields": ["session_id", "task_id", "text_content", "mentions"],
            "result_fields": ["state", "product_text", "awaiting_prompt", "error"],
        },
    }

    tree_children = []
    for package in work_packages:
        tree_children.append(
            {
                "node_id": package["package_id"],
                "parent_node": root_package_id,
                "agent": package["agent"],
                "objective": package["objective"],
                "dispatch_mode": package["dispatch_mode"],
                "depends_on": package["depends_on"],
                "input_from": package["input_from"],
                "output_to": package["output_to"],
                "inferred_roles": package.get("inferred_roles", []),
                "skills": package["skills"],
            }
        )

    phases = [
        {"phase": "decompose", "owner": coordinator, "description": "Break the task into child-agent work packages while keeping the coordinator as the single root agent."},
        {"phase": "delegate", "owner": coordinator, "description": "Delegate each child package from the root agent and relay intermediate context back through the root boundary.", "dispatch_mode": dispatch_mode, "package_ids": [package["package_id"] for package in work_packages]},
        {"phase": "collect", "owner": coordinator, "description": "Collect child outputs at the root agent and prepare the next child context or final synthesis input."},
        {"phase": "synthesize", "owner": coordinator, "description": "Merge partial outputs from the child agents into one coherent result owned by the root agent."},
        {"phase": "validate", "owner": coordinator, "description": "Check for cross-agent conflicts, missing evidence, and final answer consistency before delivery."},
        {"phase": "deliver", "owner": coordinator, "description": "Return the merged deliverable from the root agent to the caller."}
    ]

    return {
        "plan_id": f"plan-{uuid4().hex[:12]}",
        "created_at": _utc_now(),
        "mode": MODE_2,
        "strategy": "tree_root_dependency_children" if parallelizable else "tree_root_sequential_children",
        "status": "planned",
        "summary": f"Tree-shaped multi-agent plan rooted at {coordinator['name']} with {len(work_packages)} child agents.",
        "decision": decision.to_dict(),
        "coordinator": coordinator,
        "root_package": root_package,
        "work_packages": work_packages,
        "group_chat": group_chat,
        "orchestration_tree": {
            "root": root_package,
            "children": tree_children,
        },
        "phases": phases,
        "connector_contract": PLACEHOLDER_CONNECTOR_CONTRACT
    }


def execute_plan_dry_run(plan: Mapping[str, Any]) -> dict[str, Any]:
    execution_id = f"exec-{uuid4().hex[:12]}"
    runs = []
    for package in plan.get("work_packages", []):
        runs.append(
            {
                "run_id": f"run-{uuid4().hex[:10]}",
                "package_id": package["package_id"],
                "agent": package["agent"],
                "status": "accepted",
                "message": "Dry-run only. No downstream executor has been connected yet."
            }
        )

    return {
        "execution_id": execution_id,
        "plan_id": plan.get("plan_id"),
        "status": "accepted",
        "mode": plan.get("mode"),
        "strategy": plan.get("strategy"),
        "dry_run": True,
        "runs": runs,
        "next_requirement": "Connect real downstream agent executors that implement the placeholder contract before enabling live execution."
    }


def _dispatch_result(dispatch_view: Mapping[str, Any]) -> dict[str, Any]:
    result = dispatch_view.get("result") if isinstance(dispatch_view.get("result"), Mapping) else dispatch_view
    return dict(result or {})


def _dispatch_guard(dispatch_view: Mapping[str, Any] | None) -> dict[str, Any]:
    result = _dispatch_result(dispatch_view or {})
    eligible = bool(result.get("eligibleForDispatch") or result.get("eligible_for_dispatch"))
    return {
        "checked": bool(result),
        "eligible_for_dispatch": eligible,
        "reasons": list(result.get("reasons") or []),
        "status": result.get("status", ""),
        "decision": result.get("decision", ""),
        "risk_level": result.get("riskLevel") or result.get("risk_level") or "",
        "permission_tier": result.get("permissionTier") or result.get("permission_tier") or "",
        "orchestrator_hints": result.get("orchestratorHints") or result.get("orchestrator_hints") or {},
        "permissions": result.get("permissions") or {},
    }


def _agent_aic(record: Mapping[str, Any] | None) -> str:
    if not record:
        return ""
    return str(record.get("aic") or record.get("agent_aic") or "").strip()


def collect_plan_agent_aics(plan: Mapping[str, Any]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    def add(agent: Mapping[str, Any] | None) -> None:
        aic = _agent_aic(agent)
        if aic and aic not in seen:
            seen.add(aic)
            ordered.append(aic)

    add(plan.get("primary_agent") if isinstance(plan.get("primary_agent"), Mapping) else None)
    add(plan.get("coordinator") if isinstance(plan.get("coordinator"), Mapping) else None)
    root_package = plan.get("root_package") if isinstance(plan.get("root_package"), Mapping) else {}
    add(root_package.get("agent") if isinstance(root_package.get("agent"), Mapping) else None)
    for package in plan.get("work_packages", []) or []:
        if isinstance(package, Mapping):
            add(package.get("agent") if isinstance(package.get("agent"), Mapping) else None)
    return ordered


def annotate_plan_with_dispatch_guards(plan: Mapping[str, Any], dispatch_views: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    guarded_plan = copy.deepcopy(dict(plan))
    blocked_agents: list[dict[str, Any]] = []
    checked_agent_aics: set[str] = set()

    def attach(agent: dict[str, Any] | None) -> None:
        if not agent:
            return
        aic = _agent_aic(agent)
        if not aic:
            return
        guard = _dispatch_guard(dispatch_views.get(aic))
        agent["dispatch_guard"] = guard
        if guard["checked"]:
            checked_agent_aics.add(aic)
        if guard["checked"] and not guard["eligible_for_dispatch"]:
            blocked_agents.append({"aic": aic, "name": agent.get("name", ""), "reasons": guard["reasons"]})

    if isinstance(guarded_plan.get("primary_agent"), dict):
        attach(guarded_plan["primary_agent"])
    if isinstance(guarded_plan.get("coordinator"), dict):
        attach(guarded_plan["coordinator"])
    if isinstance(guarded_plan.get("root_package"), dict) and isinstance(guarded_plan["root_package"].get("agent"), dict):
        attach(guarded_plan["root_package"]["agent"])
    for package in guarded_plan.get("work_packages", []) or []:
        if isinstance(package, dict) and isinstance(package.get("agent"), dict):
            attach(package["agent"])
            package["dispatch_guard"] = package["agent"].get("dispatch_guard", {})

    unique_blocked = []
    seen_blocked: set[str] = set()
    for item in blocked_agents:
        if item["aic"] not in seen_blocked:
            seen_blocked.add(item["aic"])
            unique_blocked.append(item)

    guarded_plan["registry_validation"] = {
        "checked_agents": len(checked_agent_aics),
        "blocked_agents": unique_blocked,
        "status": "blocked" if unique_blocked else "passed",
    }
    if unique_blocked:
        guarded_plan["status"] = "dispatch_blocked"
    return guarded_plan




def build_orchestration_spec(task_description: str, skills: Iterable[Mapping[str, Any] | CandidateSkill], hints: Mapping[str, Any] | None = None, config: Mapping[str, Any] | None = None, decision: ModeDecision | None = None) -> dict[str, Any]:
    normalized_skills = _normalize_skills(skills)
    routing_decision = decision or decide_mode(task_description, normalized_skills, hints=hints, config=config)
    topology = select_topology_template(
        {
            "task": task_description,
            "task_type": "complex_multi_agent" if routing_decision.mode == MODE_2 else routing_decision.mode,
            "skills_needed": routing_decision.evidence.get("relevant_skill_count", 0),
            "requires_independent_roles": bool((routing_decision.evidence.get("hints") or {}).get("requires_independent_roles")),
            "parallelizable": bool((routing_decision.evidence.get("hints") or {}).get("parallelizable")),
            "needs_review": "review" in task_description.lower() or "??" in task_description or "review" in task_description.lower(),
        },
        hints=hints or routing_decision.evidence.get("hints", {}),
    )
    plan = build_execution_plan(task_description, normalized_skills, hints=hints, config=config, decision=routing_decision)
    if routing_decision.mode != MODE_2:
        return {
            "spec_id": f"spec-{uuid4().hex[:12]}",
            "created_at": _utc_now(),
            "task": task_description,
            "mode": routing_decision.mode,
            "status": "non_complex_skipped",
            "decision": routing_decision.to_dict(),
            "topology_catalog": topology_catalog_dict(),
            "selected_topology": None,
            "intent": {
                "task": task_description,
                "domain": "unknown",
                "difficulty": "not_multi_agent",
            },
            "framework_selection": {
                "selected": False,
                "reason": "Task is not classified as multi-agent complexity yet.",
            },
            "topology_spec": {},
            "agent_assignment": [],
            "prompt_bundle": {},
            "plan": plan,
        }

    selected_topology = topology
    selected_template = selected_topology.to_dict()
    root_agent = plan.get("coordinator") or plan.get("primary_agent") or {}
    tree = plan.get("orchestration_tree") or {}
    children = list(tree.get("children") or [])
    agent_assignment = []
    prompt_bundle = {"root_prompt": _root_objective(task_description, len(children)), "node_prompts": {}}
    for child in children:
        node_id = child.get("node_id") or ""
        role = child.get("role") or ""
        agent_assignment.append(
            {
                "node_id": node_id,
                "role": role,
                "agent": child.get("agent_name") or (child.get("agent") or {}).get("name", ""),
                "aic": child.get("agent_aic") or (child.get("agent") or {}).get("aic", ""),
                "selection_reason": f"Use {role} agent to handle the {role} subtask.",
            }
        )
        prompt_bundle["node_prompts"][node_id] = child.get("objective") or _package_objective(child.get("agent_name") or role, [])

    return {
        "spec_id": f"spec-{uuid4().hex[:12]}",
        "created_at": _utc_now(),
        "task": task_description,
        "mode": routing_decision.mode,
        "status": "planned",
        "decision": routing_decision.to_dict(),
        "intent": {
            "task": task_description,
            "domain": "literature_review",
            "difficulty": "complex_multi_agent",
            "skills_needed": routing_decision.evidence.get("relevant_skill_count", 0),
            "agents_needed": routing_decision.evidence.get("distinct_agent_count", 0),
            "reason": "Task is routed to multi-agent orchestration based on skill spread and role independence.",
        },
        "framework_selection": {
            "selected": True,
            "topology_type": selected_topology.topology_type,
            "topology_name": selected_topology.name,
            "reason": selected_topology.description,
            "candidate_topologies": [item.to_dict() for item in __import__("topology_catalog").catalog_topologies()],
        },
        "topology_spec": {
            "root": {
                "aic": root_agent.get("aic", ""),
                "name": root_agent.get("name", ""),
                "role": "coordinator",
                "framework": selected_topology.topology_type,
            },
            "nodes": selected_template.get("structure", {}).get("nodes", []),
            "edges": [
                {
                    "from": selected_template.get("structure", {}).get("root", {}).get("role", "root"),
                    "to": node.get("id", ""),
                    "type": "dispatch",
                }
                for node in selected_template.get("structure", {}).get("nodes", [])
            ],
            "merge_policy": selected_template.get("structure", {}).get("merge_policy", "root_summarize"),
        },
        "agent_assignment": agent_assignment,
        "prompt_bundle": prompt_bundle,
        "plan": plan,
    }


def get_placeholder_connector_contract() -> dict[str, Any]:
    return PLACEHOLDER_CONNECTOR_CONTRACT
