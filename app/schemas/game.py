# /home/max/programs/MonopolyPerth/app/schemas/schemas.py
from pydantic import BaseModel
from typing import List, Optional

class PlayerCreate(BaseModel):
    name: str

class HouseRulesCreate(BaseModel):
    starting_cash: int = 20000
    pass_start_bonus: int = 2000
    jackpot_enabled: bool = True
    allow_auctions: bool = True
    allow_trading: bool = True  

class CreateGameRequest(BaseModel):
    host_user_id: int
    players: List[PlayerCreate]
    house_rules: HouseRulesCreate = HouseRulesCreate()

class PlayerSummary(BaseModel):
    game_player_id: int
    name: str
    turn_order: int
    current_space_id: int
    in_jail: bool
    balance: Optional[int] = None # optional helper field

class GameSummary(BaseModel):
    game_id: int
    status: str
    players: List[PlayerSummary]
    house_rules: HouseRulesCreate