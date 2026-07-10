"""
wyl Frontend Server (static + reverse proxy)
============================================
"""
import argparse
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

PROXIES = [
    ("/api/",           "http://localhost:8001/",  False),
    ("/mode-router/",   "http://localhost:18080/", True),
    ("/agent-rpc/",     "http://localhost:19090/", True),
    ("/acps-atr-v2/",   "http://localhost:8001/",  False),
    ("/acps-dsp-v2/",   "http://localhost:8001/",  False),
    ("/acps-adp-v2/",   "http://localhost:8005/",  False),
    ("/acps-atr-v1/",   "http://localhost:8001/",  True),
]


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

    def _proxy(self, method):
        path = urlparse(self.path).path
        upstream = None
        prefix = None
        strip_prefix = False
        for pfx, base, strip in PROXIES:
            if path.startswith(pfx):
                upstream = base
                prefix = pfx
                strip_prefix = strip
                break
        if not upstream:
            sys.stderr.write(f"[wyl] no upstream for path={path!r}\n")
            sys.stderr.flush()
            self.send_error(404, "no upstream for path")
            return
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
        req = urllib.request.Request(target, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=PROXY_TIMEOUT_SECONDS) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in ("transfer-encoding", "connection"):
                        continue
                    self.send_header(k, v)
                self.end_headers()
                content_type = (resp.headers.get("Content-Type") or "").lower()
                if "text/event-stream" in content_type:
                    while True:
                        chunk = resp.readline()
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                else:
                    self.wfile.write(resp.read())
        except urllib.error.HTTPError as e:
            try:
                self.send_response(e.code)
                for k, v in (e.headers or {}).items():
                    if k.lower() in ("transfer-encoding", "connection"):
                        continue
                    self.send_header(k, v)
                self.end_headers()
                eb = e.read() if e.fp else b""
                self.wfile.write(eb)
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
        if any(path.startswith(p) for p, _, _ in PROXIES):
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
