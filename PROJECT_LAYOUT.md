# RenTA project layout on remote server

Root: `/home/johnteller/team_ws`

## Canonical runtime directories preserved in place

| Path | Role | Runtime status |
|---|---|---|
| `sds/registry-server` | Registry backend with RenTA extensions: points/events/Passport/Supervisor/API compatibility | Active canonical Registry source |
| `sds/ca-server` | CA / ACME server | Active CA source |
| `sds/challenge-server` | Legacy HTTP-01 challenge server | Legacy runtime, should become fallback after ACPs v2.1 EAB upgrade |
| `th/mode_router` | Orchestrator / Mode Router | Active orchestration source |
| `wyl/frontend` | Built frontend static assets | Active frontend served on port 8888 |
| `wyl/server/server.py` | Frontend static server and reverse proxy | Active gateway server |
| `yhl/ACPs-Discovery-Server` | Existing Discovery server | Active/compatible discovery source |
| `yhl/partner-literature-*` and `yhl/direct_rpc_server.py` | Partner agents / Direct RPC support | Active in group/direct RPC flows |
| `ACPs_update_code/ACPs-SDK` | Legacy ACPs SDK referenced by startup scripts | Keep in place until SDK upgrade |
| `cyf/ACPs-Registry-Server` | Legacy registry snapshot referenced by `start_all_servers.sh` | Keep in place; not used by `wyl/start_stack.sh` main platform path |
| `server_logs` | Runtime logs and PID files | Keep in place; startup scripts write here |

## Semantic symlink view

A non-invasive project view is available at:

```text
/home/johnteller/team_ws/renta_platform
```

This directory contains symlinks with descriptive names. It does not replace or rename active runtime paths, so existing scripts continue to work.

## Cleanup archive

Backup/temp top-level folders not on the active startup path were moved to:

```text
/home/johnteller/team_ws/_archive/pre_upgrade_cleanup_*/
```

This is reversible. No active project code directory was deleted.

## Main startup entry points

```bash
# Full historical inventory/start script
/home/johnteller/team_ws/start_all_servers.sh

# Current platform startup path used by frontend/gateway stack
/home/johnteller/team_ws/wyl/start_stack.sh

# Frontend gateway
/home/johnteller/team_ws/wyl/server/server.py

# Mode Router
/home/johnteller/team_ws/th/mode_router/start_service.sh
```

## Python dependency note

Registry startup currently needs both dependency paths:

```bash
PYTHONPATH=/home/johnteller/team_ws/sds/registry-server:/home/johnteller/team_ws/sds/registry-server/.py312deps:/home/johnteller/team_ws/sds/registry-server/.venv/lib/python3.13/site-packages
```

`asyncpg` is in `.py312deps`; `xattr` is in `.venv`.
