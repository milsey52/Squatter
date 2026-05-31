# app/api/routes/games.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import alias
from app.api.deps import get_session
from app.api import deps, auth
from app import models
from app.services.ledger_service import LedgerService
from app.services.station_service import StationService

router = APIRouter()


@router.get("/{game_id}")
def get_game(game_id: int, session: Session = Depends(get_session)):
    game = session.query(models.Game).filter_by(game_id=game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    players = (
        session.query(models.GamePlayer)
        .filter_by(game_id=game_id)
        .order_by(models.GamePlayer.turn_order)
        .all()
    )

    current_player_id = game.current_game_player_id
    if not current_player_id and players:
        current_player_id = players[0].game_player_id

    # Get game rules
    rules = session.query(models.GameRule).filter_by(game_id=game_id).first()

    return {
        "game_id": game.game_id,
        "status": game.status,
        "current_player_id": current_player_id,
        "game_rules": {
            "starting_cash": rules.starting_cash if rules else 2000,
            "quick_game": rules.quick_game if rules else False,
            "allow_trading": rules.allow_trading if rules else True,
        } if rules else None,
        "players": [
            {
                "game_player_id": p.game_player_id,
                "user_id": p.user_id,
                "player_name": p.player_name,
                "current_space_id": p.current_space_id,
                "visiting_town_turns": p.visiting_town_turns,
                "is_in_drought": p.is_in_drought,
                "drought_spaces_remaining": p.drought_spaces_remaining,
                "has_haystack": p.has_haystack,
                "turn_order": p.turn_order,
                "is_active": p.is_active,
                "is_ai": bool(p.is_ai),
                "ai_difficulty": p.ai_difficulty,
            }
            for p in players
        ],
    }


@router.get("/{game_id}/player_balances")
def player_balances(game_id: int, session: Session = Depends(get_session)):
    players = session.query(models.GamePlayer).filter_by(game_id=game_id).all()
    balances = {}
    for p in players:
        balance = LedgerService(session, game_id).player_balance(p.game_player_id)
        balances[p.game_player_id] = balance
    return balances


@router.get("/{game_id}/stations")
def get_all_stations(game_id: int, session: Session = Depends(get_session)):
    """Get station summaries for all players."""
    deps.get_game_or_404(game_id, session)
    station_svc = StationService(session, game_id)

    players = session.query(models.GamePlayer).filter_by(game_id=game_id).all()
    stations = {}
    for p in players:
        stations[p.game_player_id] = station_svc.get_station_summary(p.game_player_id)
    return stations


@router.get("/{game_id}/stations/{player_id}")
def get_player_station(game_id: int, player_id: int, session: Session = Depends(get_session)):
    """Get a specific player's station summary."""
    deps.get_game_or_404(game_id, session)
    station_svc = StationService(session, game_id)
    return station_svc.get_station_summary(player_id)


@router.get("/{game_id}/stud-rams")
def get_stud_ram_states(game_id: int, session: Session = Depends(get_session)):
    """Get stud ram ownership states."""
    deps.get_game_or_404(game_id, session)

    rams = (
        session.query(models.StudRamState, models.Space)
        .join(models.Space, models.StudRamState.space_id == models.Space.space_id)
        .filter(models.StudRamState.game_id == game_id)
        .all()
    )

    return [
        {
            "space_id": ram.space_id,
            "space_name": space.name,
            "board_index": space.board_index,
            "owner_game_player_id": ram.owner_game_player_id,
            "is_available": ram.is_available,
            "stud_fee": space.stud_fee,
            "purchase_price": space.purchase_price,
        }
        for ram, space in rams
    ]


@router.get("/{game_id}/players/{player_id}/holdings")
def get_player_holdings(game_id: int, player_id: int, session: Session = Depends(get_session)):
    """Cards retained by a player + active state flags + stud rams owned."""
    deps.get_game_or_404(game_id, session)

    player = (
        session.query(models.GamePlayer)
        .filter_by(game_id=game_id, game_player_id=player_id)
        .first()
    )
    if not player:
        raise HTTPException(status_code=404, detail="Player not found in this game")

    retained = (
        session.query(models.CardDraw, models.Card)
        .join(models.Card, models.CardDraw.card_id == models.Card.card_id)
        .filter(
            models.CardDraw.game_id == game_id,
            models.CardDraw.kept_by_player_id == player_id,
            models.CardDraw.discarded_at.is_(None),
        )
        .order_by(models.CardDraw.draw_order)
        .all()
    )

    rams = (
        session.query(models.StudRamState, models.Space)
        .join(models.Space, models.StudRamState.space_id == models.Space.space_id)
        .filter(
            models.StudRamState.game_id == game_id,
            models.StudRamState.owner_game_player_id == player_id,
        )
        .all()
    )

    paddocks = (
        session.query(models.Paddock)
        .filter_by(game_id=game_id, owner_game_player_id=player_id)
        .order_by(models.Paddock.paddock_number)
        .all()
    )

    return {
        "player_id": player_id,
        "cards": [
            {
                "card_draw_id": d.card_draw_id,
                "card_id": c.card_id,
                "deck_type": c.deck_type,
                "title": c.title,
                "body_text": c.body_text,
                "effect_code": c.effect_code,
            }
            for d, c in retained
        ],
        "stud_rams": [
            {
                "space_id": ram.space_id,
                "space_name": space.name,
                "board_index": space.board_index,
                "stud_fee": space.stud_fee,
            }
            for ram, space in rams
        ],
        "paddocks": [
            {
                "paddock_number": p.paddock_number,
                "paddock_type": p.paddock_type,
                "sheep_pens": p.sheep_pens,
                "max_pens": p.max_pens,
                "is_mortgaged": p.is_mortgaged,
            }
            for p in paddocks
        ],
        "states": {
            "has_haystack": player.has_haystack,
            "haystack_used": player.haystack_used,
            "footrot_immune": player.footrot_immune,
            "is_in_drought": player.is_in_drought,
            "drought_spaces_remaining": player.drought_spaces_remaining,
            "restock_blocked_until_circuit": player.restock_blocked_until_circuit,
            "restock_block_spaces_remaining": player.restock_block_spaces_remaining,
            "next_drought_halved": player.next_drought_halved,
            "next_sell_price_modifier": player.next_sell_price_modifier,
            "wool_cheque_bonus": player.wool_cheque_bonus,
            "visiting_town_turns": player.visiting_town_turns,
        },
    }


@router.get("/{game_id}/dice_rolls")
def get_dice_rolls(game_id: int, session: Session = Depends(get_session)):
    """Get history of dice rolls for a game."""
    game = session.query(models.Game).filter_by(game_id=game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    space_from = alias(models.Space.__table__, name='space_from')
    space_to = alias(models.Space.__table__, name='space_to')

    rolls = (
        session.query(
            models.Turn.turn_number,
            models.GamePlayer.player_name,
            models.GamePlayer.game_player_id,
            models.Turn.dice_roll_1,
            models.Turn.dice_roll_2,
            models.Turn.is_double,
            space_from.c.board_index.label('from_location'),
            space_to.c.board_index.label('to_location')
        )
        .join(models.GamePlayer, models.Turn.active_game_player_id == models.GamePlayer.game_player_id)
        .outerjoin(
            models.Movement,
            (models.Turn.turn_id == models.Movement.turn_id) &
            (models.Movement.movement_type == 'roll')
        )
        .outerjoin(space_from, models.Movement.start_space_id == space_from.c.space_id)
        .outerjoin(space_to, models.Movement.end_space_id == space_to.c.space_id)
        .filter(models.Turn.game_id == game_id)
        .order_by(models.Turn.turn_number.desc())
        .limit(20)
        .all()
    )

    result = []
    for turn_number, player_name, game_player_id, dice1, dice2, is_double, from_location, to_location in rolls:
        result.append({
            "roll_number": turn_number,
            "player": player_name,
            "player_id": game_player_id,
            "dice1": dice1,
            "dice2": dice2,
            "total": (dice1 or 0) + (dice2 or 0),
            "is_double": is_double or False,
            "from_location": from_location,
            "to_location": to_location
        })

    return {"rolls": result}
