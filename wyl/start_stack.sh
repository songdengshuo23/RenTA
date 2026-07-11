#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/johnteller/team_ws

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

start_registry() {
  local dir="$ROOT/sds/registry-server"
  local log="$dir/logs/server.wyl-restart.log"
  mkdir -p "$dir/logs"
  if port_listening 8001; then
    echo "registry:already_listening"
    return 0
  fi
  (
    cd "$dir"
    set -a
    . ./.env
    set +a
    export DATABASE_URL="postgresql+asyncpg://sds:sds123@127.0.0.1:5432/registry_db"
    export CA_SERVER_BASE_URL="http://127.0.0.1:8003/acps-atr-v2"
    export CA_SERVER_MOCK="false"
    export CA_SERVER_SERVICE_TOKEN="local-dev-token"
    export REGISTRY_SERVICE_TOKEN="local-dev-token"
    export DSP_SERVICE_TOKEN="local-dsp-token"
    export CA_CHALLENGE_STATUS_PATH_TYPE="parent"
    export ACPS_V21_ENABLED="true"
    export ACPS_LEGACY_API_ENABLED="true"
    export ACPS_AIC_DUAL_READ_ENABLED="true"
    export ACPS_EAB_ISSUANCE_ENABLED="true"
    export PYTHONPATH="$dir:$dir/.py312deps:$dir/.venv/lib/python3.13/site-packages"
    nohup python3 -u main.py > "$log" 2>&1 &
    echo $! > "$dir/logs/server.wyl-restart.pid"
  )
  wait_for_port 8001 25 && echo "registry:started" || {
    echo "registry:failed"
    tail -n 80 "$log" || true
    return 1
  }
}

start_challenge() {
  local dir="$ROOT/sds/challenge-server"
  local log="$dir/logs/challenge.global-python.log"
  mkdir -p "$dir/logs"
  if port_listening 8004; then
    echo "challenge:already_listening"
    return 0
  fi
  (
    cd "$dir"
    set -a
    [ -f .env ] && . ./.env
    set +a
    export UVICORN_HOST="0.0.0.0"
    export UVICORN_PORT="8004"
    export BASE_URL="/acps-atr-v2"
    export PYTHONPATH="$dir"
    nohup python3 -u main.py > "$log" 2>&1 &
    echo $! > "$log.pid"
  )
  wait_for_port 8004 20 && echo "challenge:started" || {
    echo "challenge:failed"
    tail -n 80 "$log" || true
    return 1
  }
}

start_ca() {
  local dir="$ROOT/sds/ca-server"
  local log="$dir/logs/ca.global-python.log"
  mkdir -p "$dir/logs"
  if port_listening 8003; then
    echo "ca:already_listening"
    return 0
  fi
  (
    cd "$dir"
    set -a
    [ -f .env ] && . ./.env
    set +a
    export DATABASE_URL="sqlite:///./agent_ca.db"
    export CA_INTERNAL_SERVICE_TOKEN="local-dev-token"
    export CA_ADMIN_TOKEN="local-admin-token"
    export AGENT_REGISTRY_SERVICE_TOKEN="local-dev-token"
    export AGENT_REGISTRY_MOCK="true"
    export HTTP01_VALIDATION_MOCK="true"
    export AGENT_REGISTRY_URL="http://127.0.0.1:8001/acps-atr-v2"
    export AGENT_REGISTRY_INTERNAL_URL="http://127.0.0.1:8001"
    export ACPS_CA_EAB_ENABLED="true"
    export ACPS_CHALLENGE_LEGACY_ENABLED="true"
    export UVICORN_HOST="0.0.0.0"
    export UVICORN_PORT="8003"
    export PYTHONPATH="$dir"
    nohup python3 -u main.py > "$log" 2>&1 &
    echo $! > "$log.pid"
  )
  wait_for_port 8003 25 && echo "ca:started" || {
    echo "ca:failed"
    tail -n 100 "$log" || true
    return 1
  }
}

stop_legacy_registry() {
  local pids
  pids=$(ss -ltnp 2>/dev/null | awk '$4 ~ /:18001$/ { line=$0; sub(/.*pid=/, "", line); sub(/,.*/, "", line); if (line ~ /^[0-9]+$/) print line }' | sort -u)
  if [ -z "${pids:-}" ]; then
    echo "legacy_registry_18001:not_listening"
    return 0
  fi
  echo "legacy_registry_18001:stopping $pids"
  kill $pids 2>/dev/null || true
  sleep 2
  local alive
  alive=$(ss -ltnp 2>/dev/null | awk '$4 ~ /:18001$/ { line=$0; sub(/.*pid=/, "", line); sub(/,.*/, "", line); if (line ~ /^[0-9]+$/) print line }' | sort -u)
  if [ -n "${alive:-}" ]; then
    echo "legacy_registry_18001:force_stopping $alive"
    kill -9 $alive 2>/dev/null || true
  fi
  wait_for_port 18001 1 && {
    echo "legacy_registry_18001:still_listening"
    return 1
  }
  echo "legacy_registry_18001:stopped"
}

start_frontend() {
  local dir="$ROOT/wyl/server"
  local log="$dir/server.log"
  if port_listening 8888; then
    echo "frontend:already_listening"
    return 0
  fi
  (
    cd "$dir"
    export ACPS_FRONTEND_V21_ENABLED="${ACPS_FRONTEND_V21_ENABLED:-true}"
    export ACPS_FRONTEND_EAB_ENABLED="${ACPS_FRONTEND_EAB_ENABLED:-true}"
    nohup python3 server.py --host 0.0.0.0 --port 8888 > "$log" 2>&1 &
    echo $! > "$dir/server.pid"
  )
  wait_for_port 8888 15 && echo "frontend:started" || {
    echo "frontend:failed"
    tail -n 80 "$log" || true
    return 1
  }
}

start_discovery() {
  local enabled="${ACPS_DISCOVERY_V21_ENABLED:-true}"
  case "${enabled,,}" in
    1|true|yes|on) ;;
    *)
      echo "discovery:disabled"
      return 0
      ;;
  esac

  local dir="$ROOT/yhl/ACPs-Discovery-Server"
  local log="$ROOT/server_logs/yhl-discovery-v21.log"
  mkdir -p "$ROOT/server_logs" "$dir/logs"
  if port_listening 8005; then
    echo "discovery:already_listening"
    return 0
  fi
  (
    cd "$dir"
    set -a
    . ./.env
    set +a
    export UVICORN_HOST="0.0.0.0"
    export UVICORN_PORT="8005"
    export UVICORN_RELOAD="false"
    export DRC_BASE_URL="http://127.0.0.1:8001/acps-dsp-v2"
    export DRC_SERVICE_TOKEN="${DSP_SERVICE_TOKEN:-${DRC_SERVICE_TOKEN:-local-dsp-token}}"
    export REGISTRY_ATR_BASE_URL="http://127.0.0.1:8001/acps-atr-v2"
    export REGISTRY_ATR_SERVICE_TOKEN="${REGISTRY_SERVICE_TOKEN:-${REGISTRY_ATR_SERVICE_TOKEN:-local-dev-token}}"
    export PYTHONPATH="$dir:$ROOT/ACPs_update_code/ACPs-SDK"
    nohup "$dir/venv/bin/python" -u main.py > "$log" 2>&1 &
    echo $! > "$dir/logs/service.pid"
  )
  wait_for_port 8005 30 && echo "discovery:started" || {
    echo "discovery:failed"
    tail -n 100 "$log" || true
    return 1
  }
}

start_mq_auth() {
  local enabled="${ACPS_MQ_AUTH_ENABLED:-true}"
  case "${enabled,,}" in
    1|true|yes|on) ;;
    *)
      echo "mq_auth:disabled"
      return 0
      ;;
  esac

  local dir="$ROOT/sds/mq-auth-server"
  local log="$ROOT/server_logs/sds-mq-auth-v21.log"
  mkdir -p "$ROOT/server_logs" "$dir/logs"
  if port_listening 9007 && port_listening 9008; then
    echo "mq_auth:already_listening"
    return 0
  fi
  if port_listening 9007 || port_listening 9008; then
    echo "mq_auth:partial_listener_state" >&2
    return 1
  fi
  (
    cd "$dir"
    nohup ./start.sh > "$log" 2>&1 &
    echo $! > "$dir/logs/service.pid"
  )
  wait_for_port 9007 30 && wait_for_port 9008 30 && echo "mq_auth:started" || {
    echo "mq_auth:failed"
    tail -n 100 "$log" || true
    return 1
  }
}

start_mode_router() {
  local dir="$ROOT/th/mode_router"
  local log="$ROOT/server_logs/th-mode-router.wyl-restart.log"
  mkdir -p "$ROOT/server_logs"
  touch "$dir/.env"
  set_env_kv() {
    local key="$1"
    local value="$2"
    if grep -q "^${key}=" "$dir/.env"; then
      sed -i "s|^${key}=.*|${key}=${value}|" "$dir/.env"
    else
      printf '\n%s=%s\n' "$key" "$value" >> "$dir/.env"
    fi
  }
  set_env_kv RABBITMQ_HOST "${RABBITMQ_HOST:-10.126.126.8}"
  set_env_kv RABBITMQ_PORT "${RABBITMQ_PORT:-5672}"
  set_env_kv RABBITMQ_USER "${RABBITMQ_USER:-guest}"
  set_env_kv RABBITMQ_PASSWORD "${RABBITMQ_PASSWORD:-guest}"
  set_env_kv RABBITMQ_VHOST "${RABBITMQ_VHOST:-/}"
  set_env_kv ACPS_DISCOVERY_V21_ENABLED "${ACPS_DISCOVERY_V21_ENABLED:-true}"
  set_env_kv ACPS_DISCOVERY_LEGACY_FALLBACK_ENABLED "${ACPS_DISCOVERY_LEGACY_FALLBACK_ENABLED:-true}"
  set_env_kv ORCHESTRATOR_DISCOVERY_URL "${ORCHESTRATOR_DISCOVERY_URL:-http://127.0.0.1:8005/acps-adp-v2/discover}"
  set_env_kv ACPS_MQ_AUTH_ENABLED "${ACPS_MQ_AUTH_ENABLED:-true}"
  set_env_kv ACPS_MQ_INBOX_ENABLED "${ACPS_MQ_INBOX_ENABLED:-true}"
  set_env_kv ACPS_MQ_LEGACY_FALLBACK_ENABLED "${ACPS_MQ_LEGACY_FALLBACK_ENABLED:-true}"
  set_env_kv ACPS_MQ_LEADER_AIC "${ACPS_MQ_LEADER_AIC:-1.2.156.3088.1.1.34C2.478BDF.3GF546.0JU4}"
  set_env_kv ACPS_MQ_HOST "${ACPS_MQ_HOST:-127.0.0.1}"
  set_env_kv ACPS_MQ_PORT "${ACPS_MQ_PORT:-5671}"
  set_env_kv ACPS_MQ_VHOST "${ACPS_MQ_VHOST:-acps}"
  set_env_kv ACPS_MQ_AUTH_URL "${ACPS_MQ_AUTH_URL:-https://127.0.0.1:9007}"
  set_env_kv ACPS_MQ_TLS_CERT_FILE "${ACPS_MQ_TLS_CERT_FILE:-$ROOT/sds/mq-auth-server/certs/leader.pem}"
  set_env_kv ACPS_MQ_TLS_KEY_FILE "${ACPS_MQ_TLS_KEY_FILE:-$ROOT/sds/mq-auth-server/certs/leader.key}"
  set_env_kv ACPS_MQ_TLS_CA_FILE "${ACPS_MQ_TLS_CA_FILE:-$ROOT/sds/mq-auth-server/certs/acps-root-ca.pem}"
  set_env_kv ACPS_MQ_TLS_CHECK_HOSTNAME "${ACPS_MQ_TLS_CHECK_HOSTNAME:-false}"
  set_env_kv ACPS_MQ_INVITATION_TIMEOUT_SECONDS "${ACPS_MQ_INVITATION_TIMEOUT_SECONDS:-30}"
  if port_listening 18080; then
    echo "mode_router:already_listening"
    return 0
  fi
  (
    cd "$dir"
    nohup ./start_service.sh > "$log" 2>&1 &
    echo $! > "$ROOT/server_logs/th-mode-router.wyl-restart.pid"
  )
  wait_for_port 18080 25 && echo "mode_router:started" || {
    echo "mode_router:failed"
    tail -n 100 "$log" || true
    return 1
  }
}

start_mode2_group_adapter() {
  local bridge_dir="$ROOT/th/mode_router"
  local proxy_dir="$ROOT/th/mode_router"
  local bridge_log="$ROOT/server_logs/th-mode2-group-bridge.log"
  local proxy_log="$ROOT/server_logs/th-mode2-group-proxy.log"
  mkdir -p "$ROOT/server_logs"
  touch "$bridge_dir/.env"
  set_bridge_env_kv() {
    local key="$1"
    local value="$2"
    if grep -q "^${key}=" "$bridge_dir/.env"; then
      sed -i "s|^${key}=.*|${key}=${value}|" "$bridge_dir/.env"
    else
      printf '\n%s=%s\n' "$key" "$value" >> "$bridge_dir/.env"
    fi
  }
  set_bridge_env_kv ACPS_MQ_INBOX_ENABLED "${ACPS_MQ_INBOX_ENABLED:-true}"
  set_bridge_env_kv ACPS_MQ_HOST "${ACPS_MQ_HOST:-127.0.0.1}"
  set_bridge_env_kv ACPS_MQ_PORT "${ACPS_MQ_PORT:-5671}"
  set_bridge_env_kv ACPS_MQ_VHOST "${ACPS_MQ_VHOST:-acps}"
  set_bridge_env_kv ACPS_MQ_PARTNER_CERT_DIR "${ACPS_MQ_PARTNER_CERT_DIR:-$ROOT/sds/mq-auth-server/certs/partners}"
  set_bridge_env_kv ACPS_MQ_TLS_CA_FILE "${ACPS_MQ_TLS_CA_FILE:-$ROOT/sds/mq-auth-server/certs/acps-root-ca.pem}"
  set_bridge_env_kv ACPS_MQ_TLS_CHECK_HOSTNAME "${ACPS_MQ_TLS_CHECK_HOSTNAME:-false}"
  if ! grep -q '^TRAVEL_GROUP_BRIDGE_FORCE_FALLBACK=' "$bridge_dir/.env" 2>/dev/null; then
    printf '\nTRAVEL_GROUP_BRIDGE_FORCE_FALLBACK=false\n' >> "$bridge_dir/.env"
  else
    sed -i 's/^TRAVEL_GROUP_BRIDGE_FORCE_FALLBACK=.*/TRAVEL_GROUP_BRIDGE_FORCE_FALLBACK=false/' "$bridge_dir/.env"
  fi
  if ! grep -q '^TRAVEL_PROXY_LOCAL_AGENT_MODE=' "$proxy_dir/.env" 2>/dev/null; then
    printf '\nTRAVEL_PROXY_LOCAL_AGENT_MODE=false\n' >> "$proxy_dir/.env"
  else
    sed -i 's/^TRAVEL_PROXY_LOCAL_AGENT_MODE=.*/TRAVEL_PROXY_LOCAL_AGENT_MODE=false/' "$proxy_dir/.env"
  fi
  if ! grep -q '^TRAVEL_PROXY_FORCE_FALLBACK=' "$proxy_dir/.env" 2>/dev/null; then
    printf '\nTRAVEL_PROXY_FORCE_FALLBACK=false\n' >> "$proxy_dir/.env"
  else
    sed -i 's/^TRAVEL_PROXY_FORCE_FALLBACK=.*/TRAVEL_PROXY_FORCE_FALLBACK=false/' "$proxy_dir/.env"
  fi
  if ! grep -q '^GROUP_BRIDGE_BASE_URL=' "$proxy_dir/.env" 2>/dev/null; then
    printf '\nGROUP_BRIDGE_BASE_URL=http://127.0.0.1:8098\n' >> "$proxy_dir/.env"
  else
    sed -i 's|^GROUP_BRIDGE_BASE_URL=.*|GROUP_BRIDGE_BASE_URL=http://127.0.0.1:8098|' "$proxy_dir/.env"
  fi

  if ! port_listening 8098; then
    (
      cd "$bridge_dir"
      set -a
      . ./.env
      set +a
      nohup python3 -m uvicorn travel_group_bridge:app --host 0.0.0.0 --port 8098 > "$bridge_log" 2>&1 &
      echo $! > "$ROOT/server_logs/th-mode2-group-bridge.pid"
    )
  else
    echo "group_bridge:already_listening"
  fi

  if ! port_listening 8099; then
    (
      cd "$proxy_dir"
      set -a
      . ./.env
      set +a
      nohup python3 -m uvicorn travel_agent_proxy:app --host 0.0.0.0 --port 8099 > "$proxy_log" 2>&1 &
      echo $! > "$ROOT/server_logs/th-mode2-group-proxy.pid"
    )
  else
    echo "group_proxy:already_listening"
  fi

  wait_for_port 8098 20 && wait_for_port 8099 20 && echo "mode2_group_adapter:started" || {
    echo "mode2_group_adapter:failed"
    tail -n 80 "$bridge_log" || true
    tail -n 80 "$proxy_log" || true
    return 1
  }
}

start_direct_rpc() {
  local dir="$ROOT/yhl"
  local log="$dir/direct_rpc_server.wyl-restart.log"
  if port_listening 19090; then
    echo "direct_rpc:already_listening"
    return 0
  fi
  (
    cd "$dir"
    nohup ./_start_direct.sh > "$log" 2>&1 &
    echo $! > "$dir/direct_rpc_server.wyl-restart.pid"
  )
  wait_for_port 19090 25 && echo "direct_rpc:started" || {
    echo "direct_rpc:failed"
    tail -n 100 "$log" || true
    return 1
  }
}

stop_legacy_registry
start_challenge
start_ca
start_registry
start_mq_auth
start_discovery
start_mode2_group_adapter
start_mode_router
start_direct_rpc
start_frontend

echo "ports:"
ss -ltnp 2>/dev/null | grep -E ':(5671|5672|8001|8003|8004|8005|9007|9008|18080|19090|8888)\b' || true
