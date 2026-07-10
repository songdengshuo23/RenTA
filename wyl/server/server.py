"""
wyl Frontend Server (static + reverse proxy)
============================================
"""
import argparse
import json
import os
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
import urllib.request
import urllib.error

HERE = Path(__file__).resolve().parent
DIST = HERE.parent / "frontend"
INDEX_HTML = DIST / "index.html"


def _proxy_timeout_seconds():
    raw = os.getenv("WYL_PROXY_TIMEOUT_SECONDS", "0").strip().lower()
    if raw in {"", "0", "none", "null", "unlimited", "infinite", "inf", "false"}:
        return None
    return max(1.0, float(raw))


PROXY_TIMEOUT_SECONDS = _proxy_timeout_seconds()

REGISTRY_UPSTREAM = os.getenv("WYL_REGISTRY_UPSTREAM", "http://localhost:8001/")
CA_UPSTREAM = os.getenv("WYL_CA_UPSTREAM", "http://localhost:8003/")

CA_PREFIXES = (
    "/acps-atr-v2/acme",
    "/acps-atr-v2/ca",
    "/acps-atr-v2/crl",
    "/acps-atr-v2/ocsp",
)


def build_proxies(registry_upstream=REGISTRY_UPSTREAM, ca_upstream=CA_UPSTREAM):
    return [
        *((prefix, ca_upstream, False) for prefix in CA_PREFIXES),
        ("/api/",           registry_upstream,          False),
        ("/mode-router/",   "http://localhost:18080/", True),
        ("/agent-rpc/",     "http://localhost:19090/", True),
        ("/acps-atr-v2/",   registry_upstream,          False),
        ("/acps-dsp-v2/",   registry_upstream,          False),
        ("/acps-adp-v2/",   "http://localhost:8005/",  False),
        ("/acps-atr-v1/",   registry_upstream,          True),
    ]


PROXIES = build_proxies()


def _env_bool(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def frontend_config():
    return {
        "acpsV21FrontendEnabled": _env_bool("ACPS_FRONTEND_V21_ENABLED"),
        "eabIssuanceEnabled": _env_bool("ACPS_FRONTEND_EAB_ENABLED"),
        "caDirectoryUrl": "/acps-atr-v2/acme/directory",
    }


def is_ca_proxy_path(path):
    return any(path == prefix or path.startswith(prefix + "/") for prefix in CA_PREFIXES)


def proxy_for_path(path):
    for prefix, upstream, strip_prefix in PROXIES:
        matches = path.startswith(prefix) if prefix.endswith("/") else path == prefix or path.startswith(prefix + "/")
        if matches:
            return prefix, upstream, strip_prefix
    return None


def external_origin(headers):
    forwarded_proto = (headers.get("X-Forwarded-Proto") or "").split(",", 1)[0].strip().lower()
    scheme = forwarded_proto if forwarded_proto in {"http", "https"} else "http"
    host = (headers.get("X-Forwarded-Host") or headers.get("Host") or "").split(",", 1)[0].strip()
    return f"{scheme}://{host}" if host else ""


def rewrite_ca_url(value, public_origin):
    if not value or not public_origin:
        return value
    ca_url = urlparse(CA_UPSTREAM)
    internal_origins = {
        f"{ca_url.scheme}://{ca_url.netloc}",
        "http://localhost:8003",
        "http://127.0.0.1:8003",
    }
    rewritten = value
    for origin in internal_origins:
        rewritten = rewritten.replace(origin, public_origin)
    return rewritten


def rewrite_ca_body(body, content_type, public_origin):
    if not body or "json" not in (content_type or "").lower():
        return body
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return body
    return rewrite_ca_url(text, public_origin).encode("utf-8")


class SPAProxyHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS, PATCH")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def _serve_config(self):
        data = json.dumps(frontend_config(), separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _relay_response(self, response, status, ca_route):
        response_headers = response.headers or {}
        content_type = response_headers.get("Content-Type") or ""
        if not ca_route and "text/event-stream" in content_type.lower():
            self.send_response(status)
            for key, value in response_headers.items():
                if key.lower() in ("transfer-encoding", "connection"):
                    continue
                self.send_header(key, value)
            self.end_headers()
            while True:
                chunk = response.readline()
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
            return

        body = response.read()
        public_origin = external_origin(self.headers) if ca_route else ""
        if ca_route:
            body = rewrite_ca_body(body, content_type, public_origin)

        self.send_response(status)
        for key, value in response_headers.items():
            lower = key.lower()
            if lower in ("transfer-encoding", "connection"):
                continue
            if ca_route and lower == "content-length":
                continue
            if ca_route and lower == "location":
                value = rewrite_ca_url(value, public_origin)
            self.send_header(key, value)
        if ca_route:
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self, method):
        path = urlparse(self.path).path
        route = proxy_for_path(path)
        if not route:
            sys.stderr.write(f"[wyl] no upstream for path={path!r}\n")
            sys.stderr.flush()
            self.send_error(404, "no upstream for path")
            return
        prefix, upstream, strip_prefix = route
        ca_route = is_ca_proxy_path(path)
        if strip_prefix:
            forward_path = path[len(prefix):]  # starts with /
        else:
            forward_path = path  # starts with /
        # Normalize: ensure exactly one slash between upstream and forward_path
        # (upstream ends with /, forward_path starts with /)
        if upstream.endswith('/') and forward_path.startswith('/'):
            target = upstream + forward_path[1:]
        elif upstream.endswith('/') or forward_path.startswith('/'):
            target = upstream + forward_path
        else:
            target = upstream + '/' + forward_path
        if urlparse(self.path).query:
            target += "?" + urlparse(self.path).query
        sys.stderr.write(f"[wyl] proxy method={method} path={path} target={target}\n")
        sys.stderr.flush()
        content_length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(content_length) if content_length > 0 else None
        headers = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length")}
        if ca_route:
            host = self.headers.get("Host")
            if host:
                headers["Host"] = host
                headers.setdefault("X-Forwarded-Host", host)
            headers.setdefault("X-Forwarded-Proto", external_origin(self.headers).split(":", 1)[0] or "http")
        req = urllib.request.Request(target, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=PROXY_TIMEOUT_SECONDS) as resp:
                self._relay_response(resp, resp.status, ca_route)
        except urllib.error.HTTPError as e:
            try:
                self._relay_response(e, e.code, ca_route)
            except (BrokenPipeError, ConnectionResetError):
                pass
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            try:
                self.send_error(502, f"proxy error: {e}")
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_GET(self): self._route("GET")
    def do_POST(self): self._route("POST")
    def do_PUT(self): self._route("PUT")
    def do_DELETE(self): self._route("DELETE")
    def do_PATCH(self): self._route("PATCH")

    def _route(self, method):
        path = urlparse(self.path).path
        if path == "/renta-config":
            return self._serve_config()
        if proxy_for_path(path):
            return self._proxy(method)
        fs_path = (DIST / path.lstrip("/")).resolve()
        try:
            fs_path.relative_to(DIST.resolve())
        except ValueError:
            self.send_error(403); return
        if fs_path.is_file():
            return self._serve_file(fs_path)
        if INDEX_HTML.is_file():
            return self._serve_file(INDEX_HTML)
        self.send_error(404, "index.html missing")

    def _serve_file(self, path):
        ctype = self.guess_type(str(path))
        try:
            data = path.read_bytes()
        except OSError:
            self.send_error(404); return
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8888)
    args = p.parse_args()

    if not DIST.is_dir():
        print(f"ERR: {DIST} not found", file=sys.stderr)
        sys.exit(1)

    print(f"serving {DIST}")
    print(f"proxies: {[p for p, _, _ in PROXIES]}")
    httpd = ThreadingHTTPServer((args.host, args.port), SPAProxyHandler)
    httpd.daemon_threads = True
    print(f"wyl frontend server on http://{args.host}:{args.port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
