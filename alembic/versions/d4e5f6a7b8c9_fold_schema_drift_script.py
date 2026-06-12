"""fold scripts/fix_schema_drift.py into the migration chain

The drift script ran on every container start to backfill columns missed
by older deploys and patch seeded/static data. Carrying it forever meant
the migration history and the real schema could diverge silently. All of
its (idempotent) statements now run exactly once, here.

Three statement categories, all safe as a one-shot:
- schema columns: ADD COLUMN IF NOT EXISTS (no-ops where migrations
  already created them);
- static-data patches: the seed CSVs/scripts have carried these fixes
  for some time, so they only matter for databases seeded before that.
  The two card INSERTs additionally require the Tucker Bag deck to
  already exist — on a fresh database the seeder provides those cards,
  and inserting them here first would trip the seeder's
  skip-if-any-rows guard and leave the deck unseeded (a latent bug in
  the old boot order, fixed by this guard);
- one-off production data corrections: each guarded by a unique marker.

Postgres-only (the SQL uses DO blocks / IF NOT EXISTS); on other
dialects (SQLite tests build schema from the models) this is a no-op.

Revision ID: d4e5f6a7b8c9
Revises: c9d0e1f2a3b4
Create Date: 2026-06-12 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STATEMENTS = [
    # ── Schema columns missed by older deploys ──────────────────────────
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
    "ALTER TABLE game_players "
    "ADD COLUMN IF NOT EXISTS is_ai BOOLEAN NOT NULL DEFAULT false",
    "ALTER TABLE game_players "
    "ADD COLUMN IF NOT EXISTS ai_difficulty VARCHAR",
    "ALTER TABLE game_rules "
    "ADD COLUMN IF NOT EXISTS ai_reaction_time_seconds INTEGER NOT NULL DEFAULT 4",
    "ALTER TABLE game_players "
    "ADD COLUMN IF NOT EXISTS restock_block_marker_board_index INTEGER",
    "ALTER TABLE game_players "
    "ADD COLUMN IF NOT EXISTS restock_block_source VARCHAR",
    "ALTER TABLE game_players "
    "ADD COLUMN IF NOT EXISTS rejoin_code VARCHAR",
    # ── Legacy game-state repairs (guarded, no-op once applied) ─────────
    # Legacy in-flight restock blocks default to 'irrigated' (the only
    # path that left them in production was Bore Dries Up).
    """
    UPDATE game_players SET restock_block_scope = 'irrigated'
    WHERE restock_blocked_until_circuit = true
      AND restock_block_scope IS NULL
    """,
    # ── Static-data patches for databases seeded before the fixes ───────
    # High Stock Prices was seeded with is_retainable=false, so the card
    # never reached the player's hand.
    "UPDATE cards SET is_retainable = true "
    "WHERE effect_code = 'HIGH_STOCK_PRICES' AND is_retainable = false",
    # Canonical effect_code for the Local Drought card is DROUGHT_LOCAL.
    """
    UPDATE cards SET effect_code = 'DROUGHT_LOCAL'
    WHERE deck_type = 'tucker_bag'
      AND title IN ('Drought', 'Local Drought')
      AND (effect_code IS NULL OR effect_code <> 'DROUGHT_LOCAL')
    """,
    # Insert Local Drought ONLY into an already-seeded deck that lacks it
    # (fresh databases get it from the seeder — see module docstring).
    """
    INSERT INTO cards (deck_type, title, body_text, is_retainable,
                       effect_code, effect_params, one_time)
    SELECT 'tucker_bag', 'Local Drought',
           'You are affected by Local Drought. Sell half of your Natural / Improved stock to the Bank at $500 per pen (or use a Haystack to receive Stock Sale prices instead — haystack consumed). Drought lasts one full circuit (44 spaces). Irrigated stock is unaffected.',
           false, 'DROUGHT_LOCAL', '{}', false
    WHERE NOT EXISTS (
        SELECT 1 FROM cards
        WHERE deck_type = 'tucker_bag' AND title IN ('Drought', 'Local Drought')
    )
    AND EXISTS (SELECT 1 FROM cards WHERE deck_type = 'tucker_bag')
    """,
    # Same for Drought on ALL Stations.
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
    AND EXISTS (SELECT 1 FROM cards WHERE deck_type = 'tucker_bag')
    """,
    """
    UPDATE cards SET effect_code = 'DROUGHT_ALL_STATIONS'
    WHERE deck_type = 'tucker_bag'
      AND title = 'Drought on ALL Stations'
      AND (effect_code IS NULL OR effect_code <> 'DROUGHT_ALL_STATIONS')
    """,
    # Swap Fly Strike Dip (was board_index 13) with Shearing Costs (was
    # 40). Current Properties.csv seeds the swapped layout directly.
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
    # contents — re-pin after the swap above.
    "UPDATE spaces SET season = NULL "
    "WHERE board_index = 13 AND season = 'Haymaking'",
    "UPDATE spaces SET season = 'Haymaking' "
    "WHERE board_index = 40 AND season IS NULL",
    # Reset stale negative wool_cheque_bonus values from the old blowfly
    # bug, and cap drought length at one full circuit.
    "UPDATE game_players SET wool_cheque_bonus = 0 WHERE wool_cheque_bonus < 0",
    "UPDATE game_players SET drought_spaces_remaining = 44 "
    "WHERE drought_spaces_remaining > 44 AND is_in_drought = true",
    # ── One-off production data corrections (idempotent via markers) ────
    # Jim (game 2, player 3): shorted $375 on three wool cheques by the
    # Blowfly Wave bug.
    """
    INSERT INTO transactions (
        game_id, player_from_id, player_to_id, amount,
        transaction_type, notes, created_at
    )
    SELECT 2, NULL, 3, 1125, 'wool_cheque_correction',
           'Retroactive ram bonus correction (Blowfly Wave bug)', NOW()
    WHERE EXISTS (SELECT 1 FROM games WHERE game_id = 2)
      AND NOT EXISTS (
        SELECT 1 FROM transactions
        WHERE notes = 'Retroactive ram bonus correction (Blowfly Wave bug)'
    )
    """,
    # George (game 9, player 18): High Stock Prices +20% never applied to
    # a 5-pen sale because of the is_retainable seed bug.
    """
    INSERT INTO transactions (
        game_id, player_from_id, player_to_id, amount,
        transaction_type, notes, created_at
    )
    SELECT 9, NULL, 18, 770, 'stock_sale_correction',
           'Retroactive High Stock Prices +20% correction (5 pens sale)', NOW()
    WHERE EXISTS (SELECT 1 FROM games WHERE game_id = 9)
      AND NOT EXISTS (
        SELECT 1 FROM transactions
        WHERE notes = 'Retroactive High Stock Prices +20% correction (5 pens sale)'
    )
    """,
    # Max in game GEG2LA: Local Drought card silently no-op'd before
    # commit 3c1c725 (renamed handler). Re-apply if still applicable.
    """
    DO $$
    DECLARE
      v_game_id INT;
      v_player_id INT;
      v_current_space INT;
    BEGIN
      SELECT game_id INTO v_game_id FROM games WHERE game_code = 'GEG2LA';
      IF v_game_id IS NULL THEN RETURN; END IF;

      SELECT game_player_id, current_board_index
        INTO v_player_id, v_current_space
      FROM game_players
      WHERE game_id = v_game_id AND player_name = 'Max';
      IF v_player_id IS NULL THEN RETURN; END IF;

      IF EXISTS (
        SELECT 1 FROM transactions
        WHERE game_id = v_game_id
          AND notes = 'Retroactive drought apply for Max (DROUGHT_LOCAL handler bug)'
      ) THEN RETURN; END IF;

      IF NOT EXISTS (
        SELECT 1 FROM paddocks
        WHERE game_id = v_game_id
          AND owner_game_player_id = v_player_id
          AND paddock_type IN ('natural','improved')
      ) THEN RETURN; END IF;

      IF EXISTS (
        SELECT 1 FROM game_players
        WHERE game_player_id = v_player_id AND is_in_drought = true
      ) THEN RETURN; END IF;

      UPDATE game_players SET
        is_in_drought = true,
        drought_spaces_remaining = 44,
        drought_start_space = v_current_space
      WHERE game_player_id = v_player_id;

      INSERT INTO transactions (
        game_id, player_from_id, player_to_id, amount,
        transaction_type, notes, created_at
      ) VALUES (
        v_game_id, NULL, v_player_id, 0, 'admin_fix',
        'Retroactive drought apply for Max (DROUGHT_LOCAL handler bug)', NOW()
      );
    END $$;
    """,
]


def upgrade() -> None:
    if op.get_bind().dialect.name != 'postgresql':
        return
    for stmt in STATEMENTS:
        op.execute(stmt)


def downgrade() -> None:
    # Data patches and backfilled columns are not reversible in any
    # meaningful way; the columns are owned by earlier migrations.
    pass
