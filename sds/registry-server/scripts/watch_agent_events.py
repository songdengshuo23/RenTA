#!/usr/bin/env python3
"""watch_agent_events.py — 只显示 Agent 注册 + 审核相关事件(注册 agent / 审核 agent)。

不修改源 watch_registry_events.py,直接复用其 _event_line 格式化函数。
两层过滤:
  1. event['type'] 白名单(注册/审核相关)
  2. createdAt/sentAt 时间戳:默认只保留启动后的事件,跳过 SSE 回放的历史

用法:
    cd /home/johnteller/team_ws/sds/registry-server
    python3 scripts/watch_agent_events.py
    python3 scripts/watch_agent_events.py --include-history
    python3 scripts/watch_agent_events.py --since 2026-06-17T17:30:00+08:00
    python3 scripts/watch_agent_events.py --types agent.created,agent.review.completed
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from watch_registry_events import _event_line  # noqa: E402

DEFAULT_ALLOWED_TYPES = {
    "agent.created",
    "agent.submitted",
    "agent.review.completed",
    "agent.passport.issued",
}


def _parse_event_time(event: dict) -> datetime | None:
    raw = event.get("createdAt") or event.get("sentAt")
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def watch_filtered(
    url: str,
    reconnect: bool,
    allowed_types: set[str],
    since: datetime | None = None,
) -> None:
    since_label = since.isoformat() if since else "(include history)"
    skipped = 0
    while True:
        try:
            req = Request(url, headers={"Accept": "text/event-stream"})
            with urlopen(req, timeout=None) as response:
                print(
                    f"connected: {url} (filter: {', '.join(sorted(allowed_types))}; since: {since_label})",
                    flush=True,
                )
                event_name = ""
                for raw in response:
                    line = raw.decode("utf-8", errors="replace").rstrip("\n")
                    if not line:
                        continue
                    if line.startswith(":"):
                        continue
                    if line.startswith("event:"):
                        event_name = line.split(":", 1)[1].strip()
                        continue
                    if line.startswith("data:"):
                        payload = line.split(":", 1)[1].strip()
                        try:
                            event = json.loads(payload)
                        except json.JSONDecodeError:
                            continue
                        if event.get("type") not in allowed_types:
                            continue
                        if since is not None:
                            event_time = _parse_event_time(event)
                            if event_time is not None and event_time < since:
                                skipped += 1
                                continue
                        print(_event_line(event), flush=True)
        except KeyboardInterrupt:
            print(f"stopped (skipped {skipped} historical event(s))", flush=True)
            return
        except URLError as exc:
            print(f"connection failed: {exc}", file=sys.stderr, flush=True)
        except Exception as exc:
            print(f"watch error: {exc}", file=sys.stderr, flush=True)
        if not reconnect:
            print(f"stopped (skipped {skipped} historical event(s))", flush=True)
            return
        time.sleep(2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Watch ONLY agent register/review events (filtered SSE).")
    parser.add_argument(
        "--url",
        default="http://10.126.126.8:8888/api/events/stream",
        help="SSE stream URL (默认走平台代理 8888,也可用 http://127.0.0.1:8001/api/events/stream 直连 registry)",
    )
    parser.add_argument("--no-reconnect", action="store_true", help="断流后退出,不自动重连")
    parser.add_argument(
        "--types",
        default=",".join(sorted(DEFAULT_ALLOWED_TYPES)),
        help=f"逗号分隔的事件 type 白名单(默认: {','.join(sorted(DEFAULT_ALLOWED_TYPES))})",
    )
    parser.add_argument("--show-default", action="store_true", help="显示默认白名单并退出")
    parser.add_argument(
        "--include-history",
        action="store_true",
        help="包含历史事件(SSE 回放缓冲,默认会跳过启动前的所有事件)",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="仅显示该 ISO 时间之后的事件(如 2026-06-17T17:30:00+08:00)。不指定 = 当前时间(跳过历史)",
    )
    args = parser.parse_args()

    if args.show_default:
        print("\n".join(sorted(DEFAULT_ALLOWED_TYPES)))
        return

    allowed = {t.strip() for t in args.types.split(",") if t.strip()}
    if not allowed:
        print("错误:--types 不能为空(用 --show-default 查看默认)", file=sys.stderr)
        sys.exit(1)

    if args.include_history and not args.since:
        since = None
    else:
        if args.since:
            try:
                since_raw = args.since.replace("Z", "+00:00")
                since = datetime.fromisoformat(since_raw)
                if since.tzinfo is None:
                    since = since.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError) as exc:
                print(f"错误:--since 格式无效(需 ISO 时间):{exc}", file=sys.stderr)
                sys.exit(1)
        else:
            since = datetime.now().astimezone()

    watch_filtered(args.url, reconnect=not args.no_reconnect, allowed_types=allowed, since=since)


if __name__ == "__main__":
    main()
