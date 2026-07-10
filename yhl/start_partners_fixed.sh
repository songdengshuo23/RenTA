#!/bin/bash
set -e
YHL=/home/johnteller/team_ws/yhl
PYTHON=$YHL/ACPs-Discovery-Server/venv/bin/python
ENV_FILE=$YHL/.env

# 从 .env 读 LLM 配置(用 awk 避免 grep+cut 的 quoting 问题)
LLM_API_KEY=$(awk -F= '/^LLM_API_KEY/ {print substr($0, index($0,"=")+1)}' $ENV_FILE)
LLM_API_URL=$(awk -F= '/^LLM_API_URL/ {print substr($0, index($0,"=")+1)}' $ENV_FILE)
LLM_MODEL=$(awk -F= '/^LLM_MODEL/ {print substr($0, index($0,"=")+1)}' $ENV_FILE)

# 兜底
[ -z "$LLM_API_URL" ] && LLM_API_URL=https://api.deepseek.com/v1/chat/completions
[ -z "$LLM_MODEL" ] && LLM_MODEL=deepseek-v4-pro

if [ -z "$LLM_API_KEY" ]; then
  echo "ERR: LLM_API_KEY not in $ENV_FILE"
  exit 1
fi

echo "LLM key=${LLM_API_KEY:0:8}... url=$LLM_API_URL model=$LLM_MODEL"

# 停旧
for pid in $(pgrep -f 'partner-literature-.*/main.py' 2>/dev/null || true); do
  kill "$pid" 2>/dev/null || true
done
sleep 2

# 启 3 个 partner(把 LLM env 通过 env 传,而不是拼到字符串)
for role in search analysis writing; do
  cd "$YHL/partner-literature-$role"
  LLM_API_KEY="$LLM_API_KEY" \
  LLM_API_URL="$LLM_API_URL" \
  LLM_MODEL="$LLM_MODEL" \
  nohup setsid bash -c "exec env LLM_API_KEY='$LLM_API_KEY' LLM_API_URL='$LLM_API_URL' LLM_MODEL='$LLM_MODEL' '$PYTHON' main.py" > server.log 2>&1 </dev/null &
  disown
  cd "$YHL"
done

sleep 4
for p in 8021 8022 8023; do
  printf '  %s: ' "$p"
  curl -s -m 2 "http://localhost:$p/health" | head -c 120
  echo
done
echo "All partners started"
