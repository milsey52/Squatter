"""
Update all card effect codes and parameters based on card text.
This script properly configures all Chance and Welfare cards with their correct effects.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app import models
import json

def main():
    session: Session = SessionLocal()

    # Card configurations: (card_id, effect_code, effect_params)
    updates = [
        # Welfare Cards (1-16)
        (1, "COLLECT", {"amount": 2000}),  # Free room upgrade
        (2, "GO_TO_JAIL", None),  # Go to Jail
        (3, "PAY_REPAIRS", {"per_house": 500, "per_hotel": 1200}),  # Tax assessment
        (4, "COLLECT", {"amount": 250}),  # Cruise Swan River
        (5, "COLLECT", {"amount": 1000}),  # Samphire Lodge
        (6, "PAY_BANK", {"amount": 500}),  # Perth Zoo donation
        (7, "PAY_BANK", {"amount": 500}),  # Concert fine
        (8, "PAY_BANK", {"amount": 1000}),  # Littering fine
        (9, "COLLECT", {"amount": 1000}),  # Bell Tower voucher
        (10, "COLLECT", {"amount": 200}),  # Surfing competition
        (11, "COLLECT", {"amount": 2000}),  # Bank dividend
        (12, "GET_OUT_OF_JAIL", None),  # Get out of Jail
        (13, "COLLECT", {"amount": 100}),  # Ice-cream voucher
        (14, "COLLECT", {"amount": 2000}),  # UWA arts award
        (15, "COLLECT", {"amount": 500}),  # Fremantle Prison prize
        (16, "COLLECT_FROM_EACH_PLAYER", {"amount": 100}),  # Meal from every player

        # Chance Cards (17-32)
        (17, "ADVANCE_NEAREST_TRANSPORT", {"rent_multiplier": 2}),  # Nearest travel
        (18, "GET_OUT_OF_JAIL", None),  # Get out of Jail
        (19, "COLLECT", {"amount": 500}),  # Kings Park competition
        (20, "PAY_REPAIRS", {"per_house": 250, "per_hotel": 1250}),  # Tax repairs
        (21, "MOVE_TO", {"space_id": 39, "allow_pass_bonus": True}),  # Ride to Kings Park
        (22, "ADVANCE_NEAREST_UTILITY", {"rent_multiplier": 10}),  # Nearest utility (already fixed)
        (23, "MOVE_TO", {"space_id": 18, "allow_pass_bonus": True}),  # Adventure World
        (24, "MOVE_BACK", {"steps": -3}),  # Go back 3 spaces
        (25, "ADVANCE_NEAREST_TRANSPORT", {"rent_multiplier": 2}),  # Nearest travel (duplicate)
        (26, "MOVE_TO", {"space_id": 5, "allow_pass_bonus": True}),  # Transperth
        (27, "MOVE_TO", {"space_id": 24, "allow_pass_bonus": True}),  # Carrilon City
        (28, "COLLECT", {"amount": 500}),  # Bank dividend
        (29, "PAY_BANK", {"amount": 150}),  # Freo Markets
        (30, "PAY_EACH_PLAYER", {"amount": 500}),  # Loser of year
        (31, "MOVE_TO", {"space_id": 1, "collect_on_land": 2000}),  # Advance to Start
        (32, "GO_TO_JAIL", None),  # Go to Jail
    ]

    for card_id, effect_code, effect_params in updates:
        card = session.query(models.Card).filter_by(card_id=card_id).first()
        if card:
            card.effect_code = effect_code
            card.effect_params = json.dumps(effect_params) if effect_params else None
            print(f"Updated card {card_id}: {card.title[:50]} -> {effect_code}")
        else:
            print(f"Warning: Card {card_id} not found")

    session.commit()
    session.close()
    print("\nAll cards updated successfully!")

if __name__ == "__main__":
    main()
