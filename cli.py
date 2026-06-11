#!/usr/bin/env python
import argparse
import sys
import os
import uuid
import secrets
import string
from contextlib import contextmanager
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

# Set DATABASE_URL to PostgreSQL by default if not already set
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "postgresql:///squatter"
    print("Using default PostgreSQL database: postgresql:///squatter")
    print("Set DATABASE_URL environment variable to override.\n")

from app.db import SessionLocal
from app import models
from app.services.turn_manager import TurnManager
from app.services.seed import seed_asset_states
from app.services.ledger_service import LedgerService


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


def generate_game_code() -> str:
    """Generate a unique 6-character game code."""
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))

def start_game(args):
    with get_session() as session:
        # Create or get users for each player
        users = []
        for player_name in args.players:
            user = session.query(models.User).filter_by(display_name=player_name).first()
            if not user:
                user = models.User(display_name=player_name)
                session.add(user)
                session.flush()
            users.append(user)

        # First player is the host
        host_user = users[0]

        # Create game with game code
        game_code = generate_game_code()
        game = models.Game(
            host_user_id=host_user.user_id,
            game_code=game_code,
            status="in_progress",
            max_players=len(args.players)
        )
        session.add(game)
        session.flush()

        # Add house rules
        house_rules = models.HouseRule(
            game_id=game.game_id,
            starting_cash=args.start_cash,
            pass_start_bonus=args.pass_bonus,
            jackpot_enabled=args.jackpot,
        )
        session.add(house_rules)

        # Add players
        game_players = []
        for order, (user, name) in enumerate(zip(users, args.players), start=1):
            gp = models.GamePlayer(
                game_id=game.game_id,
                user_id=user.user_id,
                player_name=name,
                turn_order=order,
                current_board_index=0,
                in_jail=False,
                jail_turns=0,
                double_streak=0,
                is_ready=True,
                logged_in=True,
                is_active=True
            )
            session.add(gp)
            session.flush()
            game_players.append(gp)

            # Create session token for each player
            token = str(uuid.uuid4())
            game_session = models.GameSession(
                user_id=user.user_id,
                game_id=game.game_id,
                session_token=token,
                expires_at=datetime.now() + timedelta(days=7)
            )
            session.add(game_session)

        # Set first player as current player
        game.current_game_player_id = game_players[0].game_player_id

        # Seed asset states
        seed_asset_states(session, game.game_id)

        session.commit()

        print(f"Started game {game.game_id} (code: {game_code}) with players {', '.join(args.players)}")
        print("\nSession Tokens:")
        for user, name in zip(users, args.players):
            token_obj = session.query(models.GameSession).filter_by(
                user_id=user.user_id,
                game_id=game.game_id
            ).first()
            print(f"  {name}: {token_obj.session_token}")

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
                f"{p.player_name:10} | Space: {p.current_board_index:02} | "
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
                f"| space={p.current_board_index:02d} | {status}"
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
        player.current_board_index = 0
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

        # Remove rows that depend on this game (in correct order to avoid FK violations)

        # Delete pending actions
        session.query(models.PendingAction).filter_by(game_id=game_id).delete()

        # Get turn IDs for cascade deletion
        turn_ids = [
            t.turn_id for t in session.query(models.Turn.turn_id).filter(models.Turn.game_id == game_id).all()
        ]

        # Delete movements first (depends on turns)
        if turn_ids:
            session.query(models.Movement).filter(models.Movement.turn_id.in_(turn_ids)).delete(synchronize_session=False)

        # Delete card draws
        session.query(models.CardDraw).filter_by(game_id=game_id).delete()

        # Delete transactions and jackpot ledger (must happen before deleting turns)
        session.query(models.JackpotLedger).filter_by(game_id=game_id).delete()
        session.query(models.Transaction).filter_by(game_id=game_id).delete()

        # Delete turns (after transactions that reference them)
        session.query(models.Turn).filter_by(game_id=game_id).delete()

        # Delete asset states
        session.query(models.AssetState).filter_by(game_id=game_id).delete()

        # Delete turn order rolls
        session.query(models.TurnOrderRoll).filter_by(game_id=game_id).delete()

        # Delete trade sessions
        session.query(models.TradeSession).filter_by(game_id=game_id).delete()

        # Delete game sessions (authentication tokens)
        session.query(models.GameSession).filter_by(game_id=game_id).delete()

        # Clear current_game_player_id reference in games table before deleting players
        game = session.query(models.Game).filter_by(game_id=game_id).first()
        if game:
            game.current_game_player_id = None
            session.flush()

        # Delete game players
        session.query(models.GamePlayer).filter_by(game_id=game_id).delete()

        # Delete house rules
        session.query(models.HouseRule).filter_by(game_id=game_id).delete()

        # Finally delete the game itself
        deleted = session.query(models.Game).filter_by(game_id=game_id).delete()

        session.commit()

        if deleted:
            print(f"Deleted game {game_id} and all related data.")
        else:
            print(f"No game with id {game_id} found.")

def list_games(args):
    with get_session() as session:
        games = session.query(models.Game).order_by(models.Game.game_id.desc()).all()
        if not games:
            print("No games found.")
            return

        print(f"{'ID':<5} {'Code':<8} {'Status':<18} {'Players':<10} {'Host':<15}")
        print("-" * 70)
        for game in games:
            host = session.query(models.User).get(game.host_user_id)
            player_count = session.query(models.GamePlayer).filter_by(game_id=game.game_id).count()
            print(
                f"{game.game_id:<5} {game.game_code:<8} {game.status:<18} "
                f"{player_count}/{game.max_players:<8} {host.display_name if host else 'N/A':<15}"
            )


def show_game_status(args):
    with get_session() as session:
        game = get_game_or_exit(session, args.game_id)

        print(f"\n=== Game {game.game_id} ({game.game_code}) ===")
        print(f"Status: {game.status}")
        print(f"Max Players: {game.max_players}")

        host = session.query(models.User).get(game.host_user_id)
        print(f"Host: {host.display_name if host else 'N/A'}")

        if game.current_game_player_id:
            current_player = session.query(models.GamePlayer).get(game.current_game_player_id)
            print(f"Current Player: {current_player.player_name if current_player else 'N/A'}")

        print("\nPlayers:")
        players = (
            session.query(models.GamePlayer)
            .filter_by(game_id=game.game_id)
            .order_by(models.GamePlayer.turn_order)
            .all()
        )

        ledger = LedgerService(session, game.game_id)

        for p in players:
            balance = ledger.player_balance(p.game_player_id)
            status_flags = []
            if p.in_jail:
                status_flags.append(f"JAIL({p.jail_turns})")
            if not p.logged_in:
                status_flags.append("OFFLINE")
            if not p.is_active:
                status_flags.append("RETIRED")

            status_str = " ".join(status_flags) if status_flags else "OK"
            print(
                f"  {p.turn_order}. {p.player_name:<12} | Space: {p.current_board_index:02d} | "
                f"Balance: ${balance:>6} | {status_str}"
            )


def show_sessions(args):
    with get_session() as session:
        game = get_game_or_exit(session, args.game_id)

        sessions_query = (
            session.query(models.GameSession, models.User)
            .join(models.User, models.GameSession.user_id == models.User.user_id)
            .filter(models.GameSession.game_id == args.game_id)
            .all()
        )

        if not sessions_query:
            print("No active sessions for this game.")
            return

        print(f"\n=== Sessions for Game {game.game_id} ({game.game_code}) ===\n")
        print(f"{'User':<15} {'Token':<38} {'Expires':<20} {'Valid':<6}")
        print("-" * 85)

        for game_session, user in sessions_query:
            is_valid = game_session.expires_at > datetime.now()
            print(
                f"{user.display_name:<15} {game_session.session_token:<38} "
                f"{game_session.expires_at.strftime('%Y-%m-%d %H:%M'):<20} "
                f"{'Yes' if is_valid else 'No':<6}"
            )


def main():
    parser = argparse.ArgumentParser(description="Squatter Game CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_start = subparsers.add_parser("start-game", help="Start a new game (first player is host)")
    p_start.add_argument("--players", nargs="+", required=True, help="Player names (first is host)")
    p_start.add_argument("--start-cash", type=int, default=20000, help="Starting cash per player")
    p_start.add_argument("--pass-bonus", type=int, default=2000, help="Pass start bonus")
    p_start.add_argument("--jackpot", type=int, default=1, help="Enable jackpot (1=yes, 0=no)")
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

    p_list_games = subparsers.add_parser("list-games", help="List all games")
    p_list_games.set_defaults(func=list_games)

    p_status = subparsers.add_parser("game-status", help="Show detailed game status")
    p_status.add_argument("--game-id", type=int, required=True)
    p_status.set_defaults(func=show_game_status)

    p_sessions = subparsers.add_parser("show-sessions", help="Show active sessions for a game")
    p_sessions.add_argument("--game-id", type=int, required=True)
    p_sessions.set_defaults(func=show_sessions)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()