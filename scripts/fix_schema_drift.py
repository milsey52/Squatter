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
    "ALTER TABLE game_players "
    "ADD COLUMN IF NOT EXISTS wool_cheque_blowfly_pct INTEGER NOT NULL DEFAULT 0",
    # Reset any stale negative wool_cheque_bonus values caused by the old
    # blowfly bug (decremented bonus instead of using a dedicated flag).
    "UPDATE game_players SET wool_cheque_bonus = 0 WHERE wool_cheque_bonus < 0",
    # One-off retroactive credit: Jim (game 2, player 3) was shorted $375
    # on each of three wool cheques (ids 6, 22, 28) by the Blowfly Wave bug.
    # Idempotent via the unique notes string.
    """
    INSERT INTO transactions (
        game_id, player_from_id, player_to_id, amount,
        transaction_type, notes, created_at
    )
    SELECT 2, NULL, 3, 1125, 'wool_cheque_correction',
           'Retroactive ram bonus correction (Blowfly Wave bug)', NOW()
    WHERE NOT EXISTS (
        SELECT 1 FROM transactions
        WHERE notes = 'Retroactive ram bonus correction (Blowfly Wave bug)'
    )
    """,
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
