#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_BIN="${WORKSPACE_ROOT}/yhl/ACPs-Discovery-Server/venv/bin/python"

if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3 || command -v python)"
fi

export PYTHONPATH="$SCRIPT_DIR:$WORKSPACE_ROOT/ACPs_update_code/ACPs-SDK"

exec "$PYTHON_BIN" "$SCRIPT_DIR/run_literature_workflow.py" "$@"
