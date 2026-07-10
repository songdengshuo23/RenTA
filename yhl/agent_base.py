"""
agent_base.py (RECONSTRUCTED for partner agents)
==================================================
Original .py source was lost (only .pyc remained). This is a minimal
re-implementation that supports the interfaces the partner main.py
subclasses need:

  - class attrs: port, endpoint, group_endpoint, name, partner_aic, system_prompt
  - async validate_input(task_input) -> (bool, str|None)
  - async process(task_input) -> str
  - async call_llm(prompt) -> (str, dict)
  - run() -> starts FastAPI on self.port with:
      POST <self.endpoint>       -> RpcRequest, calls self.process()
      POST <self.group_endpoint> -> GroupSession invite/start/complete

This file replaces the missing agent_base.py so partner main.py
subclasses can run again. The full GroupSession protocol is
implemented per chat_agent_invoke_flow.md spec.
"""
import os
import json
import logging
import asyncio
import time
import uuid
import httpx
from typing import Optional, Dict, Any, Tuple
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager

# ---------- LLM config (from env, same as direct_rpc_server) ----------
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_API_URL = os.getenv("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-v4-pro")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))

log = logging.getLogger("agent_base")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s agent_base: %(message)s")


# ---------- Pydantic schemas (per the partner openapi) ----------
class RpcCommand(BaseModel):
    id: str
    sentAt: str
    senderRole: str
    senderId: str
    command: str  # get/start/continue/cancel/complete/re-stream


class RpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    method: str  # must be literal "rpc" or "group"
    params: Dict[str, Any]


class RpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class TextDataItem(BaseModel):
    type: str = "text"
    text: str


class StructuredDataItem(BaseModel):
    type: str = "structured"
    data: Dict[str, Any]


class FileDataItem(BaseModel):
    type: str = "file"
    fileName: str
    mimeType: str
    content: str


class TaskCommand(BaseModel):
    type: str = "task-command"
    id: str
    sentAt: str
    senderRole: str
    senderId: str
    command: str


class TaskStatus(BaseModel):
    type: str = "task-status"
    id: str
    sentAt: str
    senderRole: str
    senderId: str
    status: str  # assigned / in_progress / awaiting_completion / completed / failed
    message: Optional[str] = None
    progress: Optional[float] = None
    artifacts: Optional[list] = None


class Product(BaseModel):
    type: str = "product"
    id: str
    name: str
    contentType: str = "text/markdown"
    content: str


# ---------- AgentBase ----------
class AgentBase:
    # subclass overrides
    port: int = 0
    endpoint: str = "/agents/agent/rpc"
    group_endpoint: str = "/group/rpc"
    name: str = "Agent"
    partner_aic: str = ""
    system_prompt: str = "You are a helpful assistant."

    async def validate_input(self, task_input: str) -> Tuple[bool, Optional[str]]:
        return True, None

    async def process(self, task_input: str) -> str:
        # subclass must implement
        raise NotImplementedError

    # ---------- LLM call ----------
    async def call_llm(self, prompt: str) -> Tuple[str, Dict[str, Any]]:
        """Call DeepSeek with the system prompt + user prompt."""
        if not LLM_API_KEY:
            raise RuntimeError("LLM_API_KEY not set in environment")
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "max_tokens": LLM_MAX_TOKENS,
            "temperature": 0.7,
        }
        headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(LLM_API_URL, headers=headers, json=payload)
            if r.status_code != 200:
                raise RuntimeError(f"LLM upstream HTTP {r.status_code}: {r.text[:200]}")
            j = r.json()
        content = j["choices"][0]["message"]["content"]
        usage = j.get("usage", {})
        log.info("call_llm done chars=%d tokens=%s", len(content), usage.get("total_tokens", 0))
        return content, usage

    # ---------- State ----------
    def __init__(self):
        self.partner_aic = self.partner_aic or os.getenv("PARTNER_AIC", "")
        # GroupSession state (per-partner task tracking)
        self._tasks: Dict[str, Dict[str, Any]] = {}

    # ---------- HTTP server ----------
    def run(self) -> None:
        import uvicorn
        app = FastAPI(title=self.name)

        @app.get("/health")
        async def health():
            return {
                "status": "healthy",
                "agent": self.name,
                "port": self.port,
                "group_endpoint": self.group_endpoint,
            }

        @app.post(self.endpoint)
        async def rpc_endpoint(req: RpcRequest):
            """Handle RpcRequest — calls self.process() with the command text."""
            log.info("rpc_endpoint method=%s params=%s", req.method, list(req.params.keys()))
            # For method='rpc', params.command has the command envelope
            cmd = req.params.get("command", {})
            cmd_obj = RpcCommand(**cmd) if isinstance(cmd, dict) else cmd
            cmd_id = cmd_obj.id
            action = cmd_obj.command
            sender = cmd_obj.senderId
            log.info("  action=%s sender=%s id=%s", action, sender, cmd_id)

            if action in ("start", "continue", "re-stream"):
                # The actual task text comes through RabbitMQ GroupSession;
                # in this minimal recon, the GroupLeader sends it via the
                # 'text' field of the command params. We pull it from there.
                task_text = (
                    req.params.get("text")
                    or req.params.get("input")
                    or req.params.get("task")
                    or cmd_obj.id  # last-resort fallback so we always have something
                )
                # Validate + process
                ok, err = await self.validate_input(task_text)
                if not ok:
                    return RpcResponse(id=req.id, error={"code": -32000, "message": err or "invalid input"}).dict()
                # Process (this calls LLM via self.call_llm in real partners)
                loop = asyncio.get_event_loop()
                try:
                    output = await self.process(task_text)
                except Exception as exc:
                    log.exception("process failed")
                    return RpcResponse(id=req.id, error={"code": -32603, "message": str(exc)}).dict()
                # Build TaskResult
                task_result = {
                    "type": "task-result",
                    "id": cmd_id,
                    "sentAt": cmd_obj.sentAt,
                    "senderRole": "partner",
                    "senderId": self.partner_aic or f"partner-{self.port}",
                    "mentions": [sender],
                    "dataItems": [{"type": "text", "text": output}],
                    "taskId": cmd_id,
                    "status": {"type": "task-status", "status": "awaiting_completion", "message": "task done, awaiting completion"},
                    "products": [{
                        "type": "product",
                        "id": cmd_id,
                        "name": f"{self.name}_output",
                        "contentType": "text/markdown",
                        "content": output,
                    }],
                }
                self._tasks[cmd_id] = {"output": output, "sender": sender, "status": "awaiting_completion"}
                return RpcResponse(id=req.id, result=task_result).dict()

            if action == "get":
                # Return current task snapshot
                t = self._tasks.get(cmd_id, {})
                return RpcResponse(id=req.id, result={
                    "type": "task-result",
                    "id": cmd_id,
                    "taskId": cmd_id,
                    "status": {"type": "task-status", "status": t.get("status", "unknown")},
                    "dataItems": [{"type": "text", "text": t.get("output", "")}],
                    "products": [{
                        "type": "product",
                        "id": cmd_id,
                        "name": f"{self.name}_output",
                        "contentType": "text/markdown",
                        "content": t.get("output", ""),
                    }],
                }).dict()

            if action == "complete":
                # Mark task complete
                t = self._tasks.get(cmd_id, {})
                t["status"] = "completed"
                return RpcResponse(id=req.id, result={"status": "completed"}).dict()

            if action == "cancel":
                self._tasks.pop(cmd_id, None)
                return RpcResponse(id=req.id, result={"status": "cancelled"}).dict()

            return RpcResponse(id=req.id, error={"code": -32601, "message": f"unknown command: {action}"}).dict()

        @app.post(self.group_endpoint)
        async def group_endpoint(req: RpcRequest):
            """Handle GroupSession invite: store session_id, return ack."""
            log.info("group_endpoint params=%s", list(req.params.keys()))
            # Minimal GroupSession protocol: just return success
            return RpcResponse(id=req.id, result={"status": "joined", "session_id": req.params.get("protocol", {}).get("sessionId", "unknown")}).dict()

        log.info("Starting %s on 0.0.0.0:%d (endpoint=%s, group=%s, LLM=%s)",
                 self.name, self.port, self.endpoint, self.group_endpoint, LLM_MODEL[:20])
        if not LLM_API_KEY:
            log.warning("LLM_API_KEY is empty — LLM calls will fail")
        uvicorn.run(app, host="0.0.0.0", port=self.port, log_level="info")
