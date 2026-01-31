import csv
import sys
import json
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app import models

FILES = {
    "welfare": Path("/home/max/programs/MonopolyPerth/data/WelfareCentreCards.csv"),
    "chance": Path("/home/max/programs/MonopolyPerth/data/Chance.csv"),
}

def parse_card_effect(text):
    """Parse card text to determine effect code and parameters."""
    text_lower = text.lower()

    # Get out of jail (retainable)
    if "get out of jail" in text_lower:
        return "GET_OUT_OF_JAIL", None

    # Go to jail
    if "go to jail" in text_lower:
        return "GO_TO_JAIL", None

    # Pay each player
    pay_each_match = re.search(r'pay each player \$?(\d+)', text_lower)
    if pay_each_match:
        amount = int(pay_each_match.group(1))
        return "PAY_EACH_PLAYER", json.dumps({"amount": amount})

    # Collect money (various patterns)
    collect_patterns = [
        r'collect \$?(\d+)',
        r'receive \$?(\d+)',
        r'pays you (?:a dividend of )?\$?(\d+)',
    ]
    for pattern in collect_patterns:
        collect_match = re.search(pattern, text_lower)
        if collect_match:
            amount = int(collect_match.group(1))
            return "COLLECT", json.dumps({"amount": amount})

    # Pay money to bank
    pay_match = re.search(r'pay \$?(\d+)', text_lower)
    if pay_match:
        amount = int(pay_match.group(1))
        return "PAY_BANK", json.dumps({"amount": amount})

    # Repairs (per house/hotel)
    if "per house" in text_lower and "per hotel" in text_lower:
        house_match = re.search(r'\$?(\d+)\s*(?:for )?(?:each )?per house', text_lower)
        hotel_match = re.search(r'\$?(\d+)\s*(?:for )?(?:each )?per hotel', text_lower)
        if house_match and hotel_match:
            return "PAY_REPAIRS", json.dumps({
                "per_house": int(house_match.group(1)),
                "per_hotel": int(hotel_match.group(1))
            })

    # Go back X spaces
    back_match = re.search(r'go back (\d+|three|two|one) space', text_lower)
    if back_match:
        num_map = {"one": 1, "two": 2, "three": 3}
        num_str = back_match.group(1)
        steps = num_map.get(num_str, int(num_str) if num_str.isdigit() else 1)
        return "MOVE_RELATIVE", json.dumps({"steps": -steps})

    # Check for nearest utility/travel first
    if "nearest utility" in text_lower:
        multiplier = 10 if "ten times" in text_lower else 1
        return "ADVANCE_NEAREST", json.dumps({
            "space_type": "utility",
            "rent_multiplier": multiplier
        })

    if "nearest travel" in text_lower:
        multiplier = 2 if "twice" in text_lower else 1
        return "ADVANCE_NEAREST", json.dumps({
            "space_type": "transport",
            "rent_multiplier": multiplier
        })

    # Advance to specific space (or take a trip/ride to)
    advance_keywords = ["advance to", "take", "ride to"]
    for keyword in advance_keywords:
        if keyword in text_lower:
            # Extract destination
            for space_name in ["kings park", "transperth", "adventure world"]:
                if space_name in text_lower:
                    collect_bonus = "pass" in text_lower and "collect" in text_lower
                    return "ADVANCE_TO", json.dumps({
                        "space_name": space_name.title(),
                        "collect_pass_bonus": collect_bonus
                    })
            break

    # Default: no effect
    return "NONE", None

def main():
    session: Session = SessionLocal()

    # Check if cards already exist
    existing_count = session.query(models.Card).count()
    if existing_count > 0:
        print(f"Updating {existing_count} existing cards...")
        # Update existing cards
        card_id = 1
        for deck_type, path in FILES.items():
            with path.open(newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                for row in reader:
                    text = row[0].strip()
                    if not text:
                        continue

                    effect_code, effect_params = parse_card_effect(text)

                    card = session.query(models.Card).get(card_id)
                    if card:
                        card.deck_type = deck_type
                        card.title = text[:80]  # Increase title length
                        card.body_text = text
                        card.is_retainable = 1 if effect_code == "GET_OUT_OF_JAIL" else 0
                        card.effect_code = effect_code
                        card.effect_params = effect_params
                        print(f"  Updated card {card_id}: {effect_code}")
                    card_id += 1
    else:
        # Insert new cards
        print("Inserting new cards...")
        for deck_type, path in FILES.items():
            with path.open(newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                for row in reader:
                    text = row[0].strip()
                    if not text:
                        continue

                    effect_code, effect_params = parse_card_effect(text)

                    card = models.Card(
                        deck_type=deck_type,
                        title=text[:80],
                        body_text=text,
                        is_retainable=1 if effect_code == "GET_OUT_OF_JAIL" else 0,
                        effect_code=effect_code,
                        effect_params=effect_params
                    )
                    session.add(card)
                    print(f"  Added card: {effect_code}")

    session.commit()
    session.close()
    print("Imported cards.")

if __name__ == "__main__":
    main()