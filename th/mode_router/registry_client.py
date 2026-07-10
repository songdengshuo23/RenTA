from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping


class RegistryCallError(RuntimeError):
    pass


def _registry_endpoint(registry_url: str, path: str) -> str:
    base = registry_url.rstrip("/")
    if base.endswith(path):
        return base
    return f"{base}/{path}"


def _atr_registry_endpoint(registry_url: str, path: str) -> str:
    base = registry_url.rstrip("/")
    if base.endswith("/acps-atr-v2") or "/acps-atr-v2/" in base:
        return _registry_endpoint(base, path)
    return _registry_endpoint(f"{base}/acps-atr-v2", path)


def _request_json_with_atr_fallback(
    method: str,
    registry_url: str,
    path: str,
    payload: Mapping[str, Any] | None = None,
    *,
    auth_token: str = "",
    timeout: float = 120.0,
    retries: int = 1,
    retry_backoff: float = 2.0,
) -> dict[str, Any]:
    endpoint = _registry_endpoint(registry_url, path)
    try:
        return _request_json(method, endpoint, payload, auth_token=auth_token, timeout=timeout, retries=retries, retry_backoff=retry_backoff)
    except RegistryCallError as exc:
        if "HTTP 404" not in str(exc):
            raise
        atr_endpoint = _atr_registry_endpoint(registry_url, path)
        if atr_endpoint == endpoint:
            raise
        return _request_json(method, atr_endpoint, payload, auth_token=auth_token, timeout=timeout, retries=retries, retry_backoff=retry_backoff)


def _append_query(url: str, params: Mapping[str, Any]) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urllib.parse.urlencode(params)}"


def _request_json(
    method: str,
    url: str,
    payload: Mapping[str, Any] | None = None,
    *,
    auth_token: str = "",
    timeout: float = 120.0,
    retries: int = 1,
    retry_backoff: float = 2.0,
) -> dict[str, Any]:
    attempts = max(1, retries + 1)
    last_error = ""

    for attempt in range(1, attempts + 1):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        req = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            last_error = f"HTTP {exc.code}: {body}"
            if exc.code not in {429, 500, 502, 503, 504} or attempt >= attempts:
                raise RegistryCallError(last_error) from exc
        except Exception as exc:
            last_error = str(exc)
            if attempt >= attempts:
                raise RegistryCallError(last_error) from exc

        time.sleep(retry_backoff * attempt)

    raise RegistryCallError(last_error or "unknown registry error")


def call_registry_discovery(
    registry_url: str,
    *,
    limit: int = 25,
    requester_user_id: str = "",
    auth_token: str = "",
    timeout: float = 120.0,
    retries: int = 1,
    retry_backoff: float = 2.0,
) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": limit}
    if requester_user_id:
        params["requesterUserId"] = requester_user_id
    path = f"passports/discovery?{urllib.parse.urlencode(params)}"
    return _request_json_with_atr_fallback("GET", registry_url, path, auth_token=auth_token, timeout=timeout, retries=retries, retry_backoff=retry_backoff)


def call_registry_public_recent(
    registry_url: str,
    *,
    page_num: int = 1,
    page_size: int = 100,
    auth_token: str = "",
    timeout: float = 30.0,
    retries: int = 0,
    retry_backoff: float = 2.0,
) -> dict[str, Any]:
    public_base = registry_url.rstrip("/")
    if public_base.endswith("/acps-atr-v2"):
        public_base = public_base[: -len("/acps-atr-v2")]
    endpoint = _registry_endpoint(public_base, "api/agent/public/recent")
    separator = "&" if "?" in endpoint else "?"
    # The CYF Registry public endpoint accepts `limit`; keep page_num/page_size
    # in the client signature so callers can share pagination-shaped config.
    params = urllib.parse.urlencode({"limit": page_size})
    return _request_json("GET", f"{endpoint}{separator}{params}", auth_token=auth_token, timeout=timeout, retries=retries, retry_backoff=retry_backoff)


def call_registry_dispatch(
    registry_url: str,
    agent_aic: str,
    *,
    requester_user_id: str = "",
    auth_token: str = "",
    timeout: float = 120.0,
    retries: int = 1,
    retry_backoff: float = 2.0,
) -> dict[str, Any]:
    quoted_aic = urllib.parse.quote(agent_aic, safe="")
    path = f"passports/{quoted_aic}/dispatch"
    if requester_user_id:
        path = f"{path}?{urllib.parse.urlencode({'requesterUserId': requester_user_id})}"
    return _request_json_with_atr_fallback("GET", registry_url, path, auth_token=auth_token, timeout=timeout, retries=retries, retry_backoff=retry_backoff)


def call_registry_runtime_review_schedule(
    registry_url: str,
    payload: Mapping[str, Any] | None = None,
    *,
    auth_token: str = "",
    timeout: float = 120.0,
    retries: int = 1,
    retry_backoff: float = 2.0,
) -> dict[str, Any]:
    payload = payload or {}
    path = "passports/runtime-review/schedule"
    params: dict[str, Any] = {}
    if payload.get("limit") is not None:
        params["limit"] = payload.get("limit")
    sync_certificates = payload.get("syncCertificates")
    if sync_certificates is None:
        sync_certificates = payload.get("sync_certificates")
    if sync_certificates is not None:
        params["syncCertificates"] = str(bool(sync_certificates)).lower()
    if params:
        path = f"{path}?{urllib.parse.urlencode(params)}"
    return _request_json_with_atr_fallback("POST", registry_url, path, {}, auth_token=auth_token, timeout=timeout, retries=retries, retry_backoff=retry_backoff)


def call_registry_agent_call_settlement(
    registry_url: str,
    payload: Mapping[str, Any],
    *,
    auth_token: str = "",
    timeout: float = 10.0,
    retries: int = 0,
    retry_backoff: float = 1.0,
) -> dict[str, Any]:
    endpoint = _registry_endpoint(registry_url.rstrip("/"), "api/points/internal/agent-call")
    return _request_json("POST", endpoint, payload, auth_token=auth_token, timeout=timeout, retries=retries, retry_backoff=retry_backoff)
