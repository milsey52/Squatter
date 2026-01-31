import csv
from pathlib import Path
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app import models

CSV_FILE = Path("/home/max/programs/MonopolyPerth/data/Properties.csv")

SPACE_TYPE_MAP = {
    "start": "start",
    "start/payday": "start",
    "chance": "chance",
    "welfare centre": "welfare",
    "income tax": "penalty",
    "mortgage payment": "penalty",
    "visit jail": "rest",
    "salvo rest home": "rest",
    "police arrest": "penalty",
    "imprisonment": "penalty",
}

TRANSPORT_NAMES = {"TransPerth","Warwick Train Station","Rottnest Express","Perth Airport"}
UTILITY_NAMES = {"Synergy","Alinta Gas"}

def detect_space_type(name: str) -> str:
    n = name.strip().lower()
    for key, val in SPACE_TYPE_MAP.items():
        if key in n:
            return val
    if name in TRANSPORT_NAMES:
        return "transport"
    if name in UTILITY_NAMES:
        return "utility"
    return "property"

def parse_money(value: str):
    if not value:
        return None
    s = value.replace("$", "").replace(",", "").strip()
    if not s:
        return None
    return int(float(s))

def main():
    session: Session = SessionLocal()

    spaces = []
    assets = []

    with CSV_FILE.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)

        for row in reader:
            if not row or not row[0].strip():
                continue
            idx = int(row[0])
            name = row[1].strip()
            sale_price = parse_money(row[2])
            rent1 = parse_money(row[3])
            rent2 = parse_money(row[4])
            rent3 = parse_money(row[5])
            rent4 = parse_money(row[6])
            house1 = parse_money(row[7])
            house2 = parse_money(row[8])
            house3 = parse_money(row[9])
            house4 = parse_money(row[10])
            hotel = parse_money(row[11])
            mortgage = parse_money(row[12])

            space = models.Space(
                space_id=idx,
                board_index=idx,
                name=name,
                space_type=detect_space_type(name),
            )
            spaces.append(space)

            if sale_price:
                asset = models.Asset(
                    space_id=idx,
                    asset_type=detect_space_type(name) if detect_space_type(name) != "property" else "property",
                    purchase_price=sale_price,
                    mortgage_value=mortgage or 0,
                    rent_base=rent1,
                    rent_group=rent2,
                    rent_house_1=house1,
                    rent_house_2=house2,
                    rent_house_3=house3,
                    rent_house_4=house4,
                    rent_hotel=hotel,
                    rent_tier_2=rent2 if name in TRANSPORT_NAMES else None,
                    rent_tier_3=rent3 if name in TRANSPORT_NAMES else None,
                    rent_tier_4=rent4 if name in TRANSPORT_NAMES else None,
                    utility_mult_single=5 if name in UTILITY_NAMES else None,
                    utility_mult_double=15 if name in UTILITY_NAMES else None,
                )
                assets.append(asset)

    # Insert spaces first to satisfy foreign key constraints
    session.add_all(spaces)
    session.commit()

    # Then insert assets
    session.add_all(assets)
    session.commit()

    session.close()
    print("Imported properties & spaces.")

if __name__ == "__main__":
    main()