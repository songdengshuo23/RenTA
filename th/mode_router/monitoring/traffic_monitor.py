from __future__ import annotations

import json
import threading
import time
from collections import deque
from typing import Any


def count_tokens(text: str) -> int:
    """Return an approximate token count for agent-to-agent payload text."""
    try:
        import tiktoken
    except ImportError:
        compact = text.replace(" ", "")
        return max(1, len(compact) * 2 // 7 + len(text.split()))

    encoder = getattr(count_tokens, "_encoder", None)
    if encoder is None:
        encoder = tiktoken.get_encoding("cl100k_base")
        count_tokens._encoder = encoder
    return len(encoder.encode(text))


def serialize_payload(payload: Any) -> str:
    """Serialize an arbitrary message payload for consistent token counting."""
    if isinstance(payload, str):
        return payload
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(exclude_none=True)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


class TrafficMonitor:
    """Thread-safe sliding-window monitor for inter-agent payload tokens."""

    def __init__(self, window_seconds: int = 60) -> None:
        self._window = max(1, int(window_seconds))
        self._lock = threading.Lock()
        self._buckets: list[dict[str, int]] = [{} for _ in range(self._window)]
        self._bucket_seconds: list[int | None] = [None for _ in range(self._window)]
        self._start_time = time.time()
        self._records_total = 0
        self._tokens_total = 0
        self._cumulative_edges: dict[str, dict[str, int]] = {}
        self._cumulative_senders: dict[str, int] = {}
        self._cumulative_receivers: dict[str, int] = {}
        self._cumulative_edge_types: dict[str, dict[str, int]] = {}
        self._cumulative_sessions: dict[str, dict[str, int]] = {}
        self._cumulative_executions: dict[str, dict[str, int]] = {}
        self._cumulative_modes: dict[str, dict[str, int]] = {}
        self._last_events: deque[dict[str, Any]] = deque(maxlen=50)

    def record(self, source: str, target: str, tokens: int, **metadata: Any) -> None:
        if tokens <= 0:
            return
        source = str(source or "unknown")
        target = str(target or "unknown")
        now = time.time()
        now_second = int(now)
        edge = f"{source}->{target}"
        edge_type = str(metadata.get("edge_type") or "unknown")
        session_id = str(metadata.get("session_id") or "")
        execution_id = str(metadata.get("execution_id") or "")
        route_mode = str(metadata.get("route_mode") or metadata.get("mode") or "unknown")
        with self._lock:
            idx = now_second % self._window
            if self._bucket_seconds[idx] != now_second:
                self._buckets[idx] = {}
                self._bucket_seconds[idx] = now_second

            bucket = self._buckets[idx]
            bucket[edge] = bucket.get(edge, 0) + tokens
            bucket[f"_edge_count:{edge}"] = bucket.get(f"_edge_count:{edge}", 0) + 1
            bucket["_global"] = bucket.get("_global", 0) + tokens
            bucket["_message_count"] = bucket.get("_message_count", 0) + 1
            bucket[f"_src:{source}"] = bucket.get(f"_src:{source}", 0) + tokens
            bucket[f"_dst:{target}"] = bucket.get(f"_dst:{target}", 0) + tokens

            self._records_total += 1
            self._tokens_total += tokens

            edge_stats = self._cumulative_edges.setdefault(edge, {"tokens_total": 0, "messages_total": 0})
            edge_stats["tokens_total"] += tokens
            edge_stats["messages_total"] += 1
            self._cumulative_senders[source] = self._cumulative_senders.get(source, 0) + tokens
            self._cumulative_receivers[target] = self._cumulative_receivers.get(target, 0) + tokens
            type_stats = self._cumulative_edge_types.setdefault(edge_type, {"tokens_total": 0, "messages_total": 0})
            type_stats["tokens_total"] += tokens
            type_stats["messages_total"] += 1
            if session_id:
                session_stats = self._cumulative_sessions.setdefault(session_id, {"tokens_total": 0, "messages_total": 0})
                session_stats["tokens_total"] += tokens
                session_stats["messages_total"] += 1
            if execution_id:
                execution_stats = self._cumulative_executions.setdefault(execution_id, {"tokens_total": 0, "messages_total": 0})
                execution_stats["tokens_total"] += tokens
                execution_stats["messages_total"] += 1
            mode_stats = self._cumulative_modes.setdefault(route_mode, {"tokens_total": 0, "messages_total": 0})
            mode_stats["tokens_total"] += tokens
            mode_stats["messages_total"] += 1

            event = {
                "time": now,
                "source": source,
                "target": target,
                "tokens": tokens,
            }
            event.update({k: v for k, v in metadata.items() if v not in (None, "")})
            self._last_events.append(event)

    def get_snapshot(self) -> dict[str, Any]:
        now = time.time()
        merged: dict[str, int] = {}
        with self._lock:
            for second, bucket in zip(self._bucket_seconds, self._buckets):
                if second is None or now - second >= self._window:
                    continue
                for key, val in bucket.items():
                    merged[key] = merged.get(key, 0) + val

            elapsed = min(max(now - self._start_time, 1.0), float(self._window))
            global_total = merged.get("_global", 0)
            message_count = merged.get("_message_count", 0)

            edges: list[dict[str, Any]] = []
            for key, total in merged.items():
                if key.startswith("_") or "->" not in key:
                    continue
                source, target = key.split("->", 1)
                edge_count = merged.get(f"_edge_count:{key}", 0)
                edges.append(
                    {
                        "from": source,
                        "to": target,
                        "tokens_total": total,
                        "messages_total": edge_count,
                        "tps": round(total / elapsed, 1),
                    }
                )
            edges.sort(key=lambda item: item["tokens_total"], reverse=True)

            senders = [
                {"agent": key[5:], "tokens_total": val, "tps": round(val / elapsed, 1)}
                for key, val in merged.items()
                if key.startswith("_src:")
            ]
            senders.sort(key=lambda item: item["tokens_total"], reverse=True)

            receivers = [
                {"agent": key[5:], "tokens_total": val, "tps": round(val / elapsed, 1)}
                for key, val in merged.items()
                if key.startswith("_dst:")
            ]
            receivers.sort(key=lambda item: item["tokens_total"], reverse=True)

            last_events = list(self._last_events)
            uptime_seconds = max(now - self._start_time, 1.0)
            cumulative_edges = [
                {
                    "from": key.split("->", 1)[0],
                    "to": key.split("->", 1)[1],
                    "tokens_total": stats["tokens_total"],
                    "messages_total": stats["messages_total"],
                    "tps_since_start": round(stats["tokens_total"] / uptime_seconds, 1),
                    "average_tokens_per_message": round(stats["tokens_total"] / max(stats["messages_total"], 1), 1),
                }
                for key, stats in self._cumulative_edges.items()
            ]
            cumulative_edges.sort(key=lambda item: item["tokens_total"], reverse=True)
            cumulative_senders = [
                {"agent": agent, "tokens_total": tokens, "tps_since_start": round(tokens / uptime_seconds, 1)}
                for agent, tokens in self._cumulative_senders.items()
            ]
            cumulative_senders.sort(key=lambda item: item["tokens_total"], reverse=True)
            cumulative_receivers = [
                {"agent": agent, "tokens_total": tokens, "tps_since_start": round(tokens / uptime_seconds, 1)}
                for agent, tokens in self._cumulative_receivers.items()
            ]
            cumulative_receivers.sort(key=lambda item: item["tokens_total"], reverse=True)
            cumulative_edge_types = [
                {
                    "edge_type": edge_type,
                    "tokens_total": stats["tokens_total"],
                    "messages_total": stats["messages_total"],
                    "average_tokens_per_message": round(stats["tokens_total"] / max(stats["messages_total"], 1), 1),
                }
                for edge_type, stats in self._cumulative_edge_types.items()
            ]
            cumulative_edge_types.sort(key=lambda item: item["tokens_total"], reverse=True)
            cumulative_sessions = [
                {"session_id": session_id, **stats}
                for session_id, stats in self._cumulative_sessions.items()
            ]
            cumulative_sessions.sort(key=lambda item: item["tokens_total"], reverse=True)
            cumulative_executions = [
                {"execution_id": execution_id, **stats}
                for execution_id, stats in self._cumulative_executions.items()
            ]
            cumulative_executions.sort(key=lambda item: item["tokens_total"], reverse=True)
            cumulative_modes = [
                {"mode": mode, **stats}
                for mode, stats in self._cumulative_modes.items()
            ]
            cumulative_modes.sort(key=lambda item: item["tokens_total"], reverse=True)

        return {
            "enabled": True,
            "global_tps": round(global_total / elapsed, 1),
            "global_tokens_total": global_total,
            "messages_total": message_count,
            "window_seconds": self._window,
            "elapsed_seconds": round(elapsed, 1),
            "records_total_since_reset": self._records_total,
            "tokens_total_since_reset": self._tokens_total,
            "edges": edges[:20],
            "top_senders": senders[:10],
            "top_receivers": receivers[:10],
            "platform_mode2_group_chat": {
                "scope": "all_mode2_tasks_since_process_start",
                "tokens_total": self._tokens_total,
                "messages_total": self._records_total,
                "uptime_seconds": round(uptime_seconds, 1),
                "tps_since_start": round(self._tokens_total / uptime_seconds, 1),
                "modes": cumulative_modes,
                "edges": cumulative_edges[:50],
                "edge_types": cumulative_edge_types,
                "top_senders": cumulative_senders[:20],
                "top_receivers": cumulative_receivers[:20],
                "sessions": cumulative_sessions[:20],
                "executions": cumulative_executions[:20],
            },
            "last_events": last_events[-20:],
        }

    def reset(self) -> None:
        with self._lock:
            self._buckets = [{} for _ in range(self._window)]
            self._bucket_seconds = [None for _ in range(self._window)]
            self._start_time = time.time()
            self._records_total = 0
            self._tokens_total = 0
            self._cumulative_edges.clear()
            self._cumulative_senders.clear()
            self._cumulative_receivers.clear()
            self._cumulative_edge_types.clear()
            self._cumulative_sessions.clear()
            self._cumulative_executions.clear()
            self._cumulative_modes.clear()
            self._last_events.clear()


_monitor: TrafficMonitor | None = None
_monitor_lock = threading.Lock()


def _get_monitor() -> TrafficMonitor:
    global _monitor
    if _monitor is None:
        with _monitor_lock:
            if _monitor is None:
                _monitor = TrafficMonitor()
    return _monitor


def record(source: str, target: str, tokens: int, **metadata: Any) -> None:
    _get_monitor().record(source, target, tokens, **metadata)


def get_snapshot() -> dict[str, Any]:
    return _get_monitor().get_snapshot()


def reset() -> None:
    _get_monitor().reset()
