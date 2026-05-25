"""Seed static data (spaces, stock_cards, tucker_bag cards) from CSV files.

Run on startup to ensure the database has the required game data.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from app.db import SessionLocal

DATA_DIR = ROOT / "data"


def _parse_dollar(val):
    """Parse a dollar string like '$500.00' or '$20/pen' into an integer."""
    if not val or not val.strip():
        return None
    val = val.strip().replace("$", "").replace(",", "")
    if "/pen" in val.lower():
        val = val.lower().replace("/pen", "")
    try:
        return int(float(val))
    except ValueError:
        return None


def _action_to_space_type(action, name, season, purchase_price):
    """Map the Action column from CSV to a space_type value."""
    if purchase_price:
        return "stud_ram"

    action_map = {
        "Wool Cheque": "wool_sale",
        "Stock Sale": "stock_sale",
        "Tucker Bag": "tucker_bag",
        "Miss Two Turns": "visiting_town",
        "Bore Dries Up": "bore_dries_up",
        "Local Drought": "local_drought",
        "Local Rain": "local_rain",
        "Flood Damage": "flood_damage",
        "Stud Ram Dies": "stud_ram_dies",
    }

    if action in action_map:
        return action_map[action]

    # Expense spaces (have costs or card benefit costs)
    return "expense"


def seed_spaces(session):
    count = session.execute(text("SELECT COUNT(*) FROM spaces")).scalar()
    if count > 0:
        print(f"  spaces already has {count} rows, skipping.")
        return

    csv_path = DATA_DIR / "Properties.csv"
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        spaces = []
        for row in reader:
            idx = int(row["Index"])
            name = row["Space Name"].strip()
            season = row["Season"].strip() if row["Season"].strip() else None
            action = row["Action"].strip() if row["Action"].strip() else None

            cost_per_pen = _parse_dollar(row.get("No Card – Rate per Pen", ""))
            cost_flat = _parse_dollar(row.get("No Card – Single Payment", ""))
            cost_per_pen_with_card = _parse_dollar(row.get("Card Benefit – Rate per Pen", ""))
            cost_flat_with_card = _parse_dollar(row.get("Card Benefit – Single Payment", ""))
            relevant_card_name = row.get("Card", "").strip() or None

            # Spaces 21 and 37: the "Card Benefit" cost IS the mandatory cost;
            # holding the card grants immunity (pay nothing)
            if idx in (21, 37) and not cost_flat and cost_flat_with_card:
                cost_flat = cost_flat_with_card
                cost_flat_with_card = None

            purchase_price = _parse_dollar(row.get("Purchase", ""))
            sell_back_price = _parse_dollar(row.get("Mortgage", ""))
            stud_fee = _parse_dollar(row.get("Rent", ""))

            space_type = _action_to_space_type(action, name, season, purchase_price)

            spaces.append({
                "space_id": idx + 1,
                "board_index": idx,
                "name": name,
                "space_type": space_type,
                "season": season,
                "cost_per_pen": cost_per_pen,
                "cost_flat": cost_flat,
                "cost_per_pen_with_card": cost_per_pen_with_card,
                "cost_flat_with_card": cost_flat_with_card,
                "relevant_card_name": relevant_card_name,
                "purchase_price": purchase_price,
                "sell_back_price": sell_back_price,
                "stud_fee": stud_fee,
            })

    for s in spaces:
        session.execute(text(
            "INSERT INTO spaces (space_id, board_index, name, space_type, season, "
            "cost_per_pen, cost_flat, cost_per_pen_with_card, cost_flat_with_card, "
            "relevant_card_name, purchase_price, sell_back_price, stud_fee) "
            "VALUES (:space_id, :board_index, :name, :space_type, :season, "
            ":cost_per_pen, :cost_flat, :cost_per_pen_with_card, :cost_flat_with_card, "
            ":relevant_card_name, :purchase_price, :sell_back_price, :stud_fee)"
        ), s)

    # Reset sequence
    session.execute(text(
        "SELECT setval('spaces_space_id_seq', (SELECT MAX(space_id) FROM spaces))"
    ))
    session.commit()
    print(f"  Seeded {len(spaces)} spaces.")


def seed_stock_cards(session):
    count = session.execute(text("SELECT COUNT(*) FROM stock_cards")).scalar()
    if count > 0:
        print(f"  stock_cards already has {count} rows, skipping.")
        return

    csv_path = DATA_DIR / "Stock Cards.csv"
    cards = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        # Skip header rows (3 rows: header, sub-header, blank)
        next(reader)  # "Buyer (price per pen),Seller (price per pen,"
        next(reader)  # ",Natural Pasture,Improved and Irrigated Pasture"
        next(reader)  # blank row

        card_id = 1
        for row in reader:
            if not row or not row[0].strip() or row[0].strip().lower() == "reg":
                continue
            try:
                buy_price = int(row[0].strip())
                sell_natural = int(row[1].strip())
                sell_improved = int(row[2].strip())
            except (ValueError, IndexError):
                continue

            cards.append({
                "stock_card_id": card_id,
                "buy_price_per_pen": buy_price,
                "sell_price_natural": sell_natural,
                "sell_price_improved_irrigated": sell_improved,
            })
            card_id += 1

    for c in cards:
        session.execute(text(
            "INSERT INTO stock_cards (stock_card_id, buy_price_per_pen, "
            "sell_price_natural, sell_price_improved_irrigated) "
            "VALUES (:stock_card_id, :buy_price_per_pen, "
            ":sell_price_natural, :sell_price_improved_irrigated)"
        ), c)

    session.execute(text(
        "SELECT setval('stock_cards_stock_card_id_seq', (SELECT MAX(stock_card_id) FROM stock_cards))"
    ))
    session.commit()
    print(f"  Seeded {len(cards)} stock cards.")


def seed_tucker_bag_cards(session):
    count = session.execute(text("SELECT COUNT(*) FROM cards")).scalar()
    if count > 0:
        print(f"  cards already has {count} rows, skipping.")
        return

    csv_path = DATA_DIR / "Tucker Bag.csv"
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        lines = [row[0].strip() for row in reader if row and row[0].strip()]

    # Map each card to effect_code and effect_params
    card_defs = [
        {
            "title": "Fire Destroys Haystack",
            "effect_code": "FIRE_DAMAGE",
            "effect_params": {"cost": 500, "protection_card": "Fire Fighting Equipment"},
            "is_retainable": False,
        },
        {
            "title": "Income Tax Assessment",
            "effect_code": "INCOME_TAX",
            "effect_params": {
                "per_natural_paddock": 50,
                "per_improved_paddock": 200,
                "per_irrigated_paddock": 500,
                "per_pen": 100,
                "per_1000_cash": 200,
            },
            "is_retainable": False,
        },
        {
            "title": "Good Autumn and Spring Rains",
            "effect_code": "MOVE_TO_WOOL_SALE",
            "effect_params": {"breaks_drought": True},
            "is_retainable": False,
        },
        {
            "title": "Lucerne Flea Infestation",
            "effect_code": "LUCERNE_FLEA",
            "effect_params": {
                "sell_fraction": 0.333,
                "sell_price_per_pen": 500,
                "restock_blocked": True,
                "protection_card": "Control of Weeds and Insects",
            },
            "is_retainable": False,
        },
        {
            "title": "Fire Fighting Equipment",
            "effect_code": "FIRE_FIGHTING_EQUIPMENT",
            "effect_params": {"purchase_price": 350},
            "is_retainable": True,
        },
        {
            "title": "General Rain",
            "effect_code": "GENERAL_RAIN",
            "effect_params": {},
            "is_retainable": False,
        },
        {
            "title": "Soil Conservation Trophy",
            "effect_code": "COLLECT",
            "effect_params": {"amount": 600},
            "is_retainable": False,
        },
        {
            "title": "Tractor Injury",
            "effect_code": "MISS_TURNS",
            "effect_params": {"turns": 2},
            "is_retainable": False,
        },
        {
            "title": "Worm Infestation",
            "effect_code": "WORM_INFESTATION",
            "effect_params": {
                "sell_fraction": 0.5,
                "sell_price_per_pen": 500,
                "protection_card": "Worm Control Program",
            },
            "is_retainable": False,
        },
        {
            "title": "Local Rain",
            "effect_code": "LOCAL_RAIN",
            "effect_params": {},
            "is_retainable": False,
        },
        {
            "title": "Successful Lambing Season",
            "effect_code": "SUCCESSFUL_LAMBING",
            "effect_params": {"pens": 3, "cash_if_full": 1800},
            "is_retainable": False,
        },
        {
            "title": "Fire-Safe Award",
            "effect_code": "COLLECT",
            "effect_params": {"amount": 400},
            "is_retainable": False,
        },
        {
            "title": "Sustainable Grazing Prize",
            "effect_code": "COLLECT",
            "effect_params": {"amount": 300},
            "is_retainable": False,
        },
        {
            "title": "Stud Ewe National Award",
            "effect_code": "COLLECT",
            "effect_params": {"amount": 500},
            "is_retainable": False,
        },
        {
            "title": "Landcare and Tree Planting",
            "effect_code": "RECEIVE_PENS_AND_BONUS",
            "effect_params": {"pens": 2, "cash_if_full": 1200, "wool_cheque_bonus": 1000},
            "is_retainable": False,
        },
        {
            "title": "Sustainable Water Management",
            "effect_code": "SUSTAINABLE_WATER",
            "effect_params": {"drought_halved_spaces": 22},
            "is_retainable": False,
        },
        {
            "title": "Grass Fire",
            "effect_code": "GRASS_FIRE",
            "effect_params": {
                "sell_fraction": 0.5,
                "restock_blocked": True,
                "protection_card": "Fire Fighting Equipment",
            },
            "is_retainable": False,
        },
        {
            "title": "Blowfly Wave",
            "effect_code": "BLOWFLY_WAVE",
            "effect_params": {"wool_reduction_pct": 10},
            "is_retainable": False,
        },
        {
            "title": "Fat Lamb Sale",
            "effect_code": "COLLECT",
            "effect_params": {"amount": 500},
            "is_retainable": False,
        },
        {
            "title": "High Stock Prices",
            "effect_code": "HIGH_STOCK_PRICES",
            "effect_params": {"price_modifier_pct": 20},
            "is_retainable": True,
        },
        {
            "title": "Eradicate Footrot",
            "effect_code": "ERADICATE_FOOTROT",
            "effect_params": {},
            "is_retainable": False,
        },
        {
            "title": "Special Sheep Sale",
            "effect_code": "MOVE_TO_STOCK_SALE",
            "effect_params": {},
            "is_retainable": False,
        },
        {
            "title": "Stud Ram Insurance",
            "effect_code": "STUD_RAM_INSURANCE",
            "effect_params": {"refund": 500},
            "is_retainable": True,
        },
        {
            "title": "Agistment Fees",
            "effect_code": "AGISTMENT_FEES",
            "effect_params": {"amount": 600},
            "is_retainable": False,
        },
        {
            "title": "Superfine Wool",
            "effect_code": "SUPERFINE_WOOL",
            "effect_params": {"wool_cheque_bonus": 3000},
            "is_retainable": False,
        },
        {
            "title": "Drought",
            "effect_code": "DROUGHT",
            "effect_params": {},
            "is_retainable": False,
        },
        {
            "title": "Drought on ALL Stations",
            "effect_code": "DROUGHT_ALL_STATIONS",
            "effect_params": {},
            "is_retainable": False,
        },
    ]

    if len(card_defs) != len(lines):
        print(f"  WARNING: {len(card_defs)} card definitions but {len(lines)} CSV lines")

    for i, (card_def, body_text) in enumerate(zip(card_defs, lines), start=1):
        session.execute(text(
            "INSERT INTO cards (card_id, deck_type, title, body_text, "
            "is_retainable, effect_code, effect_params) "
            "VALUES (:card_id, :deck_type, :title, :body_text, "
            ":is_retainable, :effect_code, :effect_params)"
        ), {
            "card_id": i,
            "deck_type": "tucker_bag",
            "title": card_def["title"],
            "body_text": body_text,
            "is_retainable": card_def["is_retainable"],
            "effect_code": card_def["effect_code"],
            "effect_params": json.dumps(card_def["effect_params"]),
        })

    session.execute(text(
        "SELECT setval('cards_card_id_seq', (SELECT MAX(card_id) FROM cards))"
    ))
    session.commit()
    print(f"  Seeded {len(card_defs)} Tucker Bag cards.")


def seed_expense_cards(session):
    """Seed purchasable expense-immunity cards (not part of Tucker Bag deck)."""
    # These cards can only be obtained by paying extra at certain expense spaces.
    # They grant immunity from future landings on the same space.
    expense_cards = [
        {
            "title": "Worm Control Program",
            "body_text": "Immunity from Drench Sheep for Worms expense.",
            "effect_code": "EXPENSE_IMMUNITY",
            "effect_params": json.dumps({"immune_space": "Drench Sheep for Worms"}),
        },
        {
            "title": "Control of Weeds and Insects",
            "body_text": "Immunity from Spray for Weeds & Insects expense.",
            "effect_code": "EXPENSE_IMMUNITY",
            "effect_params": json.dumps({"immune_space": "Spray for Weeds & Insects"}),
        },
        {
            "title": "Fertilised Pasture",
            "body_text": "Immunity from Fertilising Pasture expense.",
            "effect_code": "EXPENSE_IMMUNITY",
            "effect_params": json.dumps({"immune_space": "Fertilising Pasture"}),
        },
    ]

    existing = session.execute(
        text("SELECT title FROM cards WHERE deck_type = 'expense_immunity'")
    ).fetchall()
    existing_titles = {r[0] for r in existing}

    added = 0
    for card_def in expense_cards:
        if card_def["title"] in existing_titles:
            continue
        session.execute(text(
            "INSERT INTO cards (deck_type, title, body_text, "
            "is_retainable, effect_code, effect_params) "
            "VALUES (:deck_type, :title, :body_text, "
            ":is_retainable, :effect_code, :effect_params)"
        ), {
            "deck_type": "expense_immunity",
            "title": card_def["title"],
            "body_text": card_def["body_text"],
            "is_retainable": True,
            "effect_code": card_def["effect_code"],
            "effect_params": card_def["effect_params"],
        })
        added += 1

    if added > 0:
        session.commit()
        print(f"  Seeded {added} expense immunity cards.")
    else:
        print("  Expense immunity cards already exist, skipping.")


if __name__ == "__main__":
    session = SessionLocal()
    try:
        print("Seeding static data...")
        seed_spaces(session)
        seed_stock_cards(session)
        seed_tucker_bag_cards(session)
        seed_expense_cards(session)
        print("Done.")
    finally:
        session.close()
