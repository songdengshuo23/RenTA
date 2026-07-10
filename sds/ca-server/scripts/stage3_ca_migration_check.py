"""Validate the live SQLite CA schema before stamping its legacy Alembic head."""

import argparse
import json
import sqlite3
from pathlib import Path


PREVIOUS_REVISION = "9b3d2b7c1a6f"
NEW_REVISION = "d4e5f6a7b8c9"

REQUIRED_COLUMNS = {
    "acme_accounts": {
        "id",
        "key_id",
        "public_key",
        "status",
        "external_account_binding",
    },
    "acme_orders": {"id", "order_id", "account_id", "status", "identifiers"},
    "acme_authorizations": {"id", "authz_id", "order_id", "status"},
    "acme_challenges": {"id", "challenge_id", "authorization_id", "status"},
    "acme_certificates": {"id", "cert_id", "order_id", "aic", "status"},
    "certificates": {"id", "serial_number", "version", "aic", "status"},
}


def inspect_database(path: Path, expect_aic: bool) -> dict:
    if not path.is_file():
        raise SystemExit(f"database does not exist: {path}")

    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise SystemExit(f"database integrity check failed: {integrity}")

        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        missing_tables = sorted(set(REQUIRED_COLUMNS) - tables)
        if missing_tables:
            raise SystemExit(f"missing required tables: {', '.join(missing_tables)}")

        counts = {}
        for table, required in REQUIRED_COLUMNS.items():
            columns = {
                row[1]
                for row in connection.execute(f'PRAGMA table_info("{table}")')
            }
            missing_columns = sorted(required - columns)
            if missing_columns:
                raise SystemExit(
                    f"{table} is missing columns: {', '.join(missing_columns)}"
                )
            counts[table] = connection.execute(
                f'SELECT count(*) FROM "{table}"'
            ).fetchone()[0]

        account_columns = {
            row[1]
            for row in connection.execute('PRAGMA table_info("acme_accounts")')
        }
        has_account_aic = "aic" in account_columns
        if expect_aic != has_account_aic:
            expected = "present" if expect_aic else "absent"
            raise SystemExit(f"acme_accounts.aic must be {expected}")

        revisions = []
        if "alembic_version" in tables:
            revisions = [
                row[0]
                for row in connection.execute(
                    "SELECT version_num FROM alembic_version"
                )
            ]

        return {
            "database": str(path.resolve()),
            "integrity": integrity,
            "hasAccountAic": has_account_aic,
            "alembicVersions": revisions,
            "counts": counts,
        }
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("--expect-aic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(inspect_database(args.database, args.expect_aic), indent=2))


if __name__ == "__main__":
    main()
