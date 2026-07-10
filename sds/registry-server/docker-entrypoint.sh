#!/usr/bin/env bash
set -euo pipefail
cd /workspace
pip install --upgrade pip
pip install .
alembic upgrade head
exec python main.py
