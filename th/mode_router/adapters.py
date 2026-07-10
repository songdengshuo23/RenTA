from __future__ import annotations

from typing import Any, Mapping


def _pick(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def extract_skills_from_discovery_response(discovery_response: Mapping[str, Any]) -> list[dict[str, Any]]:
    if "error" in discovery_response and discovery_response.get("error"):
        raise ValueError("discovery response contains error and cannot be routed")

    result = discovery_response.get("result") or discovery_response
    acs_map = _pick(result, "acsMap", "acs_map", default={}) or {}
    agent_groups = result.get("agents") or []

    normalized: list[dict[str, Any]] = []
    for group in agent_groups:
        group_name = group.get("group", "")
        agent_skills = _pick(group, "agentSkills", "agent_skills", default=[]) or []
        for skill in agent_skills:
            aic = skill.get("aic")
            if not aic:
                continue
            acs = acs_map.get(aic, {}) or {}
            normalized.append(
                {
                    "aic": aic,
                    "skillid": _pick(skill, "skillId", "skill_id", default="") or "",
                    "ranking": skill.get("ranking"),
                    "memo": skill.get("memo") or "",
                    "agent_name": acs.get("name") or "",
                    "acs": acs,
                    "group": group_name,
                }
            )
    return normalized


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _first_endpoint(acp: Mapping[str, Any]) -> dict[str, Any]:
    endpoints = _pick(acp, "endpoints", "endPoints", default=[]) or []
    if not endpoints:
        return {}
    first = endpoints[0] or {}
    return first if isinstance(first, Mapping) else {}


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp_score(value: float) -> float:
    return max(0.0, min(1.0, value))


def _registry_score(item: Mapping[str, Any]) -> float:
    capabilities = item.get("capabilities") or {}
    hints = item.get("orchestratorHints") or item.get("orchestrator_hints") or {}
    adjustments = hints.get("rankingAdjustments") or hints.get("ranking_adjustments") or {}

    base = _safe_float(capabilities.get("capabilityConfidence") or item.get("capabilityConfidence"))
    if base is None:
        base = 0.75 if hints.get("eligibleForAutoDispatch", True) else 0.35

    boost = (_safe_float(adjustments.get("capabilityBoost")) or 0.0) + (_safe_float(adjustments.get("reliabilityBoost")) or 0.0)
    penalty = _safe_float(adjustments.get("riskPenalty")) or 0.0
    return round(_clamp_score(base + boost - penalty), 4)


def _registry_memo(item: Mapping[str, Any], skill: Mapping[str, Any]) -> str:
    hints = item.get("orchestratorHints") or item.get("orchestrator_hints") or {}
    parts = [
        str(skill.get("description") or ""),
        f"passport_status={item.get('status', '')}",
        f"decision={item.get('decision', '')}",
        f"risk={item.get('riskLevel') or item.get('risk_level') or ''}",
        f"permission_tier={item.get('permissionTier') or item.get('permission_tier') or ''}",
    ]
    domains = ", ".join(str(value) for value in _as_list(item.get("domains")))
    task_types = ", ".join(str(value) for value in _as_list(item.get("taskTypes") or item.get("task_types")))
    if domains:
        parts.append(f"domains={domains}")
    if task_types:
        parts.append(f"task_types={task_types}")
    if hints:
        parts.append(f"parallel_safe={bool(hints.get('parallelSafe') or hints.get('parallel_safe'))}")
        parts.append(f"auto_dispatch={bool(hints.get('eligibleForAutoDispatch') or hints.get('eligible_for_auto_dispatch'))}")
    return "; ".join(part for part in parts if part)


def _registry_acs(item: Mapping[str, Any]) -> dict[str, Any]:
    acp = item.get("acs") or item.get("acp") or {}
    endpoint = _first_endpoint(acp)
    declared_skills = _as_list(
        item.get("declaredSkills")
        or (item.get("capabilities") or {}).get("declaredSkills")
        or acp.get("skills")
        or (acp.get("capabilities") or {}).get("declaredSkills")
    )
    return {
        "name": item.get("name") or acp.get("name") or item.get("agentName") or item.get("agentAic") or acp.get("aic") or "",
        "description": item.get("description") or acp.get("description") or (item.get("passport") or {}).get("identity", {}).get("descriptionSummary", ""),
        "endPoints": [endpoint] if endpoint else [],
        "skills": declared_skills,
        "passport": {
            "passportId": item.get("passportId"),
            "reviewId": item.get("reviewId"),
            "status": item.get("status"),
            "decision": item.get("decision"),
            "riskLevel": item.get("riskLevel"),
            "permissionTier": item.get("permissionTier"),
            "orchestratorHints": item.get("orchestratorHints") or {},
        },
    }


def _registry_items(registry_response: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    result = registry_response.get("result") or registry_response
    if isinstance(result, list):
        return [item for item in result if isinstance(item, Mapping)]
    if not isinstance(result, Mapping):
        return []
    items = result.get("items")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, Mapping)]
    if result.get("agentAic") or result.get("passportId") or result.get("acs"):
        return [result]
    return []


def is_registry_discovery_response(payload: Mapping[str, Any]) -> bool:
    items = _registry_items(payload)
    if not items:
        return False
    first = items[0]
    return bool(first.get("agentAic") or first.get("passportId") or first.get("declaredSkills") or first.get("acs"))


def extract_skills_from_registry_discovery_response(registry_response: Mapping[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for ranking, item in enumerate(_registry_items(registry_response), start=1):
        acp = item.get("acs") or item.get("acp") or {}
        aic = str(item.get("agentAic") or item.get("aic") or acp.get("aic") or "").strip()
        if not aic:
            continue

        acs = _registry_acs(item)
        declared_skills = _as_list(
            item.get("declaredSkills")
            or (item.get("capabilities") or {}).get("declaredSkills")
            or acp.get("skills")
            or (acp.get("capabilities") or {}).get("declaredSkills")
        )
        if not declared_skills:
            declared_skills = [{"skillId": f"passport/{item.get('passportId') or aic}", "name": "Registry approved agent"}]

        score = _registry_score(item)
        for skill in declared_skills:
            if not isinstance(skill, Mapping):
                continue
            normalized.append(
                {
                    "aic": aic,
                    "agent_id": item.get("agentId") or item.get("id"),
                    "skillid": _pick(skill, "skillId", "skill_id", "id", default="") or "",
                    "skill_name": _pick(skill, "name", "skillName", "skill_name", default="") or "",
                    "score": score,
                    "enhanced_weighted_score": score,
                    "ranking": ranking,
                    "memo": _registry_memo(item, skill),
                    "agent_name": item.get("name") or acp.get("name") or "",
                    "acs": acs,
                    "group": "registry_passport",
                    "registry_passport": {
                        "passportId": item.get("passportId"),
                        "reviewId": item.get("reviewId"),
                        "status": item.get("status"),
                        "decision": item.get("decision"),
                        "riskLevel": item.get("riskLevel"),
                        "permissionTier": item.get("permissionTier"),
                    },
                    "orchestrator_hints": item.get("orchestratorHints") or {},
                }
            )
    return normalized


def normalize_request_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    task = (
        payload.get("task")
        or payload.get("task_description")
        or payload.get("query")
        or payload.get("objective")
        or ""
    )

    source = "skills"
    if payload.get("skills") is not None:
        skills = list(payload.get("skills") or [])
    elif payload.get("candidate_skills") is not None:
        skills = list(payload.get("candidate_skills") or [])
    elif payload.get("registry_discovery_response") is not None or payload.get("registryDiscoveryResponse") is not None:
        registry_response = payload.get("registry_discovery_response") or payload.get("registryDiscoveryResponse")
        skills = extract_skills_from_registry_discovery_response(registry_response or {})
        source = "registry_passport_discovery"
    else:
        discovery_response = (
            payload.get("discovery_response")
            or payload.get("discoveryResponse")
            or payload.get("adp_response")
            or payload.get("adpResponse")
        )
        if discovery_response is None and is_registry_discovery_response(payload):
            skills = extract_skills_from_registry_discovery_response(payload)
            source = "registry_passport_discovery"
            discovery_response = None
        if discovery_response is None and (payload.get("result") or payload.get("agents")):
            discovery_response = payload
        if discovery_response is not None:
            if is_registry_discovery_response(discovery_response):
                skills = extract_skills_from_registry_discovery_response(discovery_response)
                source = "registry_passport_discovery"
            else:
                skills = extract_skills_from_discovery_response(discovery_response)
                source = "discovery_response"
        else:
            skills = []

    return {
        "task": task,
        "skills": skills,
        "hints": payload.get("hints") or {},
        "config": payload.get("config") or {},
        "source": source,
        "metadata": payload.get("metadata") or {},
    }
