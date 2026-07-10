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
| `server_logs` | Runtime logs and PID files | Keep in place; startup scripts write here |

## Semantic symlink view

A non-invasive project view is available at:

```text
/home/johnteller/team_ws/renta_platform
```

This directory contains symlinks with descriptive names. It does not replace or rename active runtime paths, so existing scripts continue to work. The obsolete `legacy_registry_cyf` and broad `legacy_acps_reference` links were removed; `legacy_acps_sdk` remains valid.

## Removed unused runtime copies

The following paths had no process, startup, systemd, cron, Docker, or source-code runtime references and were deleted after the active paths were verified:

```text
cyf/
sds/image-parts/
ACPs_update_code/ACPs-Registry-Server/
ACPs_update_code/ACPs-CA-Server/
ACPs_update_code/ACPs-CA-Challenge/
ACPs_update_code/ACPs-CA-Client/
ACPs_update_code/ACPs-Discovery-Server/
wyl/frontend_backups/
module-local backups/ and *.bak* files
25 unreachable files from an obsolete Vite build in wyl/frontend/assets/
```

`sds/registry-server` is the only Registry implementation used by the platform. `yhl/ACPs-Discovery-Server` is the active Discovery implementation. `ACPs_update_code/ACPs-SDK` is deliberately retained because Mode Router and partner startup paths still import it.

## Cleanup archive

Backup/temp top-level folders not on the active startup path were moved to:

```text
/home/johnteller/team_ws/_archive/pre_upgrade_cleanup_*/
```

The archived pre-upgrade material remains reversible. The unused runtime copies listed above were deleted rather than archived; they remain available in Git history at commit `88542ce` if a historical comparison is needed.

## Main startup entry points

```bash
# Full active-service inventory/start script
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
