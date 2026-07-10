#!/usr/bin/env python3
"""Read-only smoke checks for the pre-upgrade RenTA service stack."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Check:
    name: str
    port: int
    path: str
    expected_status: int = 200
    content: str = "json"
    marker: str | None = None


CHECKS = (
    Check("gateway-home", 8888, "/", content="text", marker="RenTA"),
    Check("gateway-agent-list", 8888, "/api/agent/public/recent"),
    Check("gateway-acs-example", 8888, "/api/agent/public/acs_example"),
    Check("gateway-events", 8888, "/api/events/recent"),
    Check("gateway-dsp-auth", 8888, "/acps-dsp-v2/info", expected_status=401),
    Check(
        "gateway-passport-auth",
        8888,
        "/acps-atr-v2/passports/discovery",
        expected_status=401,
    ),
    Check("gateway-mode-router", 8888, "/mode-router/health"),
    Check("gateway-direct-rpc", 8888, "/agent-rpc/health"),
    Check("registry-root", 8001, "/"),
    Check("ca-health", 8003, "/health"),
    Check("ca-acme-directory", 8003, "/acps-atr-v2/acme/directory"),
    Check(
        "ca-trust-bundle",
        8003,
        "/acps-atr-v2/ca/trust-bundle",
        content="text",
        marker="BEGIN CERTIFICATE",
    ),
    Check("challenge-health", 8004, "/acps-atr-v2/health"),
    Check("challenge-status", 8004, "/status"),
    Check("group-bridge-health", 8098, "/health"),
    Check("group-proxy-health", 8099, "/health"),
    Check("mode-router-health", 18080, "/health"),
    Check("direct-rpc-health", 19090, "/health"),
)


def request(check: Check, host: str, timeout: float) -> tuple[int, bytes]:
    url = f"http://{host}:{check.port}{check.path}"
    req = Request(url, headers={"User-Agent": "RenTA-stage0-smoke/1.0"})
    try:
        with urlopen(req, timeout=timeout) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()


def validate(check: Check, status: int, body: bytes) -> str | None:
    if status != check.expected_status:
        return f"expected HTTP {check.expected_status}, got {status}"
    if not body:
        return "empty response body"
    if check.content == "json":
        try:
            json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return f"invalid JSON: {exc}"
    if check.marker and check.marker.encode("utf-8") not in body:
        return f"missing marker {check.marker!r}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args()

    failures = []
    for check in CHECKS:
        url = f"http://{args.host}:{check.port}{check.path}"
        try:
            status, body = request(check, args.host, args.timeout)
            error = validate(check, status, body)
        except (URLError, TimeoutError, OSError) as exc:
            status, body, error = 0, b"", f"{type(exc).__name__}: {exc}"

        if error:
            failures.append((check.name, error))
            print(f"FAIL {check.name:24} {url} - {error}")
        else:
            print(f"PASS {check.name:24} HTTP {status} ({len(body)} bytes)")

    print(f"\n{len(CHECKS) - len(failures)}/{len(CHECKS)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
