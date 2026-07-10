#!/usr/bin/env bash
set -euo pipefail
cd /workspace
pip install --upgrade pip
pip install .
exec python main.py
