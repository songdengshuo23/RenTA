import json
import os
from pathlib import Path
from typing import List, Optional, Dict
import logging
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
            all_agents, acs_dict, reasoning = await self._discovery_agents_async(
                request.query, limit=request.limit, filters=legacy_filters
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
    
    async def _discovery_agents_async(self, query: str, limit: int, filters: DiscoveryFilters = None) -> Tuple[List[DiscoveryAgentSkill], Dict, str]:
        agents_schema = []
        reasoning = ""

        try:
            async with AsyncSessionLocal() as session:
                stmt = select(Agent)
                where_clauses = self._build_filter_clauses(filters)
                for clause in where_clauses:
                    stmt = stmt.where(clause)
                result = await session.execute(stmt)
                agents = result.scalars().all()
                agents_data = [agent.acs for agent in agents]

            enhanced_button = True
            if enhanced_button:
                agents_schema, acs_dict, reasoning = await self._enhanced_search_agents(
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

    @time_it_return_ms
    async def discover_agents_filtered(
        self, request: DiscoveryRequest
    ) -> Tuple[Tuple[List[DiscoveryAgentSkill], Dict], float]:
        try:
            legacy_filters = convert_filter_to_legacy(request.filter)

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
            for rank, agent in enumerate(agents, start=1):
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
