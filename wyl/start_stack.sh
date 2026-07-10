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
    export ACPS_V21_ENABLED="false"
    export ACPS_LEGACY_API_ENABLED="true"
    export ACPS_AIC_DUAL_READ_ENABLED="true"
    export ACPS_EAB_ISSUANCE_ENABLED="false"
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
    nohup python3 server.py --host 0.0.0.0 --port 8888 > "$log" 2>&1 &
    echo $! > "$dir/server.pid"
  )
  wait_for_port 8888 15 && echo "frontend:started" || {
    echo "frontend:failed"
    tail -n 80 "$log" || true
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
start_mode2_group_adapter
start_mode_router
start_direct_rpc
start_frontend

echo "ports:"
ss -ltnp 2>/dev/null | grep -E ':(8001|8003|8004|18080|19090|8888)\b' || true
