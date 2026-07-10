#!/bin/bash
cd /home/johnteller/team_ws/yhl
export $(grep -E "^LLM_" .env | xargs)
exec ./ACPs-Discovery-Server/venv/bin/python -B direct_rpc_server.py
