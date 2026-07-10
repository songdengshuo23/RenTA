import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Mapping
import logging
import urllib.parse
import urllib.request
from fastapi import status
from sqlmodel import select, Boolean
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.sync.model import Agent
from app.discovery.exception import (
    DiscoveryError,
    DiscoveryException,
)
from app.discovery.schema import (
    DiscoveryRequest,
    DiscoveryResponse,
    DiscoveryAgentSkill,
    DiscoveryFilters,
    convert_filter_to_legacy,
)
from app.discovery.singleton import AgentDiscovery
import time
import asyncio
from functools import wraps
from typing import Callable, Any, Awaitable, Tuple
from sqlalchemy import or_
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import JSONPATH 

# ??????
SyncFunc = Callable[..., Any]
AsyncFunc = Callable[..., Awaitable[Any]]
Func = Callable[..., Any]
WrappedReturn = Tuple[Any, float]


def time_it_return_ms(func: Func) -> Callable[..., Awaitable[WrappedReturn]]:
    @wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> WrappedReturn:
        start_time = time.perf_counter()
        result = await func(*args, **kwargs)
        end_time = time.perf_counter()
        return result, (end_time - start_time) * 1000

    @wraps(func)
    async def sync_wrapper_async_return(*args: Any, **kwargs: Any) -> WrappedReturn:
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        return result, (end_time - start_time) * 1000

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper_async_return


logger = logging.getLogger(__name__)


def _enhanced_search_timeout_seconds() -> Optional[float]:
    raw_value = os.getenv("DISCOVERY_ENHANCED_TIMEOUT_SECONDS") or os.getenv(
        "DISCOVERY_ENHANCED_TIMEOUT"
    )
    if raw_value is None or raw_value == "":
        raw_value = "3"
    try:
        timeout = float(raw_value)
    except (TypeError, ValueError):
        return 3.0
    return timeout if timeout > 0 else None


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _as_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "on"}:
            return True
        if lowered in {"false", "0", "no", "n", "off"}:
            return False
    return None


def _as_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metadata_value(metadata: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in metadata and metadata[key] is not None:
            return metadata[key]
    return None


def _request_metadata(request: DiscoveryRequest) -> Dict[str, Any]:
    context = request.context
    if not context:
        return {}
    metadata = getattr(context, "metadata", None)
    return metadata if isinstance(metadata, dict) else {}


def _requester_user_id_from_metadata(metadata: Mapping[str, Any]) -> str:
    return str(
        _metadata_value(
            metadata,
            "requesterUserId",
            "requester_user_id",
            "userId",
            "user_id",
            "entityUserId",
            "entity_user_id",
        )
        or ""
    )


def _workable_only_from_metadata(metadata: Mapping[str, Any]) -> bool:
    value = _metadata_value(metadata, "workableOnly", "workable_only", "availableOnly", "available_only")
    parsed = _as_bool(value)
    return True if parsed is None else parsed


def _owner_user_id(acs: Mapping[str, Any]) -> str:
    identity = _as_dict(acs.get("identity"))
    provider = _as_dict(acs.get("provider"))
    return str(
        _first_present(
            acs.get("ownerUserId"),
            acs.get("entityUserId"),
            identity.get("ownerUserId"),
            identity.get("entityUserId"),
            provider.get("userId"),
        )
        or ""
    )


def _visibility_reasons(acs: Mapping[str, Any], requester_user_id: str = "") -> List[str]:
    hints = _as_dict(acs.get("orchestratorHints"))
    access = _as_dict(acs.get("access"))
    visibility_raw = acs.get("visibility")
    visibility_obj = _as_dict(visibility_raw)
    visibility = str(
        _first_present(
            visibility_obj.get("scope"),
            visibility_obj.get("visibility"),
            visibility_raw if isinstance(visibility_raw, str) else None,
            hints.get("visibility"),
            access.get("visibility"),
            "public",
        )
        or "public"
    ).lower()
    owner_user_id = _owner_user_id(acs)
    requester_is_owner = bool(owner_user_id and requester_user_id and owner_user_id == requester_user_id)
    share_flags = [
        hints.get("callableByOthers"),
        hints.get("shareEnabled"),
        hints.get("publicCallable"),
        hints.get("allowExternalInvocation"),
        access.get("callableByOthers"),
        access.get("shareEnabled"),
        access.get("publicCallable"),
        access.get("allowExternalInvocation"),
        visibility_obj.get("callableByOthers"),
    ]
    reasons: List[str] = []
    if visibility in {"private", "owner", "owner_only", "local"} and not requester_is_owner:
        reasons.append("agent_private_to_owner")
    if any(_as_bool(value) is False for value in share_flags) and not requester_is_owner:
        reasons.append("agent_sharing_disabled")
    return reasons


def _runtime_reasons(acs: Mapping[str, Any]) -> List[str]:
    hints = _as_dict(acs.get("orchestratorHints"))
    runtime_raw = _first_present(
        acs.get("runtimeStatus"),
        acs.get("runtime"),
        acs.get("availability"),
        acs.get("health"),
        hints.get("runtimeStatus"),
    )
    runtime = _as_dict(runtime_raw)
    status_value = (
        runtime_raw if isinstance(runtime_raw, str) else _first_present(
            runtime.get("status"),
            runtime.get("state"),
            runtime.get("health"),
            runtime.get("availability"),
            hints.get("healthStatus"),
            "unknown",
        )
    )
    status_value = str(status_value or "unknown").strip().lower()
    current_load = _as_float(
        _first_present(
            runtime.get("currentLoad"),
            runtime.get("current_load"),
            runtime.get("activeTasks"),
            runtime.get("active_tasks"),
            hints.get("currentLoad"),
        )
    )
    max_concurrency = _as_float(
        _first_present(
            runtime.get("maxConcurrentTasks"),
            runtime.get("max_concurrent_tasks"),
            runtime.get("capacity"),
            hints.get("maxConcurrentTasks"),
        )
    )
    queue_depth = _as_float(_first_present(runtime.get("queueDepth"), runtime.get("queue_depth")))
    max_queue_depth = _as_float(_first_present(runtime.get("maxQueueDepth"), runtime.get("max_queue_depth")))
    accepting_tasks = _as_bool(
        _first_present(runtime.get("acceptingTasks"), runtime.get("accepting_tasks"), hints.get("acceptingTasks"))
    )

    reasons: List[str] = []
    if accepting_tasks is False:
        reasons.append("agent_not_accepting_tasks")
    if status_value in {"offline", "down", "unhealthy", "stopped", "disabled", "maintenance", "unavailable", "error"}:
        reasons.append(f"agent_runtime_{status_value}")
    if max_concurrency is not None and max_concurrency >= 0 and current_load is not None and current_load >= max_concurrency:
        reasons.append("agent_overloaded")
    if max_queue_depth is not None and max_queue_depth >= 0 and queue_depth is not None and queue_depth > max_queue_depth:
        reasons.append("agent_queue_full")
    return reasons


def _agent_workability_reasons(acs: Mapping[str, Any], requester_user_id: str = "") -> List[str]:
    if not isinstance(acs, Mapping):
        return ["invalid_acs"]

    reasons: List[str] = []
    active = _as_bool(acs.get("active"))
    if active is False:
        reasons.append("agent_inactive")
    eligible_for_dispatch = _as_bool(acs.get("eligibleForDispatch"))
    if eligible_for_dispatch is False:
        reasons.append("registry_dispatch_blocked")
    dispatch_reasons = acs.get("dispatchReasons")
    if isinstance(dispatch_reasons, list):
        reasons.extend(str(reason) for reason in dispatch_reasons if reason)
    hints = _as_dict(acs.get("orchestratorHints"))
    if _as_bool(hints.get("eligibleForAutoDispatch")) is False:
        reasons.append("orchestrator_auto_dispatch_not_allowed")
    reasons.extend(_visibility_reasons(acs, requester_user_id))
    reasons.extend(_runtime_reasons(acs))

    unique: List[str] = []
    seen = set()
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            unique.append(reason)
    return unique


def _filter_workable_agents(
    agents_data: List[Dict[str, Any]], requester_user_id: str = "", workable_only: bool = True
) -> List[Dict[str, Any]]:
    if not workable_only:
        return agents_data
    return [
        agent
        for agent in agents_data
        if not _agent_workability_reasons(agent or {}, requester_user_id=requester_user_id)
    ]
def _registry_atr_base_url() -> str:
    raw_url = (
        getattr(settings, "REGISTRY_ATR_BASE_URL", "")
        or os.getenv("REGISTRY_ATR_BASE_URL")
        or os.getenv("DISCOVERY_REGISTRY_ATR_BASE_URL")
        or getattr(settings, "DRC_BASE_URL", "")
        or "http://localhost:8001"
    )
    base_url = str(raw_url).strip().rstrip("/")
    for suffix in ("/acps-dsp-v2", "/acps-atr-v2"):
        if base_url.endswith(suffix):
            base_url = base_url[: -len(suffix)]
    return base_url or "http://localhost:8001"


def _registry_atr_token() -> str:
    return str(
        getattr(settings, "REGISTRY_ATR_SERVICE_TOKEN", "")
        or os.getenv("REGISTRY_ATR_SERVICE_TOKEN")
        or os.getenv("DISCOVERY_REGISTRY_ATR_SERVICE_TOKEN")
        or os.getenv("REGISTRY_SERVICE_TOKEN")
        or os.getenv("ORCHESTRATOR_REGISTRY_SERVICE_TOKEN")
        or ""
    )


def _registry_item_endpoint(item: Mapping[str, Any]) -> Dict[str, Any]:
    acp = _as_dict(item.get("acp") or item.get("acs"))
    endpoints = acp.get("endpoints") or acp.get("endPoints") or []
    if not isinstance(endpoints, list) or not endpoints:
        return {}
    endpoint = endpoints[0]
    return dict(endpoint) if isinstance(endpoint, Mapping) else {}


def _registry_declared_skills(item: Mapping[str, Any]) -> List[Dict[str, Any]]:
    acp = _as_dict(item.get("acp") or item.get("acs"))
    raw_skills = item.get("declaredSkills") or acp.get("skills") or []
    if not isinstance(raw_skills, list):
        raw_skills = []
    skills: List[Dict[str, Any]] = []
    for index, raw_skill in enumerate(raw_skills, start=1):
        if not isinstance(raw_skill, Mapping):
            continue
        skill = dict(raw_skill)
        skill_id = skill.get("id") or skill.get("skillId") or skill.get("skill_id")
        if not skill_id:
            skill_id = f"passport.skill.{index}"
        skill["id"] = str(skill_id)
        if "name" not in skill and skill.get("skillName"):
            skill["name"] = skill.get("skillName")
        skills.append(skill)
    if not skills:
        passport_id = item.get("passportId") or item.get("agentAic") or "agent"
        skills.append(
            {
                "id": f"passport/{passport_id}",
                "name": "Registry approved agent",
                "description": item.get("description") or item.get("name") or "",
                "inputModes": ["text/plain", "application/json"],
                "outputModes": ["text/plain", "application/json"],
            }
        )
    return skills


def _registry_item_to_discovery_acs(item: Mapping[str, Any]) -> Dict[str, Any]:
    acp = _as_dict(item.get("acp") or item.get("acs"))
    endpoint = _registry_item_endpoint(item)
    runtime = _as_dict(item.get("runtime"))
    interaction = _as_dict(acp.get("interaction"))
    capabilities = _as_dict(acp.get("capabilities"))
    if not capabilities:
        capabilities = {
            "streaming": interaction.get("streaming", False),
            "messageQueue": interaction.get("messageQueue") or [],
            "notification": interaction.get("notification", False),
        }
    aic = str(item.get("agentAic") or item.get("aic") or acp.get("aic") or "")
    return {
        "aic": aic,
        "name": item.get("name") or acp.get("name") or aic,
        "active": bool(item.get("eligibleForDispatch", True)),
        "skills": _registry_declared_skills(item),
        "version": item.get("version") or acp.get("version") or "1.0.0",
        "provider": acp.get("provider") or {},
        "endPoints": [endpoint] if endpoint else [],
        "description": item.get("description") or acp.get("description") or "",
        "capabilities": capabilities,
        "protocolVersion": acp.get("protocolVersion") or "02.00",
        "securitySchemes": acp.get("securitySchemes") or {},
        "lastModifiedTime": item.get("updatedAt") or acp.get("lastModifiedTime") or "",
        "defaultInputModes": acp.get("inputModes") or ["text/plain", "application/json"],
        "defaultOutputModes": acp.get("outputModes") or ["text/plain", "application/json"],
        "eligibleForDispatch": item.get("eligibleForDispatch"),
        "dispatchReasons": item.get("dispatchReasons") or [],
        "orchestratorHints": item.get("orchestratorHints") or {},
        "visibility": item.get("visibility") or {},
        "runtime": runtime,
        "registryPassport": {
            "passportId": item.get("passportId"),
            "reviewId": item.get("reviewId"),
            "status": item.get("status"),
            "decision": item.get("decision"),
            "riskLevel": item.get("riskLevel"),
            "permissionTier": item.get("permissionTier"),
        },
    }


def _registry_item_dispatchable(item: Mapping[str, Any]) -> bool:
    runtime = _as_dict(item.get("runtime"))
    health_probe = _as_dict(runtime.get("healthProbe"))
    rpc_probe = _as_dict(runtime.get("rpcProbe"))
    if item.get("eligibleForDispatch") is not True:
        return False
    if runtime.get("status") != "online" or runtime.get("acceptingTasks") is not True:
        return False
    if health_probe and health_probe.get("healthy") is not True:
        return False
    if rpc_probe and (rpc_probe.get("ok") is not True or rpc_probe.get("fallback") is True):
        return False
    return True


def _fetch_registry_dispatchable_agents_sync(limit: int, requester_user_id: str = "") -> List[Dict[str, Any]]:
    fetch_limit = max(1, min(200, max(int(limit or 1), 25)))
    params: Dict[str, Any] = {"limit": fetch_limit}
    if requester_user_id:
        params["requesterUserId"] = requester_user_id
    url = f"{_registry_atr_base_url()}/acps-atr-v2/passports/discovery?{urllib.parse.urlencode(params)}"
    headers = {"Accept": "application/json"}
    token = _registry_atr_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    result = payload.get("result") if isinstance(payload, Mapping) else None
    items = result.get("items") if isinstance(result, Mapping) else []
    if not isinstance(items, list):
        return []
    agents = [
        _registry_item_to_discovery_acs(item)
        for item in items
        if isinstance(item, Mapping) and _registry_item_dispatchable(item)
    ]
    logger.info("Loaded %d dispatchable agents from Registry ATR discovery feed", len(agents))
    return agents


async def _fetch_registry_dispatchable_agents(limit: int, requester_user_id: str = "") -> List[Dict[str, Any]]:
    try:
        return await asyncio.to_thread(_fetch_registry_dispatchable_agents_sync, limit, requester_user_id)
    except Exception as exc:
        logger.warning("Registry ATR discovery feed unavailable; falling back to local DRC cache: %s", exc)
        return []

class DiscoveryService:
    """Agent ?????????"""

    def __init__(self):
        """????????"""
        pass

    @time_it_return_ms
    async def discover_agents_async(
        self, request: DiscoveryRequest
    ) -> Tuple[Tuple[List[DiscoveryAgentSkill], Dict, str], float]:
        """
        ?????????? Agent???????

        Returns:
            ((agents_list, acs_dict, reasoning), duration_ms)
        """
        try:
            legacy_filters = convert_filter_to_legacy(request.filter)
            metadata = _request_metadata(request)
            all_agents, acs_dict, reasoning = await self._discovery_agents_async(
                request.query,
                limit=request.limit,
                filters=legacy_filters,
                requester_user_id=_requester_user_id_from_metadata(metadata),
                workable_only=_workable_only_from_metadata(metadata),
            )
            return all_agents, acs_dict, reasoning

        except Exception as e:
            raise DiscoveryException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_name=DiscoveryError.DISCOVERY_FAIL,
                error_msg=f"Failed to discover: {str(e)}",
                input_params={"query": request.query},
            )

    async def _search_agents_async(self, query: str) -> List[DiscoveryAgentSkill]:
        agents_schema = []
        try:
            async with AsyncSessionLocal() as session:
                stmt = (
                    select(Agent)
                    .where(Agent.acs["description"].astext.like(f"%{query}%"))
                    .order_by(Agent.seq.desc())
                    .limit(3)
                )
                result = await session.execute(stmt)
                agents = result.scalars().all()
                for agent in agents:
                    agent_schema = DiscoveryAgentSkill(
                        aic=agent.aic,
                        skillId=None,
                        ranking=None,
                        memo=None
                    )
                    agents_schema.append(agent_schema)
        except Exception as e:
            raise DiscoveryException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_name=DiscoveryError.DATABASE_ERROR,
                error_msg=f"Database query failed: {e}",
                input_params={"query": query},
            )
        return agents_schema
    
    async def _discovery_agents_async(
        self,
        query: str,
        limit: int,
        filters: DiscoveryFilters = None,
        requester_user_id: str = "",
        workable_only: bool = True,
    ) -> Tuple[List[DiscoveryAgentSkill], Dict, str]:
        agents_schema = []
        reasoning = ""

        try:
            agents_data = []
            if workable_only:
                agents_data = await _fetch_registry_dispatchable_agents(limit, requester_user_id)

            if not agents_data:
                async with AsyncSessionLocal() as session:
                    stmt = select(Agent)
                    where_clauses = self._build_filter_clauses(filters)
                    for clause in where_clauses:
                        stmt = stmt.where(clause)
                    result = await session.execute(stmt)
                    agents = result.scalars().all()
                    agents_data = [agent.acs for agent in agents]
                    agents_data = _filter_workable_agents(
                        agents_data,
                        requester_user_id=requester_user_id,
                        workable_only=workable_only,
                    )

            enhanced_button = True
            if enhanced_button:
                agents_schema, acs_dict, reasoning = await self._enhanced_search_with_timeout(
                    query, agents_data, limit
                )
            else:
                for agent in agents_data[:limit]:
                    agent_schema = DiscoveryAgentSkill(
                        aic=None, skillId=None, ranking=None, memo=""
                    )
                    agents_schema.append(agent_schema)
                acs_dict = {}
                reasoning = ""

        except Exception as e:
            raise DiscoveryException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_name=DiscoveryError.DATABASE_ERROR,
                error_msg=f"Database query failed: {e}",
                input_params={"query": query},
            )
        return agents_schema, acs_dict, reasoning

    def _build_filter_clauses(self, filters: Optional[DiscoveryFilters]):
        from sqlalchemy import and_, or_, not_, func
        from sqlmodel import Boolean

        clauses = []
        if filters is None or (filters.hasEndpoints is None and filters.hasWebAppUrl is None):
            clauses.append(
                or_(
                    func.jsonb_array_length(Agent.acs["endPoints"]) > 0,
                    and_(
                        Agent.acs["webAppUrl"].is_not(None),
                        Agent.acs["webAppUrl"].astext != "null",
                        Agent.acs["webAppUrl"].astext != ""
                    )
                )
            )
        if filters is None or filters.isActive is None:
            clauses.append(
                or_(
                    Agent.acs["active"].astext.cast(Boolean) == True,
                    Agent.acs["active"].astext == "true"
                )
            )

        if filters is None:
            return clauses

        if filters.protocolVersions:
            clauses.append(Agent.acs["protocolVersion"].astext.in_(filters.protocolVersions))
        if filters.protocolVersions_reject:
            clauses.append(not_(Agent.acs["protocolVersion"].astext.in_(filters.protocolVersions_reject)))
        if filters.transports:
            transport_conditions = [
                func.jsonb_path_exists(Agent.acs, cast(f'$.endPoints[*] ? (@.transport == "{transport}")', JSONPATH))
                for transport in filters.transports
            ]
            clauses.append(or_(*transport_conditions))
        if filters.transports_reject:
            transport_conditions = [
                not_(func.jsonb_path_exists(Agent.acs, cast(f'$.endPoints[*] ? (@.transport == "{transport}")', JSONPATH)))
                for transport in filters.transports_reject
            ]
            clauses.extend(transport_conditions)
        if filters.requiredSecuritySchemes:
            security_conditions = [
                Agent.acs["securitySchemes"].has_key(scheme)
                for scheme in filters.requiredSecuritySchemes
            ]
            clauses.append(or_(*security_conditions))
        if filters.requiredSecuritySchemes_reject:
            reject_conditions = [
                not_(Agent.acs["securitySchemes"].has_key(scheme))
                for scheme in filters.requiredSecuritySchemes_reject
            ]
            clauses.extend(reject_conditions)
        if filters.skillTags:
            tag_conditions = [
                func.jsonb_path_exists(Agent.acs, cast(f'$.skills[*] ? (@.tags[*] == "{tag}")', JSONPATH))
                for tag in filters.skillTags
            ]
            clauses.append(or_(*tag_conditions))
        if filters.skillTags_reject:
            reject_conditions = [
                not_(func.jsonb_path_exists(Agent.acs, cast(f'$.skills[*] ? (@.tags[*] == "{tag}")', JSONPATH)))
                for tag in filters.skillTags_reject
            ]
            clauses.extend(reject_conditions)
        if filters.skillIds:
            id_conditions = [
                func.jsonb_path_exists(Agent.acs, cast(f'$.skills[*] ? (@.id == "{skill_id}")', JSONPATH))
                for skill_id in filters.skillIds
            ]
            clauses.append(or_(*id_conditions))
        if filters.skillIds_reject:
            reject_conditions = [
                not_(func.jsonb_path_exists(Agent.acs, cast(f'$.skills[*] ? (@.id == "{skill_id}")', JSONPATH)))
                for skill_id in filters.skillIds_reject
            ]
            clauses.extend(reject_conditions)
        if filters.providerCountryCodes:
            clauses.append(Agent.acs["provider"]["countryCode"].astext.in_(filters.providerCountryCodes))
        if filters.providerCountryCodes_reject:
            clauses.append(not_(Agent.acs["provider"]["countryCode"].astext.in_(filters.providerCountryCodes_reject)))
        if filters.providerOrganizations:
            org_conditions = [Agent.acs["provider"]["organization"].astext.ilike(f"%{org}%") for org in filters.providerOrganizations]
            clauses.append(or_(*org_conditions))
        if filters.providerOrganizations_reject:
            reject_conditions = [not_(Agent.acs["provider"]["organization"].astext.ilike(f"%{org}%")) for org in filters.providerOrganizations_reject]
            clauses.extend(reject_conditions)
        if filters.providerLicenses:
            license_conditions = [Agent.acs["provider"]["license"].astext.ilike(f"%{license_name}%") for license_name in filters.providerLicenses]
            clauses.append(or_(*license_conditions))
        if filters.providerLicenses_reject:
            reject_conditions = [not_(Agent.acs["provider"]["license"].astext.ilike(f"%{license_name}%")) for license_name in filters.providerLicenses_reject]
            clauses.extend(reject_conditions)
        if filters.inputModes:
            mode_conditions = [func.jsonb_path_exists(Agent.acs, cast(f'$.skills[*] ? (@.inputModes[*] == "{mode}")', JSONPATH)) for mode in filters.inputModes]
            clauses.append(or_(*mode_conditions))
        if filters.inputModes_reject:
            reject_conditions = [not_(func.jsonb_path_exists(Agent.acs, cast(f'$.skills[*] ? (@.inputModes[*] == "{mode}")', JSONPATH))) for mode in filters.inputModes_reject]
            clauses.extend(reject_conditions)
        if filters.outputModes:
            mode_conditions = [func.jsonb_path_exists(Agent.acs, cast(f'$.skills[*] ? (@.outputModes[*] == "{mode}")', JSONPATH)) for mode in filters.outputModes]
            clauses.append(or_(*mode_conditions))
        if filters.outputModes_reject:
            reject_conditions = [not_(func.jsonb_path_exists(Agent.acs, cast(f'$.skills[*] ? (@.outputModes[*] == "{mode}")', JSONPATH))) for mode in filters.outputModes_reject]
            clauses.extend(reject_conditions)
        if filters.isActive is not None:
            val = True if filters.isActive else False
            clauses.append(or_(Agent.acs["active"].astext.cast(Boolean) == val, Agent.acs["active"].astext == str(val).lower()))
        if filters.aic:
            clauses.append(Agent.aic == filters.aic)
        if filters.aicStartWith:
            clauses.append(Agent.aic.startswith(filters.aicStartWith))
        if filters.entityUserId:
            clauses.append(Agent.acs["entityUserId"].astext == filters.entityUserId)
        if filters.hasEndpoints is not None:
            if filters.hasEndpoints:
                clauses.append(func.jsonb_array_length(Agent.acs["endPoints"]) > 0)
            else:
                clauses.append(func.jsonb_array_length(Agent.acs["endPoints"]) == 0)
        if filters.hasWebAppUrl is not None:
            if filters.hasWebAppUrl:
                clauses.append(Agent.acs["webAppUrl"].astext != "")
            else:
                clauses.append(or_(Agent.acs["webAppUrl"].is_(None), Agent.acs["webAppUrl"].astext == "", Agent.acs["webAppUrl"].astext == "null"))
        cap = filters.capabilities
        if cap:
            if cap.streaming is not None:
                val = True if cap.streaming else False
                clauses.append(or_(Agent.acs["capabilities"]["streaming"].astext.cast(Boolean) == val, Agent.acs["capabilities"]["streaming"].astext == str(val).lower()))
            if cap.notification is not None:
                val = True if cap.notification else False
                clauses.append(or_(Agent.acs["capabilities"]["notification"].astext.cast(Boolean) == val, Agent.acs["capabilities"]["notification"].astext == str(val).lower()))
            if cap.messageQueue:
                mq_conditions = [func.jsonb_path_exists(Agent.acs, cast(f'$.capabilities.messageQueue[*] ? (@ == "{mq}")', JSONPATH)) for mq in cap.messageQueue]
                clauses.append(or_(*mq_conditions))
        return clauses

    async def _fallback_search_agents(self, query: str, agents_data, count: int = 5, reason: str = "") -> Tuple[List[DiscoveryAgentSkill], Dict, str]:
        agents_schema = []
        acs_dict = {}
        if not agents_data:
            return agents_schema, acs_dict, reason or "????????????"

        normalized_query = (query or "").lower()
        keywords = [kw for kw in normalized_query.replace("?", " ").replace(",", " ").split() if kw]

        scored_agents = []
        for agent in agents_data:
            text_parts = [
                str(agent.get("name") or ""),
                str(agent.get("description") or ""),
            ]
            for skill in agent.get("skills", []) or []:
                text_parts.append(str(skill.get("name") or ""))
                text_parts.append(str(skill.get("description") or ""))
                text_parts.extend([str(tag) for tag in (skill.get("tags") or [])])
            haystack = " ".join(text_parts).lower()
            score = sum(1 for kw in keywords if kw and kw in haystack)
            scored_agents.append((score, agent))

        scored_agents.sort(key=lambda item: item[0], reverse=True)
        top_agents = [agent for _, agent in scored_agents[:count]]

        for rank, agent in enumerate(top_agents, start=1):
            skills = agent.get("skills") or []
            skill_id = ""
            if skills:
                skill_id = str(skills[0].get("id") or "")
            agent_schema = DiscoveryAgentSkill(
                aic=agent.get("aic"),
                skillId=skill_id,
                ranking=rank,
                memo="fallback: LLM??????????????",
            )
            agents_schema.append(agent_schema)
            acs_dict[agent.get("aic")] = agent

        fallback_reason = reason or "LLM??????????????"
        return agents_schema, acs_dict, fallback_reason

    async def _enhanced_search_agents(
        self, query: str, agents_data, count: int = 5
    ) -> Tuple[List[DiscoveryAgentSkill], Dict, str]:
        agents_schema = []
        reasoning = ""
        try:
            await AgentDiscovery.load_agents_async(agents_data)
            result = await AgentDiscovery.discover_skills_enhanced(task_description=query, k=count)

            if not isinstance(result, dict):
                logger.warning("??????????????????????")
                return await self._fallback_search_agents(query, agents_data, count, "??????????????")

            if result.get("error"):
                logger.warning("?????????: %s??????????", result.get("error"))
                return await self._fallback_search_agents(query, agents_data, count, f"???????????{result.get('error')}")

            skills = result.get("skills") or []
            if not skills:
                logger.warning("????????skills??????????")
                return await self._fallback_search_agents(query, agents_data, count, "???????????????")

            reasoning = result.get("reasoning", "")
            acs_dict = {}
            for agent in skills:
                agent_schema = DiscoveryAgentSkill(
                    aic=agent.get("aic"),
                    skillId=agent.get("skillid"),
                    ranking=agent.get("ranking"),
                    memo=agent.get("memo", ""),
                )
                agents_schema.append(agent_schema)
                acs_dict[agent.get('aic')] = agent.get('acs')
        except Exception as e:
            logger.warning("??????????????????: %s", e)
            return await self._fallback_search_agents(query, agents_data, count, f"???????????{e}")
        return agents_schema, acs_dict, reasoning

    async def _enhanced_search_with_timeout(
        self, query: str, agents_data, count: int = 5
    ) -> Tuple[List[DiscoveryAgentSkill], Dict, str]:
        timeout = _enhanced_search_timeout_seconds()
        if timeout is None:
            return await self._enhanced_search_agents(query, agents_data, count)
        try:
            return await asyncio.wait_for(
                self._enhanced_search_agents(query, agents_data, count),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Enhanced discovery timed out after %.2fs; using local fallback.", timeout)
            return await self._fallback_search_agents(
                query,
                agents_data,
                count,
                f"enhanced discovery timed out after {timeout:.2f}s; used local keyword fallback",
            )

    @time_it_return_ms
    async def discover_agents_filtered(
        self, request: DiscoveryRequest
    ) -> Tuple[Tuple[List[DiscoveryAgentSkill], Dict], float]:
        try:
            legacy_filters = convert_filter_to_legacy(request.filter)
            metadata = _request_metadata(request)
            requester_user_id = _requester_user_id_from_metadata(metadata)
            workable_only = _workable_only_from_metadata(metadata)

            async with AsyncSessionLocal() as session:
                stmt = select(Agent)
                where_clauses = self._build_filter_clauses(legacy_filters)
                for clause in where_clauses:
                    stmt = stmt.where(clause)
                limit = request.limit or 10
                stmt = stmt.limit(limit)
                result = await session.execute(stmt)
                agents = result.scalars().all()

            agents_schema = []
            acs_dict = {}
            workable_agents = [
                agent
                for agent in agents
                if not workable_only
                or not _agent_workability_reasons(agent.acs or {}, requester_user_id=requester_user_id)
            ]
            for rank, agent in enumerate(workable_agents, start=1):
                agent_schema = DiscoveryAgentSkill(
                    aic=agent.aic,
                    skillId="",
                    ranking=rank,
                    memo="",
                )
                agents_schema.append(agent_schema)
                acs_dict[agent.aic] = agent.acs

            return agents_schema, acs_dict

        except Exception as e:
            raise DiscoveryException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_name=DiscoveryError.DATABASE_ERROR,
                error_msg=f"Filtered query failed: {str(e)}",
                input_params={"filter": str(request.filter)},
            )

discovery_service = DiscoveryService()
