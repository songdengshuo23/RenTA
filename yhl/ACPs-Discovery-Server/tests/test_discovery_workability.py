import asyncio

import pytest

from app.discovery.service import DiscoveryService, _agent_workability_reasons, _filter_workable_agents


def _agent(aic, **updates):
    payload = {
        "aic": aic,
        "active": True,
        "endPoints": [{"url": f"http://127.0.0.1/{aic}/rpc"}],
        "orchestratorHints": {"eligibleForAutoDispatch": True},
        "runtimeStatus": {"status": "online", "currentLoad": 0, "maxConcurrentTasks": 2},
    }
    payload.update(updates)
    return payload


def test_workability_blocks_offline_overloaded_and_dispatch_denied_agents():
    agents = [
        _agent("ready"),
        _agent("offline", runtimeStatus={"status": "offline"}),
        _agent("busy", runtimeStatus={"status": "online", "currentLoad": 2, "maxConcurrentTasks": 2}),
        _agent("blocked", dispatchReasons=["passport_review_due"]),
    ]

    filtered = _filter_workable_agents(agents)

    assert [agent["aic"] for agent in filtered] == ["ready"]
    assert "agent_runtime_offline" in _agent_workability_reasons(agents[1])
    assert "agent_overloaded" in _agent_workability_reasons(agents[2])
    assert "passport_review_due" in _agent_workability_reasons(agents[3])


def test_workability_allows_private_agent_for_owner_only():
    owner_id = "user-1"
    agent = _agent(
        "private",
        visibility="private",
        entityUserId=owner_id,
        orchestratorHints={"eligibleForAutoDispatch": True, "callableByOthers": False},
    )

    assert _agent_workability_reasons(agent, requester_user_id=owner_id) == []
    assert "agent_private_to_owner" in _agent_workability_reasons(agent, requester_user_id="user-2")
    assert "agent_sharing_disabled" in _agent_workability_reasons(agent, requester_user_id="user-2")


@pytest.mark.asyncio
async def test_enhanced_search_timeout_uses_keyword_fallback(monkeypatch):
    service = DiscoveryService()

    async def _slow_enhanced_search(query, agents_data, count=5):
        await asyncio.sleep(1)
        return [], {}, "slow"

    monkeypatch.setenv("DISCOVERY_ENHANCED_TIMEOUT_SECONDS", "0.01")
    monkeypatch.setattr(service, "_enhanced_search_agents", _slow_enhanced_search)

    agents, acs_map, reasoning = await service._enhanced_search_with_timeout(
        "backend monitor",
        [
            _agent(
                "ready",
                name="Backend Monitor",
                description="backend monitor service health",
                skills=[{"id": "monitor.health", "name": "Health Monitor"}],
            )
        ],
        1,
    )

    assert len(agents) == 1
    assert agents[0].aic == "ready"
    assert "ready" in acs_map
    assert "timed out" in reasoning
