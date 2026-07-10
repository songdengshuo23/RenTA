#!/bin/bash
ENV_FILE=/home/johnteller/team_ws/yhl/ACPs-Discovery-Server/.env
PYTHON=/home/johnteller/team_ws/yhl/ACPs-Discovery-Server/venv/bin/python
YHL=/home/johnteller/team_ws/yhl

export LLM_API_KEY=
export LLM_API_URL=
export LLM_MODEL=
[ -z  ] && export LLM_API_URL=https://api.deepseek.com/v1/chat/completions
[ -z  ] && export LLM_MODEL=deepseek-v4-pro

echo LLM_API_KEY=... URL= MODEL=

# 停止旧进程
for pid in ; do
    kill  2>/dev/null
done
sleep 2

# 启动三个Agent
cd /partner-literature-search
nohup  main.py > server.log 2>&1 &

cd /partner-literature-analysis
nohup  main.py > server.log 2>&1 &

cd /partner-literature-writing
nohup  main.py > server.log 2>&1 &

sleep 5
curl -s http://localhost:8021/ && echo ''
curl -s http://localhost:8022/ && echo ''
curl -s http://localhost:8023/ && echo ''
echo 'All partners started'
