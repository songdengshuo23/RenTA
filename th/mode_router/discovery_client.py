from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Mapping


class DiscoveryCallError(RuntimeError):
    pass


def _selection_mode(payload: Mapping[str, Any]) -> str:
    explicit = str(payload.get("selection_mode") or payload.get("selectionMode") or "").strip()
    if explicit:
        return explicit
    route_label = str(payload.get("route_label") or payload.get("routeLabel") or "").strip().lower()
    if route_label in {"agent", "single_agent", "single-agent"}:
        return "single_agent"
    if route_label in {"multi_agent", "multi-agent", "multiagent", "多agent", "澶欰gent"}:
        return "multi_agent"
    return ""


def _selection_limits(payload: Mapping[str, Any], selection_mode: str) -> dict[str, int]:
    limit = int(payload.get("limit", 5))
    min_agents = payload.get("min_agents", payload.get("minAgents"))
    max_agents = payload.get("max_agents", payload.get("maxAgents"))
    if min_agents is None:
        min_agents = 2 if selection_mode == "multi_agent" else 1
    if max_agents is None:
        max_agents = limit
    return {"minAgents": int(min_agents), "maxAgents": int(max_agents)}


def _context_with_selection(payload: Mapping[str, Any], selection_mode: str) -> Mapping[str, Any] | None:
    raw_context = payload.get("context")
    context = dict(raw_context) if isinstance(raw_context, Mapping) else {}
    context.setdefault("conversationId", str(payload.get("session_id") or payload.get("sessionId") or payload.get("conversation_id") or payload.get("conversationId") or "orchestrator-discovery"))
    context.setdefault("recentTurns", [])
    context.setdefault("userProfile", {})
    metadata = dict(context.get("metadata") or {})
    if selection_mode:
        metadata["selectionMode"] = selection_mode
    metadata.update(_selection_limits(payload, selection_mode))
    metadata["workableOnly"] = bool(payload.get("workable_only", payload.get("workableOnly", True)))
    requester_user_id = payload.get("requester_user_id") or payload.get("requesterUserId") or payload.get("user_id") or payload.get("userId")
    if requester_user_id:
        metadata["requesterUserId"] = str(requester_user_id)
    if metadata:
        context["metadata"] = metadata
    return context or raw_context


def build_discovery_request(task: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    selection_mode = _selection_mode(payload)
    return {
        "type": payload.get("type", "explicit"),
        "query": task,
        "limit": payload.get("limit", 5),
        "context": _context_with_selection(payload, selection_mode),
        "selection": {
            "mode": selection_mode,
            **_selection_limits(payload, selection_mode),
            "workableOnly": bool(payload.get("workable_only", payload.get("workableOnly", True))),
        },
        "filter": payload.get("filter"),
        "forwardDepthLimit": payload.get("forwardDepthLimit", 1),
        "forwardFanoutLimit": payload.get("forwardFanoutLimit", 1),
        "forwardFanoutRemaining": payload.get("forwardFanoutRemaining", 0),
        "forwardChain": payload.get("forwardChain", []),
        "forwardTrustedServers": payload.get("forwardTrustedServers", []),
        "forwardSignatures": payload.get("forwardSignatures", []),
        "forwardEachTimeoutMs": payload.get("forwardEachTimeoutMs", 10000),
        "forwardTotalTimeoutMs": payload.get("forwardTotalTimeoutMs", 60000),
    }


def call_discovery(discovery_url: str, request_payload: Mapping[str, Any], timeout: float = 120.0, retries: int = 1, retry_backoff: float = 2.0) -> dict[str, Any]:
    attempts = max(1, retries + 1)
    last_error = ""

    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(
            discovery_url,
            data=json.dumps(request_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            last_error = f"HTTP {exc.code}: {body}"
            if exc.code not in {429, 500, 502, 503, 504} or attempt >= attempts:
                raise DiscoveryCallError(last_error) from exc
        except Exception as exc:
            last_error = str(exc)
            if attempt >= attempts:
                raise DiscoveryCallError(last_error) from exc

        time.sleep(retry_backoff * attempt)

    raise DiscoveryCallError(last_error or "unknown discovery error")
