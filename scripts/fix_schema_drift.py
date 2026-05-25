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
    "ALTER TABLE game_players "
    "ADD COLUMN IF NOT EXISTS restock_block_scope VARCHAR",
    "ALTER TABLE game_players "
    "ADD COLUMN IF NOT EXISTS restock_block_until_stock_sale BOOLEAN NOT NULL DEFAULT false",
    # Legacy in-flight restock blocks (rows existing before the scope column
    # was added) default to 'irrigated' since the only path that left them
    # in production testing was Bore Dries Up. Idempotent — once scope is
    # set, the IS NULL clause fails.
    """
    UPDATE game_players SET restock_block_scope = 'irrigated'
    WHERE restock_blocked_until_circuit = true
      AND restock_block_scope IS NULL
    """,
    # High Stock Prices was incorrectly seeded with is_retainable=False, so
    # drawing it never put the card in the player's hand and the +20% bonus
    # could never be applied. Repair the existing prod row. Idempotent.
    "UPDATE cards SET is_retainable = true "
    "WHERE effect_code = 'HIGH_STOCK_PRICES' AND is_retainable = false",
    # New Tucker Bag card "Drought" — ensure the prod row has effect_code
    # 'DROUGHT' so the dispatcher fires the local-drought handler.
    # Idempotent — once effect_code='DROUGHT' the WHERE no longer matches.
    """
    UPDATE cards SET effect_code = 'DROUGHT'
    WHERE deck_type = 'tucker_bag'
      AND title = 'Drought'
      AND (effect_code IS NULL OR effect_code <> 'DROUGHT')
    """,
    # If the card row doesn't exist at all (e.g. fresh seed without the
    # new entry, or local DB lacking it), insert it. Idempotent via the
    # NOT EXISTS guard.
    """
    INSERT INTO cards (deck_type, title, body_text, is_retainable,
                       effect_code, effect_params, one_time)
    SELECT 'tucker_bag', 'Drought',
           'You are affected by Local Drought. Sell half of your Natural / Improved stock to the Bank at $500 per pen (or use a Haystack to receive Stock Sale prices instead — haystack consumed). Drought lasts one full circuit (44 spaces). Irrigated stock is unaffected.',
           false, 'DROUGHT', '{}', false
    WHERE NOT EXISTS (
        SELECT 1 FROM cards
        WHERE deck_type = 'tucker_bag' AND title = 'Drought'
    )
    """,
    # New Tucker Bag card "Drought on ALL Stations" — applies drought to
    # every active player. INSERT IF NOT EXISTS, idempotent.
    """
    INSERT INTO cards (deck_type, title, body_text, is_retainable,
                       effect_code, effect_params, one_time)
    SELECT 'tucker_bag', 'Drought on ALL Stations',
           'General Drought affecting ALL stations. Each player sells half of their Natural / Improved stock to the Bank at $500 per pen (or uses a Haystack to receive Stock Sale prices instead — haystack consumed). Drought lasts one full circuit (44 spaces) per station. While in drought, restocking is restricted to Irrigated paddocks only. Stations with only Irrigated Pasture are unaffected.',
           false, 'DROUGHT_ALL_STATIONS', '{}', false
    WHERE NOT EXISTS (
        SELECT 1 FROM cards
        WHERE deck_type = 'tucker_bag' AND title = 'Drought on ALL Stations'
    )
    """,
    # In case the row exists but effect_code wasn't set (e.g. manually
    # added without the right code), back-fill. Idempotent.
    """
    UPDATE cards SET effect_code = 'DROUGHT_ALL_STATIONS'
    WHERE deck_type = 'tucker_bag'
      AND title = 'Drought on ALL Stations'
      AND (effect_code IS NULL OR effect_code <> 'DROUGHT_ALL_STATIONS')
    """,
    # Swap Fly Strike Dip (was board_index 13) with Shearing Costs (was
    # board_index 40). Idempotent — the IF guards by checking the current
    # name at board_index 13; once swapped, it no longer matches Fly Strike.
    """
    DO $$
    BEGIN
      IF EXISTS (
        SELECT 1 FROM spaces
        WHERE board_index = 13 AND name LIKE '%Fly Strike%'
      ) THEN
        UPDATE spaces SET board_index = 9999 WHERE board_index = 13;
        UPDATE spaces SET board_index = 13   WHERE board_index = 40;
        UPDATE spaces SET board_index = 40   WHERE board_index = 9999;
      END IF;
    END $$;
    """,
    # Haymaking belongs to the BOARD POSITION (37-42), not the space's
    # contents. The swap above carried the Haymaking flag with Shearing
    # over to position 13 — pin it back to position 40. Idempotent via
    # the WHERE guards.
    "UPDATE spaces SET season = NULL "
    "WHERE board_index = 13 AND season = 'Haymaking'",
    "UPDATE spaces SET season = 'Haymaking' "
    "WHERE board_index = 40 AND season IS NULL",
    # Reset any stale negative wool_cheque_bonus values caused by the old
    # blowfly bug (decremented bonus instead of using a dedicated flag).
    "UPDATE game_players SET wool_cheque_bonus = 0 WHERE wool_cheque_bonus < 0",
    # Cap drought_spaces_remaining at one full circuit. Old apply_drought
    # extended by += BOARD_SIZE on subsequent Local Drought landings; the
    # rule is to reset to BOARD_SIZE. Idempotent — once values are <=44,
    # no rows match.
    "UPDATE game_players SET drought_spaces_remaining = 44 "
    "WHERE drought_spaces_remaining > 44 AND is_in_drought = true",
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
    # One-off retroactive credit: George (game 9, player 18) sold 5 pens at
    # $770/pen ($3,850) but should have applied his High Stock Prices card
    # for +20% ($4,620). HSP was never retained because of the
    # is_retainable=false seed bug (now fixed above), so the checkbox never
    # showed in the modal. Credit the $770 difference. Idempotent.
    """
    INSERT INTO transactions (
        game_id, player_from_id, player_to_id, amount,
        transaction_type, notes, created_at
    )
    SELECT 9, NULL, 18, 770, 'stock_sale_correction',
           'Retroactive High Stock Prices +20% correction (5 pens sale)', NOW()
    WHERE NOT EXISTS (
        SELECT 1 FROM transactions
        WHERE notes = 'Retroactive High Stock Prices +20% correction (5 pens sale)'
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
