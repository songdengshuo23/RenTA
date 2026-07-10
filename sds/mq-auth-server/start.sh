#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${MQ_AUTH_PYTHON_BIN:-$HERE/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "mq-auth-server Python runtime is missing: $PYTHON_BIN" >&2
  exit 1
fi
if [[ ! -f "$HERE/.env" ]]; then
  echo "mq-auth-server environment file is missing: $HERE/.env" >&2
  exit 1
fi

cd "$HERE"
set -a
. ./.env
set +a
exec "$PYTHON_BIN" -B -m app.main
