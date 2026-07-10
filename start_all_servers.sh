#!/usr/bin/env bash
set -u

ROOT="${TEAM_WS_ROOT:-/home/johnteller/team_ws}"
LOG_ROOT="$ROOT/server_logs"
INVENTORY="$ROOT/server_inventory.md"
STARTED=()
SKIPPED=()
WARNINGS=()

mkdir -p "$LOG_ROOT"

timestamp() {
  date '+%Y-%m-%d %H:%M:%S %z'
}

log() {
  printf '[%s] %s\n' "$(timestamp)" "$*"
}

warn() {
  WARNINGS+=("$*")
  log "WARN: $*"
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

port_listening() {
  local port="$1"
  ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "(:|])${port}$"
}

wait_for_port() {
  local port="$1"
  local seconds="${2:-20}"
  local waited=0
  while [ "$waited" -lt "$seconds" ]; do
    if port_listening "$port"; then
      return 0
    fi
    sleep 1
    waited=$((waited + 1))
  done
  return 1
}

start_detached() {
  local name="$1"
  local port="$2"
  local workdir="$3"
  local logfile="$4"
  shift 4
  local cmd="$*"

  if port_listening "$port"; then
    SKIPPED+=("$name already listening on :$port")
    log "SKIP $name: port $port is already listening"
    return 0
  fi
  if [ ! -d "$workdir" ]; then
    warn "$name workdir missing: $workdir"
    return 1
  fi

  mkdir -p "$(dirname "$logfile")"
  log "START $name on :$port"
  (
    cd "$workdir" || exit 1
    nohup bash -lc "$cmd" >"$logfile" 2>&1 &
    echo $! >"$logfile.pid"
  )

  if wait_for_port "$port" 25; then
    STARTED+=("$name started on :$port")
    return 0
  fi

  warn "$name did not open port $port within timeout; see $logfile"
  return 1
}

start_docker_compose_stack() {
  local stack_dir="$ROOT/sds"
  if [ ! -f "$stack_dir/docker-compose.yml" ]; then
    warn "SDS docker-compose.yml not found: $stack_dir/docker-compose.yml"
    return 1
  fi
  if ! have_cmd docker; then
    warn "docker command is not available"
    return 1
  fi

  log "START SDS docker compose stack"
  (
    cd "$stack_dir" || exit 1
    if docker compose version >/dev/null 2>&1; then
      docker compose up -d
    elif have_cmd docker-compose; then
      docker-compose up -d
    else
      echo "No docker compose command found" >&2
      exit 1
    fi
  ) >>"$LOG_ROOT/sds-compose.log" 2>&1 || warn "SDS docker compose up failed; see $LOG_ROOT/sds-compose.log"

  for container in sds-registry-passport-source cb-orchestrator-rabbitmq; do
    if docker container inspect "$container" >/dev/null 2>&1; then
      local state
      state="$(docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null || echo false)"
      if [ "$state" != "true" ]; then
        log "START docker container $container"
        docker start "$container" >>"$LOG_ROOT/docker-extra-containers.log" 2>&1 || warn "docker start $container failed"
      else
        SKIPPED+=("docker container $container already running")
      fi
    fi
  done
}

start_yhl_discovery() {
  start_detached \
    "YHL Agent Discovery Server" \
    8005 \
    "$ROOT/yhl/ACPs-Discovery-Server" \
    "$LOG_ROOT/yhl-discovery.log" \
    'PYTHONPATH="$PWD" ./venv/bin/python main.py'
}

start_literature_agent() {
  local name="$1"
  local port="$2"
  local dir="$3"
  local aic="$4"
  if port_listening "$port"; then
    SKIPPED+=("$name already listening on :$port")
    log "SKIP $name: port $port is already listening"
    return 0
  fi
  if [ ! -f "$ROOT/yhl/agent_base.py" ] && [ ! -f "$ROOT/yhl/agent_base.pyc" ]; then
    local cached
    cached="$(find "$ROOT/yhl/__pycache__" -maxdepth 1 -name 'agent_base.cpython-*.pyc' 2>/dev/null | sort | tail -1)"
    if [ -n "$cached" ]; then
      cp "$cached" "$ROOT/yhl/agent_base.pyc"
      log "Recovered sourceless import cache for agent_base.pyc from $cached"
    fi
  fi
  if [ ! -f "$ROOT/yhl/agent_base.py" ] && [ ! -f "$ROOT/yhl/agent_base.pyc" ]; then
    warn "$name cannot be cold-started because both $ROOT/yhl/agent_base.py and agent_base.pyc are missing. Existing running process, if any, is preserved."
    return 1
  fi
  start_detached \
    "$name" \
    "$port" \
    "$dir" \
    "$LOG_ROOT/${name// /_}.log" \
    "set -a; [ -f '$ROOT/yhl/.env' ] && . '$ROOT/yhl/.env'; set +a; export PYTHONPATH='$ROOT/yhl:$ROOT/ACPs_update_code/ACPs-SDK'; export PARTNER_AIC='$aic'; '$ROOT/yhl/ACPs-Discovery-Server/venv/bin/python' main.py"
}

start_leader_server() {
  if port_listening 8030; then
    SKIPPED+=("Leader server already listening on :8030")
    log "SKIP Leader server: port 8030 is already listening"
    return 0
  fi
  if [ ! -f "$ROOT/leader_server.py" ]; then
    warn "Leader server cannot be cold-started because $ROOT/leader_server.py is missing. Existing running process, if any, is preserved."
    return 1
  fi
  start_detached \
    "Leader server" \
    8030 \
    "$ROOT" \
    "$LOG_ROOT/leader-server.log" \
    "ACPS_SDK_PATH='$ROOT/ACPs_update_code/ACPs-SDK' '$ROOT/yhl/ACPs-Discovery-Server/venv/bin/python3' -u leader_server.py"
}

start_mode_router() {
  start_detached \
    "TH Mode Router" \
    18080 \
    "$ROOT/th/mode_router" \
    "$LOG_ROOT/th-mode-router.log" \
    './start_service.sh'
}

probe_url() {
  local url="$1"
  local code
  local body_file
  body_file="$(mktemp)"
  code="$(curl -m 2 -s -o "$body_file" -w '%{http_code}' "$url" 2>/dev/null || true)"
  local body
  body="$(head -c 120 "$body_file" 2>/dev/null | tr '\n' ' ' | sed 's/|/\\|/g')"
  rm -f "$body_file"
  printf '%s %s' "${code:-000}" "$body"
}

port_owner() {
  local port="$1"
  ss -ltnp 2>/dev/null | awk -v port=":$port" '$4 ~ port"$" {print $0}' | head -1 | sed 's/|/\\|/g'
}

service_row() {
  local name="$1"
  local port="$2"
  local url="$3"
  local probe="$4"
  local source="$5"
  local status="DOWN"
  if port_listening "$port"; then
    status="LISTEN"
  fi
  local probe_result="-"
  if [ -n "$probe" ]; then
    probe_result="$(probe_url "$probe")"
  fi
  local owner
  owner="$(port_owner "$port")"
  printf '| %s | %s | `%s` | %s | `%s` | `%s` |\n' "$name" "$port" "$url" "$status" "$probe_result" "$source" >>"$INVENTORY"
  if [ -n "$owner" ]; then
    printf '  - owner: `%s`\n' "$owner" >>"$INVENTORY"
  fi
}

write_inventory() {
  cat >"$INVENTORY" <<EOF
# team_ws Server Inventory

Generated at: $(timestamp)

Root: \`$ROOT\`

## Active Servers

| Server | Port | URL | Status | Probe | Source / start owner |
|---|---:|---|---|---|---|
EOF

  service_row "SDS Registry Server (Supervisor/Passport)" 8001 "http://10.126.126.8:8001/" "http://127.0.0.1:8001/" "sds/docker-compose.yml: registry-server"
  service_row "SDS Registry Passport Source" 18002 "http://10.126.126.8:18002/" "http://127.0.0.1:18002/" "existing docker container: sds-registry-passport-source"
  service_row "SDS CA Server" 8003 "http://10.126.126.8:8003/" "http://127.0.0.1:8003/health" "sds/docker-compose.yml: ca-server"
  service_row "SDS Challenge Server" 8004 "http://10.126.126.8:8004/" "http://127.0.0.1:8004/" "sds/docker-compose.yml: challenge-server"
  service_row "SDS Postgres" 5432 "postgres://10.126.126.8:5432" "" "sds/docker-compose.yml: postgres"
  service_row "YHL Agent Discovery Server" 8005 "http://10.126.126.8:8005/" "http://127.0.0.1:8005/" "yhl/ACPs-Discovery-Server/main.py"
  service_row "Literature Search Agent" 8021 "http://10.126.126.8:8021/agents/literature_search/rpc" "http://127.0.0.1:8021/health" "yhl/partner-literature-search/main.py"
  service_row "Literature Analysis Agent" 8022 "http://10.126.126.8:8022/agents/literature_analysis/rpc" "http://127.0.0.1:8022/health" "yhl/partner-literature-analysis/main.py"
  service_row "Literature Writing Agent" 8023 "http://10.126.126.8:8023/agents/literature_writing/rpc" "http://127.0.0.1:8023/health" "yhl/partner-literature-writing/main.py"
  service_row "Leader Server" 8030 "http://10.126.126.8:8030/" "http://127.0.0.1:8030/health" "leader_server.py process; source currently missing"
  service_row "TH Mode Router" 18080 "http://10.126.126.8:18080/" "http://127.0.0.1:18080/health" "th/mode_router/start_service.sh"
  service_row "RabbitMQ AMQP" 5672 "amqp://10.126.126.8:5672" "" "existing docker container: cb-orchestrator-rabbitmq"
  service_row "RabbitMQ Management" 15672 "http://10.126.126.8:15672/" "http://127.0.0.1:15672/" "existing docker container: cb-orchestrator-rabbitmq"

  {
    echo
    echo "## Start Summary"
    echo
    echo "- Started by this run: ${#STARTED[@]}"
    for item in "${STARTED[@]:-}"; do echo "  - $item"; done
    echo "- Already running / skipped: ${#SKIPPED[@]}"
    for item in "${SKIPPED[@]:-}"; do echo "  - $item"; done
    echo "- Warnings: ${#WARNINGS[@]}"
    for item in "${WARNINGS[@]:-}"; do echo "  - $item"; done
    echo
    echo "## Notes"
    echo
    echo "- Obsolete Registry/CA/Challenge/Client/Discovery snapshots were removed from ACPs_update_code; ACPs-SDK is retained because the active orchestrator still imports it."
    echo "- Literature partner agents use yhl/agent_base.py when present; if only __pycache__ is available, this script restores yhl/agent_base.pyc for sourceless import."
    echo "- Leader Server is currently running, but leader_server.py is missing on disk; if port 8030 is stopped, cold-start is not possible until that source file is restored."
  } >>"$INVENTORY"
}

main() {
  log "Using ROOT=$ROOT"
  start_docker_compose_stack
  start_yhl_discovery
  start_literature_agent "Literature Search Agent" 8021 "$ROOT/yhl/partner-literature-search" "aip-auto-agent-wwx_search"
  start_literature_agent "Literature Analysis Agent" 8022 "$ROOT/yhl/partner-literature-analysis" "aip-auto-agent-wwx_analysis"
  start_literature_agent "Literature Writing Agent" 8023 "$ROOT/yhl/partner-literature-writing" "aip-auto-agent-wx_writing"
  start_leader_server
  start_mode_router
  write_inventory
  log "Inventory written to $INVENTORY"
  echo
  sed -n '1,220p' "$INVENTORY"
}

main "$@"
