from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import deque
from datetime import datetime
from typing import Any, AsyncIterator, Deque, Dict, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.service_auth import require_registry_service_token


router = APIRouter(prefix="/events", tags=["runtime-events"])
logger = logging.getLogger("registry.events")

_MAX_HISTORY = 200
_history: Deque[Dict[str, Any]] = deque(maxlen=_MAX_HISTORY)
_subscribers: set[asyncio.Queue[Dict[str, Any]]] = set()


class RuntimeEventIn(BaseModel):
    source: str = Field(default="external")
    type: str
    level: str = Field(default="info")
    title: str
    message: str = Field(default="")
    agent: Dict[str, Any] = Field(default_factory=dict)
    review: Dict[str, Any] = Field(default_factory=dict)
    passport: Dict[str, Any] = Field(default_factory=dict)
    userId: str = Field(default="")
    extra: Dict[str, Any] = Field(default_factory=dict)


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, uuid.UUID)):
        return str(value)
    return str(value)


def _event_payload(
    *,
    source: str,
    event_type: str,
    level: str,
    title: str,
    message: str,
    agent: Any = None,
    review: Optional[Dict[str, Any]] = None,
    passport: Any = None,
    user_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    agent_id = str(getattr(agent, "id", "") or "")
    created_by_id = str(getattr(agent, "created_by_id", "") or "")
    passport_payload = getattr(passport, "passport_payload", None) or {}
    payload = {
        "id": f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}",
        "source": source,
        "type": event_type,
        "level": level,
        "title": title,
        "message": message,
        "createdAt": datetime.now().astimezone().isoformat(),
        "agent": {
            "id": agent_id,
            "aic": str(getattr(agent, "aic", "") or ""),
            "name": str(getattr(agent, "name", "") or ""),
            "version": str(getattr(agent, "version", "") or ""),
            "approvalStatus": str(getattr(getattr(agent, "approval_status", ""), "value", getattr(agent, "approval_status", "") or "")),
            "createdById": created_by_id,
        },
        "review": review or {},
        "passport": {
            "id": str(getattr(passport, "id", "") or ""),
            "passportId": str(getattr(passport, "passport_id", "") or ""),
            "status": str(getattr(passport, "status", "") or passport_payload.get("status") or ""),
            "decision": str(getattr(passport, "decision", "") or passport_payload.get("decision") or ""),
            "riskLevel": str(getattr(passport, "risk_level", "") or ""),
            "permissionTier": str(getattr(passport, "permission_tier", "") or ""),
        },
        "userId": str(user_id or created_by_id or ""),
    }
    if extra:
        payload["extra"] = extra
    return payload


def publish_event(event: Dict[str, Any]) -> None:
    event.setdefault("id", f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}")
    event.setdefault("createdAt", datetime.now().astimezone().isoformat())
    event.setdefault("agent", {})
    event.setdefault("review", {})
    event.setdefault("passport", {})
    event.setdefault("extra", {})
    _history.append(event)
    agent = event.get("agent") or {}
    review = event.get("review") or {}
    passport = event.get("passport") or {}
    extra = event.get("extra") or {}
    logger.info(
        "[runtime-event] source=%s type=%s level=%s title=%s agent=%s status=%s decision=%s passport=%s aic=%s service=%s stage=%s path=%s code=%s message=%s",
        event.get("source") or "-",
        event.get("type") or "-",
        event.get("level") or "-",
        event.get("title") or "-",
        agent.get("name") or "-",
        agent.get("approvalStatus") or "-",
        review.get("decision") or passport.get("decision") or "-",
        passport.get("status") or "-",
        agent.get("aic") or "-",
        extra.get("service") or "-",
        extra.get("stage") or "-",
        extra.get("path") or "-",
        extra.get("statusCode") or extra.get("status_code") or "-",
        event.get("message") or "-",
    )
    stale = []
    for queue in list(_subscribers):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            stale.append(queue)
    for queue in stale:
        _subscribers.discard(queue)


def publish_agent_event(
    *,
    event_type: str,
    level: str,
    title: str,
    message: str,
    agent: Any,
    review: Optional[Dict[str, Any]] = None,
    passport: Any = None,
    user_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    event = _event_payload(
        source="registry",
        event_type=event_type,
        level=level,
        title=title,
        message=message,
        agent=agent,
        review=review,
        passport=passport,
        user_id=user_id,
        extra=extra,
    )
    publish_event(event)
    return event


def _format_sse(event: Dict[str, Any]) -> str:
    event_name = str(event.get("type") or "message")
    data = json.dumps(event, ensure_ascii=False, default=_json_default)
    event_id = str(event.get("id") or "")
    return f"id: {event_id}\nevent: {event_name}\ndata: {data}\n\n"


async def _event_generator(request: Request) -> AsyncIterator[str]:
    queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=100)
    _subscribers.add(queue)
    try:
        for event in list(_history)[-20:]:
            yield _format_sse(event)
        yield ": registry event stream ready\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15)
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"
                continue
            yield _format_sse(event)
    finally:
        _subscribers.discard(queue)


@router.get("/stream")
async def stream_events(request: Request):
    return StreamingResponse(
        _event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/recent")
async def recent_events(limit: int = 20):
    bounded_limit = max(1, min(limit, _MAX_HISTORY))
    return {"items": list(_history)[-bounded_limit:], "total": len(_history)}


@router.post("/publish", dependencies=[Depends(require_registry_service_token)])
async def publish_runtime_event(event: RuntimeEventIn):
    payload = event.model_dump()
    payload["userId"] = payload.pop("userId", "") or ""
    publish_event(payload)
    return {"ok": True, "id": payload["id"]}
