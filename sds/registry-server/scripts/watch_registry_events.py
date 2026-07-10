#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from urllib.error import URLError
from urllib.request import Request, urlopen


def _event_line(event: dict) -> str:
    agent = event.get("agent") or {}
    review = event.get("review") or {}
    passport = event.get("passport") or {}
    extra = event.get("extra") or {}
    created_at = event.get("createdAt") or datetime.now().astimezone().isoformat()
    parts = [
        created_at.replace("T", " ")[:19],
        event.get("source") or "-",
        event.get("type") or "-",
        event.get("level") or "-",
        event.get("title") or "-",
    ]
    if extra.get("service"):
        parts.append(f"service={extra.get('service')}")
    if extra.get("stage"):
        parts.append(f"stage={extra.get('stage')}")
    if extra.get("path"):
        parts.append(f"path={extra.get('path')}")
    if extra.get("statusCode") or extra.get("status_code"):
        parts.append(f"code={extra.get('statusCode') or extra.get('status_code')}")
    if extra.get("durationMs") is not None:
        parts.append(f"durationMs={extra.get('durationMs')}")
    if extra.get("route"):
        parts.append(f"route={extra.get('route')}")
    if extra.get("role"):
        parts.append(f"role={extra.get('role')}")
    if extra.get("query"):
        parts.append(f"query={extra.get('query')}")
    if agent.get("name"):
        parts.append(f"agent={agent.get('name')}")
    if agent.get("approvalStatus"):
        parts.append(f"status={agent.get('approvalStatus')}")
    decision = review.get("decision") or passport.get("decision")
    if decision:
        parts.append(f"decision={decision}")
    if passport.get("status"):
        parts.append(f"passport={passport.get('status')}")
    if review.get("riskLevel") or passport.get("riskLevel"):
        parts.append(f"risk={review.get('riskLevel') or passport.get('riskLevel')}")
    if review.get("permissionTier") or passport.get("permissionTier"):
        parts.append(f"tier={review.get('permissionTier') or passport.get('permissionTier')}")
    if agent.get("aic"):
        parts.append(f"aic={agent.get('aic')}")
    message = event.get("message")
    if message:
        parts.append(f"msg={message}")
    return " | ".join(parts)


def watch(url: str, reconnect: bool) -> None:
    while True:
        try:
            req = Request(url, headers={"Accept": "text/event-stream"})
            with urlopen(req, timeout=None) as response:
                print(f"connected: {url}", flush=True)
                event_name = ""
                for raw in response:
                    line = raw.decode("utf-8", errors="replace").rstrip("\n")
                    if not line:
                        continue
                    if line.startswith(":"):
                        print(line, flush=True)
                        continue
                    if line.startswith("event:"):
                        event_name = line.split(":", 1)[1].strip()
                        continue
                    if line.startswith("data:"):
                        payload = line.split(":", 1)[1].strip()
                        try:
                            event = json.loads(payload)
                        except json.JSONDecodeError:
                            print(f"{event_name or 'message'} | raw={payload}", flush=True)
                            continue
                        print(_event_line(event), flush=True)
        except KeyboardInterrupt:
            print("stopped", flush=True)
            return
        except URLError as exc:
            print(f"connection failed: {exc}", file=sys.stderr, flush=True)
        except Exception as exc:
            print(f"watch error: {exc}", file=sys.stderr, flush=True)
        if not reconnect:
            return
        time.sleep(2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch Registry runtime events in terminal.")
    parser.add_argument(
        "--url",
        default="http://10.126.126.8:8888/api/events/stream",
        help="SSE stream URL. Defaults to the platform proxy; use http://127.0.0.1:8001/api/events/stream to bypass it on the server.",
    )
    parser.add_argument("--no-reconnect", action="store_true", help="Exit when the stream disconnects.")
    args = parser.parse_args()
    watch(args.url, reconnect=not args.no_reconnect)


if __name__ == "__main__":
    main()
