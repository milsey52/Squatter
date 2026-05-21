"""Idempotent backfill for columns missed by the consolidated squatter_schema
migration. Safe to run on every container start; uses ADD COLUMN IF NOT EXISTS.

Exists because some deployment paths skipped the follow-up alembic migration
that added these columns.
"""
import os
import sys

import psycopg2


STATEMENTS = [
    "ALTER TABLE games "
    "ADD COLUMN IF NOT EXISTS current_turn_order_round INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE game_players "
    "ADD COLUMN IF NOT EXISTS restock_block_spaces_remaining INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE cards "
    "ADD COLUMN IF NOT EXISTS one_time BOOLEAN NOT NULL DEFAULT false",
]


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("fix_schema_drift: DATABASE_URL not set; skipping", flush=True)
        return 0

    conn = psycopg2.connect(url)
    try:
        with conn, conn.cursor() as cur:
            for stmt in STATEMENTS:
                print(f"fix_schema_drift: {stmt}", flush=True)
                cur.execute(stmt)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
