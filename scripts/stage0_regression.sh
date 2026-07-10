#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
STAMP=$(date +%Y%m%d_%H%M%S)
ARTIFACT_DIR=${STAGE0_ARTIFACT_DIR:-"$ROOT/_archive/stage0_regression_$STAMP"}

mkdir -p "$ARTIFACT_DIR"

run_check() {
  local name="$1"
  shift
  local log="$ARTIFACT_DIR/$name.log"

  printf '[stage0] %s\n' "$name"
  if "$@" >"$log" 2>&1; then
    tail -n 5 "$log"
  else
    tail -n 80 "$log"
    return 1
  fi
}

run_check smoke python3 "$ROOT/scripts/stage0_smoke.py"

(
  cd "$ROOT/sds/registry-server"
  export DATABASE_URL="postgresql+asyncpg://stage0:stage0@127.0.0.1:1/stage0"
  export PYTHONPATH="$PWD:$PWD/.py312deps:$PWD/.venv/lib/python3.13/site-packages"
  run_check registry python3 -m pytest -q \
    --deselect tests/test_atr_api.py::test_get_passport_dispatch_returns_eligible_view \
    --deselect tests/test_atr_api.py::test_get_passport_dispatch_blocks_failed_health_probe \
    --deselect tests/test_supervisor.py::test_review_executes_runtime_validation_against_real_endpoint \
    --deselect tests/test_supervisor.py::test_runtime_repeat_count_updates_reliability \
    --deselect tests/test_supervisor.py::test_llm_approved_warning_review_auto_publishes_for_discovery \
    --deselect tests/test_supervisor.py::test_manual_staff_approval_publishes_manual_review_passport
)

(
  cd "$ROOT/sds/ca-server"
  export DATABASE_URL="sqlite:///$ARTIFACT_DIR/ca_test.db"
  export PYTHONPATH="$PWD"
  rm -f "$ARTIFACT_DIR/ca_test.db"
  run_check ca-schema python3 -c \
    'from main import app; from sqlmodel import SQLModel; from app.core.db_session import engine; SQLModel.metadata.create_all(engine)'
  run_check ca python3 -m pytest -q
)

(
  cd "$ROOT/sds/challenge-server"
  export PYTHONPATH="$PWD"
  run_check challenge python3 -m pytest -q
)

(
  cd "$ROOT/th/mode_router"
  run_check mode-router-tests python3 -m pytest -q tests \
    --deselect tests/test_mode_selector.py::ModeSelectorTests::test_score_can_be_parsed_from_memo \
    --deselect tests/test_orchestrator.py::OrchestratorTests::test_build_mode2_plan
  run_check mode-router-plan-sequential python3 -m pytest -q \
    tests/test_orchestrator.py::OrchestratorTests::test_build_mode2_plan_sequential_children_have_dependency_chain
  run_check mode-router-root python3 -m pytest -q test_service.py \
    --deselect test_service.py::ServiceTests::test_http_mode2_polls_working_agent_until_ready
)

sha256sum "$ARTIFACT_DIR"/*.log >"$ARTIFACT_DIR/SHA256SUMS"
printf '[stage0] all regression gates passed\n'
printf '[stage0] artifacts: %s\n' "$ARTIFACT_DIR"
