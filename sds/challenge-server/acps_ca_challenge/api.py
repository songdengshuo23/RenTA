import os
import logging
import json
from typing import Any
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from acps_ca_challenge.schema import AgentAIC, ChallengeToken
from acps_ca_challenge.security import require_challenge_write_token
from acps_ca_challenge.service import get_challenge, save_challenge
from acps_ca_challenge.config import settings
from acps_ca_challenge.exception import ChallengeNotFoundError, ChallengeStorageError

router = APIRouter()
LOGGER = logging.getLogger("challenge_server")
EVENT_CENTER_URL = os.getenv(
    "EVENT_CENTER_URL", "http://127.0.0.1:8001/api/events/publish"
)
EVENT_CENTER_TOKEN = os.getenv("EVENT_CENTER_TOKEN", "local-dev-token")


async def publish_runtime_event(
    *,
    event_type: str,
    level: str,
    title: str,
    message: str,
    aic: str = "",
    extra: dict[str, Any] | None = None,
) -> None:
    if not EVENT_CENTER_URL or not EVENT_CENTER_TOKEN:
        return
    payload = {
        "source": "challenge",
        "type": event_type,
        "level": level,
        "title": title,
        "message": message,
        "agent": {"aic": aic or ""},
        "extra": {"service": "challenge-server", **(extra or {})},
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        EVENT_CENTER_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {EVENT_CENTER_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=2).read()
    except Exception as exc:
        LOGGER.debug("failed to publish challenge runtime event: %s", exc)


@router.get("/health", tags=["System"])
async def health_check():
    """健康检查端点。"""
    return {"status": "OK"}


@router.get(
    "/{agent_aic}/{token}",
    response_class=PlainTextResponse,
    summary="Get Challenge Response",
    tags=["Challenge"],
    responses={
        200: {"description": "Challenge response found", "content": {"text/plain": {}}},
        404: {"description": "Challenge not found"},
        422: {"description": "Validation Error"},
    },
)
async def get_challenge_endpoint(agent_aic: AgentAIC, token: ChallengeToken):
    """
    获取指定 Agent 和 Token 的挑战响应。
    此端点由 CA 服务器在验证期间调用。
    """
    try:
        content = get_challenge(agent_aic, token)
        LOGGER.info(f"Served challenge: AIC={agent_aic} Token={token}")
        await publish_runtime_event(
            event_type="challenge.response.served",
            level="success",
            title="Challenge 响应已读取",
            message=f"AIC {agent_aic} 的 HTTP-01 challenge 已被 CA 读取。",
            aic=str(agent_aic),
            extra={
                "stage": "get-challenge",
                "path": "/acps-atr-v2/{agent_aic}/{token}",
                "token": str(token),
            },
        )
        return content
    except ChallengeNotFoundError:
        LOGGER.warning(f"Challenge not found: AIC={agent_aic} Token={token}")
        await publish_runtime_event(
            event_type="challenge.response.missing",
            level="warning",
            title="Challenge 响应不存在",
            message=f"AIC {agent_aic} 的 HTTP-01 challenge 未找到。",
            aic=str(agent_aic),
            extra={
                "stage": "get-challenge",
                "path": "/acps-atr-v2/{agent_aic}/{token}",
                "token": str(token),
                "statusCode": 404,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found"
        )
    except ChallengeStorageError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error",
        )


@router.post(
    "/{agent_aic}/{token}",
    summary="Set Challenge Response",
    tags=["Challenge"],
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Challenge set successfully"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)
async def set_challenge_endpoint(
    agent_aic: AgentAIC,
    token: ChallengeToken,
    request: Request,
    _auth: None = Depends(require_challenge_write_token),
):
    """
    设置指定 Agent 和 Token 的挑战响应。
    此端点由 CA 客户端 (Agent) 调用。
    """
    # 将请求体作为文本读取
    body = await request.body()
    if len(body) > settings.MAX_CHALLENGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Challenge response is too large",
        )

    payload = body.decode("utf-8").strip()

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty body"
        )

    try:
        save_challenge(agent_aic, token, payload)
        LOGGER.info(f"Set challenge: AIC={agent_aic} Token={token}")
        await publish_runtime_event(
            event_type="challenge.response.saved",
            level="success",
            title="Challenge 响应已写入",
            message=f"AIC {agent_aic} 的 HTTP-01 challenge 响应已写入 challenge-server。",
            aic=str(agent_aic),
            extra={
                "stage": "set-challenge",
                "path": "/acps-atr-v2/{agent_aic}/{token}",
                "token": str(token),
                "bytes": len(body),
            },
        )
        return PlainTextResponse("Challenge set successfully")
    except ChallengeStorageError:
        await publish_runtime_event(
            event_type="challenge.response.save_failed",
            level="error",
            title="Challenge 响应写入失败",
            message=f"AIC {agent_aic} 的 HTTP-01 challenge 写入失败。",
            aic=str(agent_aic),
            extra={
                "stage": "set-challenge",
                "path": "/acps-atr-v2/{agent_aic}/{token}",
                "token": str(token),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save challenge",
        )
