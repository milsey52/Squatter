# app/schemas/game.py
from pydantic import BaseModel
from typing import List, Optional


class PlayerCreate(BaseModel):
    name: str


class GameRulesCreate(BaseModel):
    starting_cash: int = 2000
    quick_game: bool = False
    starting_paddock_type: str = "natural"
    allow_trading: bool = True


class CreateGameRequest(BaseModel):
    host_user_id: int
    players: List[PlayerCreate]
    game_rules: GameRulesCreate = GameRulesCreate()


class PlayerSummary(BaseModel):
    game_player_id: int
    name: str
    turn_order: int
    current_board_index: int
    visiting_town_turns: int = 0
    is_in_drought: bool = False
    balance: Optional[int] = None


class GameSummary(BaseModel):
    game_id: int
    status: str
    players: List[PlayerSummary]
    game_rules: GameRulesCreate
