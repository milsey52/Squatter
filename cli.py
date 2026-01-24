#!/usr/bin/env python
import argparse
import sys
from contextlib import contextmanager
from sqlalchemy import func

from app.db import SessionLocal
from app import models
from app.services.turn_manager import TurnManager
from app.services.seed import seed_asset_states
from app.services.ledger_service import LedgerService
from datetime import datetime


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_game_or_exit(session, game_id: int) -> models.Game:
    """Get game by ID or print error and exit."""
    game = session.query(models.Game).filter_by(game_id=game_id).first()
    if not game:
        print(f"Error: Game {game_id} not found.", file=sys.stderr)
        sys.exit(1)
    return game

def start_game(args):
    with get_session() as session:
        # create game
        game = models.Game(host_user_id=args.host_user_id, status="in_progress")
        session.add(game)
        session.flush()

        # add house rules (use default values or parse from args)
        house_rules = models.HouseRule(
            game_id=game.game_id,
            starting_cash=args.start_cash,
            pass_start_bonus=args.pass_bonus,
            jackpot_enabled=args.jackpot,
        )
        session.add(house_rules)

        # add players
        for order, name in enumerate(args.players, start=1):
            gp = models.GamePlayer(
                game_id=game.game_id,
                player_name=name,
                turn_order=order,
                current_space_id=0,
                in_jail=False,
                jail_turns=0,
                double_streak=0,
            )
            session.add(gp)

        session.flush()
        seed_asset_states(session, game.game_id)

        session.commit()
        print(f"Started game {game.game_id} with players {', '.join(args.players)}")

def next_turn(args):
    with get_session() as session:
        get_game_or_exit(session, args.game_id)
        tm = TurnManager(session, args.game_id)
        tm.play_turn()
        session.commit()
        print("Turn completed.")

def show_board(args):
    with get_session() as session:
        get_game_or_exit(session, args.game_id)
        players = (
            session.query(models.GamePlayer)
            .filter(models.GamePlayer.game_id == args.game_id)
            .order_by(models.GamePlayer.turn_order)
            .all()
        )
        for p in players:
            print(
                f"{p.player_name:10} | Space: {p.current_space_id:02} | "
                f"Jail: {p.in_jail} | Double streak: {p.double_streak}"
            )

def list_players(args):
    with get_session() as session:
        get_game_or_exit(session, args.game_id)
        players = (
            session.query(models.GamePlayer)
            .filter(models.GamePlayer.game_id == args.game_id)
            .order_by(models.GamePlayer.turn_order)
            .all()
        )
        for p in players:
            status = "active" if p.is_active else "inactive"
            print(
                f"ID={p.game_player_id:2d} | {p.player_name:10s} "
                f"| space={p.current_space_id:02d} | {status}"
            )

def ledger(args):
    with get_session() as session:
        get_game_or_exit(session, args.game_id)
        txns = (
            session.query(models.Transaction)
            .filter(models.Transaction.game_id == args.game_id)
            .order_by(models.Transaction.created_at)
            .all()
        )
        for t in txns:
            print(
                f"{t.created_at} | {t.transaction_type:15} | "
                f"{t.player_from_id} -> {t.player_to_id} | ${t.amount}"
            )

def save_game(args):
    with get_session() as session:
        game = get_game_or_exit(session, args.game_id)
        game.last_saved_at = datetime.utcnow()
        session.commit()
        print(f"Saved game {game.game_id}")

def retire_player(args):
    with get_session() as session:
        get_game_or_exit(session, args.game_id)
        player = (
            session.query(models.GamePlayer)
            .filter_by(game_id=args.game_id, game_player_id=args.player_id)
            .first()
        )
        if not player:
            print("Player not found.")
            return
        if not player.is_active:
            print("Player is already inactive.")
            return

        # Show summary so user’s sure
        print(f"About to retire {player.player_name} (ID {player.game_player_id})")
        owned_assets = (
            session.query(models.AssetState)
            .filter_by(game_id=args.game_id, owner_game_player_id=player.game_player_id)
            .all()
        )
        if owned_assets:
            print("Owned assets:")
            for state in owned_assets:
                asset = session.query(models.Asset).get(state.asset_id)
                print(f"  - {asset.asset_type.title()} on {asset.space_id}")
        else:
            print("No owned assets.")
        if input("Proceed? (yes/no): ").lower() not in {"yes", "y"}:
            print("Aborted.")
            return

        # Release assets to bank
        for state in owned_assets:
            state.owner_game_player_id = None
            state.is_mortgaged = False
            state.improvement_level = 0
            state.has_hotel = False

        # Return retained cards
        (
            session.query(models.CardDraw)
            .filter(
                models.CardDraw.game_id == args.game_id,
                models.CardDraw.kept_by_player_id == player.game_player_id,
                models.CardDraw.discarded_at.is_(None),
            )
            .update(
                {
                    models.CardDraw.kept_by_player_id: None,
                    models.CardDraw.discarded_at: func.now(),
                },
                synchronize_session=False,
            )
        )

        # Zero out bank balance if positive (optional)
        ledger = LedgerService(session, args.game_id)
        balance = ledger.player_balance(player.game_player_id)
        if balance > 0:
            ledger.pay_bank(player, balance, "player_exit", turn_id=None)

        # Mark inactive
        player.is_active = False
        player.current_space_id = 0
        player.in_jail = False
        player.jail_turns = 0
        player.double_streak = 0

        session.commit()
        print(f"Player {player.player_name} retired and assets returned to bank.")        

def delete_game(args):
    confirm = input(f"Delete game {args.game_id}? This cannot be undone. (yes/no): ")
    if confirm.lower() not in {"yes", "y"}:
        print("Aborted.")
        return

    with get_session() as session:
        game_id = args.game_id

        # Remove rows that depend on this game
        session.query(models.CardDraw).filter_by(game_id=game_id).delete()
        session.query(models.JackpotLedger).filter_by(game_id=game_id).delete()
        session.query(models.Transaction).filter_by(game_id=game_id).delete()

        turn_ids = (
            session.query(models.Turn.turn_id)
            .filter(models.Turn.game_id == game_id)
            .subquery()
        )
        session.query(models.Movement).filter(models.Movement.turn_id.in_(turn_ids)).delete(synchronize_session=False)
        session.query(models.Turn).filter_by(game_id=game_id).delete()

        session.query(models.AssetState).filter_by(game_id=game_id).delete()
        session.query(models.GamePlayer).filter_by(game_id=game_id).delete()
        session.query(models.HouseRule).filter_by(game_id=game_id).delete()

        deleted = session.query(models.Game).filter_by(game_id=game_id).delete()

        session.commit()

        if deleted:
            print(f"Deleted game {game_id}.")
        else:        
            print(f"No game with id {game_id} found.")

def main():
    parser = argparse.ArgumentParser(description="Game CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_start = subparsers.add_parser("start-game")
    p_start.add_argument("--host-user-id", type=int, default=1)
    p_start.add_argument("--players", nargs="+", required=True)
    p_start.add_argument("--start-cash", type=int, default=20000)
    p_start.add_argument("--pass-bonus", type=int, default=2000)
    p_start.add_argument("--jackpot", type=int, default=1)
    p_start.set_defaults(func=start_game)

    p_next = subparsers.add_parser("next-turn")
    p_next.add_argument("--game-id", type=int, required=True)
    p_next.set_defaults(func=next_turn)

    p_board = subparsers.add_parser("show-board")
    p_board.add_argument("--game-id", type=int, required=True)
    p_board.set_defaults(func=show_board)

    p_ledger = subparsers.add_parser("ledger")
    p_ledger.add_argument("--game-id", type=int, required=True)
    p_ledger.set_defaults(func=ledger)

    p_save = subparsers.add_parser("save-game")
    p_save.add_argument("--game-id", type=int, required=True)
    p_save.set_defaults(func=save_game)

    p_list = subparsers.add_parser("list-players")
    p_list.add_argument("--game-id", type=int, required=True)
    p_list.set_defaults(func=list_players)

    p_delete = subparsers.add_parser("delete-game")
    p_delete.add_argument("--game-id", type=int, required=True)
    p_delete.set_defaults(func=delete_game)

    p_retire = subparsers.add_parser("retire-player")
    p_retire.add_argument("--game-id", type=int, required=True)
    p_retire.add_argument("--player-id", type=int, required=True, help="game_player_id (see list-players)")
    p_retire.set_defaults(func=retire_player)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()