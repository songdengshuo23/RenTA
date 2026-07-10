#!/usr/bin/env bash
set -euo pipefail

: "${STAGE2_TEST_DATABASE_URL:?set STAGE2_TEST_DATABASE_URL}"
: "${STAGE2_TEST_PSQL_URL:?set STAGE2_TEST_PSQL_URL}"
: "${STAGE2_ARTIFACT_DIR:?set STAGE2_ARTIFACT_DIR}"

if [[ "$STAGE2_TEST_DATABASE_URL" == *"/registry_db" ]]; then
  echo "stage2 migration check refuses to run against registry_db" >&2
  exit 2
fi

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p "$STAGE2_ARTIFACT_DIR"

psql_value() {
  psql "$STAGE2_TEST_PSQL_URL" -Atc "$1"
}

cd "$ROOT/sds/registry-server"
export DATABASE_URL="$STAGE2_TEST_DATABASE_URL"
export PYTHONPATH="$PWD:$PWD/.py312deps:$PWD/.venv/lib/python3.13/site-packages"
export PYTHONDONTWRITEBYTECODE=1

psql "$STAGE2_TEST_PSQL_URL" -At -F= -c "
SELECT 'version=' || version_num FROM alembic_version;
SELECT 'account_user=' || count(*) FROM account_user;
SELECT 'agent=' || count(*) FROM agent;
SELECT 'points_wallet=' || count(*) FROM points_wallet;
SELECT 'points_transaction=' || count(*) FROM points_transaction;
SELECT 'points_wallet_columns=' || count(*) FROM information_schema.columns
  WHERE table_schema='public' AND table_name='points_wallet';
SELECT 'points_transaction_columns=' || count(*) FROM information_schema.columns
  WHERE table_schema='public' AND table_name='points_transaction';
" | tee "$STAGE2_ARTIFACT_DIR/before.log"

test "$(psql_value 'select version_num from alembic_version')" = "d9e0f1a2b3c4"
test "$(psql_value "select count(*) from information_schema.columns where table_schema='public' and table_name='points_wallet'")" = "5"
test "$(psql_value "select count(*) from information_schema.columns where table_schema='public' and table_name='points_transaction'")" = "12"

python3 -B -m alembic stamp e7f6a5b4c3d2 2>&1 | tee "$STAGE2_ARTIFACT_DIR/stamp_e7.log"
python3 -B -m alembic upgrade f1a2b3c4d5e6 2>&1 | tee "$STAGE2_ARTIFACT_DIR/upgrade.log"
test "$(psql_value 'select version_num from alembic_version')" = "f1a2b3c4d5e6"
test "$(psql_value "select to_regclass('public.eab_credential')")" = "eab_credential"

ACPS_EAB_ISSUANCE_ENABLED=true \
SM4_ENCRYPTION_KEY=0123456789abcdeffedcba9876543210 \
EAB_CREDENTIAL_EXPIRE_HOURS=24 \
python3 -B "$ROOT/scripts/stage2_eab_db_probe.py" \
  2>&1 | tee "$STAGE2_ARTIFACT_DIR/lifecycle.log"

psql "$STAGE2_TEST_PSQL_URL" -At -F= -c "
SELECT 'version=' || version_num FROM alembic_version;
SELECT 'account_user=' || count(*) FROM account_user;
SELECT 'points_wallet=' || count(*) FROM points_wallet;
SELECT 'points_transaction=' || count(*) FROM points_transaction;
SELECT 'eab_credential=' || count(*) FROM eab_credential;
" | tee "$STAGE2_ARTIFACT_DIR/after_upgrade.log"

python3 -B -m alembic downgrade e7f6a5b4c3d2 \
  2>&1 | tee "$STAGE2_ARTIFACT_DIR/downgrade.log"
test "$(psql_value 'select version_num from alembic_version')" = "e7f6a5b4c3d2"
test -z "$(psql_value "select to_regclass('public.eab_credential')")"

python3 -B -m alembic upgrade f1a2b3c4d5e6 \
  2>&1 | tee "$STAGE2_ARTIFACT_DIR/reupgrade.log"
test "$(psql_value 'select count(*) from eab_credential')" = "0"

psql "$STAGE2_TEST_PSQL_URL" -At -F= -c "
SELECT 'version=' || version_num FROM alembic_version;
SELECT 'account_user=' || count(*) FROM account_user;
SELECT 'points_wallet=' || count(*) FROM points_wallet;
SELECT 'points_transaction=' || count(*) FROM points_transaction;
SELECT 'eab_credential=' || count(*) FROM eab_credential;
" | tee "$STAGE2_ARTIFACT_DIR/final.log"

sha256sum "$STAGE2_ARTIFACT_DIR"/* > "$STAGE2_ARTIFACT_DIR/SHA256SUMS"
echo "stage2 isolated migration check passed"
