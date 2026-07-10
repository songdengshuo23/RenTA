"""
Agent 间通信流量监测模块

监控范围：Agent 之间传递的消息内容中的 token 数/秒
注意：此处统计的是 Agent 间消息 payload 的 token 数，
      不是 Agent 内部调用 LLM 的 prompt/completion tokens。

tokens/s 定义：
    最近 60 秒内所有 Agent 间消息 token 总数 / 60 秒

使用方式：
    from monitoring.traffic_monitor import record, get_snapshot

    # 在发送消息前调用
    record(source="planner", target="researcher", tokens=842)

    # 获取当前流量快照（供前端 API 使用）
    snapshot = get_snapshot()
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Token 计数
# ---------------------------------------------------------------------------

def count_tokens(text: str) -> int:
    """计算文本的近似 token 数。

    优先使用 tiktoken (cl100k_base)，不可用时用字符数 / 3.5 估算。
    """
    try:
        import tiktoken
    except ImportError:
        return max(1, len(text.replace(" ", "")) * 2 // 7 + len(text.split()))

    _tik = getattr(count_tokens, "_tik", None)
    if _tik is None:
        _tik = tiktoken.get_encoding("cl100k_base")
        count_tokens._tik = _tik
    return len(_tik.encode(text))


def serialize_payload(payload: Any) -> str:
    """统一序列化消息 payload 为字符串。"""
    if isinstance(payload, str):
        return payload
    if hasattr(payload, "model_dump"):
        return json.dumps(payload.model_dump(exclude_none=True), ensure_ascii=False, sort_keys=True)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


# ---------------------------------------------------------------------------
# 秒级滑动窗口缓冲区
# ---------------------------------------------------------------------------

class TrafficMonitor:
    """线程安全的秒级滑动窗口流量监控器。

    内部用定长列表模拟循环缓冲区，每格存一秒的计数。
    """

    def __init__(self, window_seconds: int = 60):
        self._window = max(1, window_seconds)
        self._lock = threading.Lock()
        self._buckets: List[Dict[str, int]] = [{} for _ in range(self._window)]
        self._start_time = time.time()

    def record(self, source: str, target: str, tokens: int) -> None:
        if tokens <= 0:
            return
        edge = f"{source}→{target}"
        with self._lock:
            idx = int(time.time() - self._start_time) % self._window
            bucket = self._buckets[idx]
            bucket[edge] = bucket.get(edge, 0) + tokens
            bucket["_global"] = bucket.get("_global", 0) + tokens
            bucket[f"_src:{source}"] = bucket.get(f"_src:{source}", 0) + tokens
            bucket[f"_dst:{target}"] = bucket.get(f"_dst:{target}", 0) + tokens

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            merged: Dict[str, int] = {}
            for bucket in self._buckets:
                for key, val in bucket.items():
                    merged[key] = merged.get(key, 0) + val

            elapsed = min(time.time() - self._start_time, self._window)
            seconds = max(elapsed, 1)
            global_total = merged.get("_global", 0)

            edges = []
            for key, total in merged.items():
                if key.startswith("_") or "→" not in key:
                    continue
                src, dst = key.split("→", 1)
                edges.append({"from": src, "to": dst, "tokens_total": total, "tps": round(total / seconds, 1)})
            edges.sort(key=lambda e: e["tokens_total"], reverse=True)

            senders = [
                {"agent": k[5:], "tokens_total": v, "tps": round(v / seconds, 1)}
                for k, v in merged.items() if k.startswith("_src:")
            ]
            senders.sort(key=lambda s: s["tokens_total"], reverse=True)

            receivers = [
                {"agent": k[5:], "tokens_total": v, "tps": round(v / seconds, 1)}
                for k, v in merged.items() if k.startswith("_dst:")
            ]
            receivers.sort(key=lambda r: r["tokens_total"], reverse=True)

        return {
            "global_tps": round(global_total / seconds, 1),
            "global_tokens_total": global_total,
            "window_seconds": int(seconds),
            "edges": edges[:20],
            "top_senders": senders[:10],
            "top_receivers": receivers[:10],
        }

    def reset(self) -> None:
        with self._lock:
            self._buckets = [{} for _ in range(self._window)]
            self._start_time = time.time()


# 全局单例
_monitor: Optional[TrafficMonitor] = None
_mlock = threading.Lock()


def _get_monitor() -> TrafficMonitor:
    global _monitor
    if _monitor is None:
        with _mlock:
            if _monitor is None:
                _monitor = TrafficMonitor(window_seconds=60)
    return _monitor


def record(source: str, target: str, tokens: int) -> None:
    _get_monitor().record(source, target, tokens)


def get_snapshot() -> Dict[str, Any]:
    return _get_monitor().get_snapshot()


def reset() -> None:
    _get_monitor().reset()
