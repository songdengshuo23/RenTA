from __future__ import annotations

import select
import socket
import socketserver
import sys
import threading
from dataclasses import dataclass

import paramiko


@dataclass(frozen=True)
class TunnelSpec:
    local_port: int
    remote_host: str
    remote_port: int


HOST = "10.126.126.8"
SSH_PORT = 2222
USERNAME = "johnteller"
PASSWORD = "1"

TUNNELS = [
    TunnelSpec(8005, "127.0.0.1", 8005),
    TunnelSpec(8021, "127.0.0.1", 8021),
    TunnelSpec(8022, "127.0.0.1", 8022),
    TunnelSpec(8023, "127.0.0.1", 8023),
]


class ForwardHandler(socketserver.BaseRequestHandler):
    spec: TunnelSpec
    transport: paramiko.Transport

    def handle(self) -> None:
        try:
            channel = self.transport.open_channel(
                "direct-tcpip",
                (self.spec.remote_host, self.spec.remote_port),
                self.request.getpeername(),
            )
        except Exception:
            return
        if channel is None:
            return

        try:
            while True:
                readable, _, _ = select.select([self.request, channel], [], [])
                if self.request in readable:
                    data = self.request.recv(4096)
                    if not data:
                        break
                    channel.sendall(data)
                if channel in readable:
                    data = channel.recv(4096)
                    if not data:
                        break
                    self.request.sendall(data)
        finally:
            channel.close()
            self.request.close()


class ThreadedTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def make_server(transport: paramiko.Transport, spec: TunnelSpec) -> ThreadedTCPServer:
    handler = type(
        f"ForwardHandler_{spec.local_port}",
        (ForwardHandler,),
        {"spec": spec, "transport": transport},
    )
    return ThreadedTCPServer(("127.0.0.1", spec.local_port), handler)


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=SSH_PORT, username=USERNAME, password=PASSWORD, timeout=20)
    transport = client.get_transport()
    if transport is None:
        raise RuntimeError("SSH transport unavailable")

    servers: list[ThreadedTCPServer] = []
    threads: list[threading.Thread] = []
    for spec in TUNNELS:
        server = make_server(transport, spec)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        servers.append(server)
        threads.append(thread)
        print(f"forwarding 127.0.0.1:{spec.local_port} -> {spec.remote_host}:{spec.remote_port}", flush=True)

    try:
        while True:
            if not transport.is_active():
                return 1
            threading.Event().wait(1.0)
    except KeyboardInterrupt:
        return 0
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
