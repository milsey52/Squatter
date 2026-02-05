"""Seed static data (spaces, assets, cards, property_groups) if tables are empty.

Run this on startup to ensure Railway PostgreSQL has the required game data.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from app.db import SessionLocal


def seed_property_groups(session):
    count = session.execute(text("SELECT COUNT(*) FROM property_groups")).scalar()
    if count > 0:
        print(f"  property_groups already has {count} rows, skipping.")
        return

    groups = [
        (1, 'Dark Blue', '#00008B', 500, 500),
        (2, 'Brown', '#8B4513', 500, 500),
        (3, 'Light Blue', '#87CEEB', 500, 500),
        (4, 'Pink', '#FF1493', 500, 500),
        (5, 'Orange', '#FFA500', 500, 500),
        (6, 'Red', '#FF0000', 500, 500),
        (7, 'Yellow', '#FFFF00', 500, 500),
        (8, 'Green', '#00FF00', 500, 500),
    ]
    for g in groups:
        session.execute(text(
            "INSERT INTO property_groups (group_id, group_name, color_hex, house_cost, hotel_cost) "
            "VALUES (:gid, :name, :color, :house, :hotel)"
        ), {"gid": g[0], "name": g[1], "color": g[2], "house": g[3], "hotel": g[4]})
    session.commit()
    print(f"  Seeded {len(groups)} property groups.")


def seed_spaces(session):
    count = session.execute(text("SELECT COUNT(*) FROM spaces")).scalar()
    if count > 0:
        print(f"  spaces already has {count} rows, skipping.")
        return

    # (space_id, board_index, name, space_type, group_id_or_None)
    spaces = [
        (1, 0, 'Start/Payday', 'start', None),
        (2, 1, 'Belvue House', 'property', 2),
        (3, 2, 'Balga Inn', 'property', 2),
        (4, 3, 'Welfare Centre', 'welfare', None),
        (5, 4, 'Income Tax', 'penalty', None),
        (6, 5, 'TransPerth', 'transport', None),
        (7, 6, 'Ascot Waters', 'property', 3),
        (8, 7, 'Midland', 'property', 3),
        (9, 8, 'Chance', 'chance', None),
        (10, 9, 'Swan Vinyard', 'property', 3),
        (11, 10, 'Visit Jail', 'rest', None),
        (12, 11, 'Optus Stadiium', 'property', 4),
        (13, 12, 'Synergy', 'utility', None),
        (14, 13, 'WACA', 'property', 4),
        (15, 14, 'Perth Arena', 'property', 4),
        (16, 15, 'Warwick Train Station', 'transport', None),
        (17, 16, 'Hilliarys Boat Harbour', 'property', 5),
        (18, 17, 'Water World', 'property', 5),
        (19, 18, 'Adventure World', 'property', 5),
        (20, 19, 'Welfare Centre', 'welfare', None),
        (21, 20, 'Salvo Rest Home', 'rest', None),
        (22, 21, 'Whitfords Shopping Centre', 'property', 6),
        (23, 22, 'Cannington Shopping Centre', 'property', 6),
        (24, 23, 'Chance', 'chance', None),
        (25, 24, 'Carrilon City', 'property', 6),
        (26, 25, 'Rottnest Express', 'transport', None),
        (27, 26, 'Rottnest Island', 'property', 7),
        (28, 27, 'Alinta Gas', 'utility', None),
        (29, 28, 'City Beach', 'property', 7),
        (30, 29, 'Yanchep Beach', 'property', 7),
        (31, 30, 'Police Arrest \u2013 Imprisonment', 'penalty', None),
        (32, 31, 'Perth Zoo', 'property', 8),
        (33, 32, 'Welfare Centre', 'welfare', None),
        (34, 33, 'Curtin Uni', 'property', 8),
        (35, 34, 'The Casino', 'property', 8),
        (36, 35, 'Perth Airport', 'transport', None),
        (37, 36, 'Chance', 'chance', None),
        (38, 37, 'Nedlands', 'property', 1),
        (39, 38, 'Mortgage Payment', 'penalty', None),
        (40, 39, 'Kings Park', 'property', 1),
    ]
    for s in spaces:
        session.execute(text(
            "INSERT INTO spaces (space_id, board_index, name, space_type, group_id) "
            "VALUES (:sid, :bidx, :name, :stype, :gid)"
        ), {"sid": s[0], "bidx": s[1], "name": s[2], "stype": s[3], "gid": s[4]})

    # Reset the sequence for PostgreSQL so next auto-generated id is correct
    session.execute(text("SELECT setval('spaces_space_id_seq', (SELECT MAX(space_id) FROM spaces))"))
    session.commit()
    print(f"  Seeded {len(spaces)} spaces.")


def seed_assets(session):
    count = session.execute(text("SELECT COUNT(*) FROM assets")).scalar()
    if count > 0:
        print(f"  assets already has {count} rows, skipping.")
        return

    # (asset_id, space_id, asset_type, purchase_price, mortgage_value,
    #  rent_base, rent_group, rent_house_1, rent_house_2, rent_house_3, rent_house_4, rent_hotel,
    #  rent_tier_2, rent_tier_3, rent_tier_4, utility_mult_single, utility_mult_double)
    assets = [
        (1, 1, 'start', 2000, 0, None, None, None, None, None, None, None, None, None, None, None, None),
        (2, 2, 'property', 600, 300, 36, 72, 180, 540, 1620, 3240, 4500, None, None, None, None, None),
        (3, 3, 'property', 600, 300, 36, 72, 180, 540, 1620, 3240, 4500, None, None, None, None, None),
        (4, 5, 'penalty', -2000, -1000, None, None, None, None, None, None, None, None, None, None, None, None),
        (5, 6, 'transport', 2000, 1000, 250, 500, None, None, None, None, None, 500, 1000, 2000, None, None),
        (6, 7, 'property', 1000, 500, 70, 140, 350, 1050, 3150, 6300, 8750, None, None, None, None, None),
        (7, 8, 'property', 1000, 500, 70, 140, 350, 1050, 3150, 6300, 8750, None, None, None, None, None),
        (8, 10, 'property', 1200, 600, 84, 168, 420, 1260, 3780, 7560, 10500, None, None, None, None, None),
        (9, 12, 'property', 1400, 700, 112, 224, 560, 1680, 5040, 10080, 14000, None, None, None, None, None),
        (10, 13, 'utility', 1500, 750, 5, 15, None, None, None, None, None, None, None, None, 5, 15),
        (11, 14, 'property', 1400, 700, 112, 224, 560, 1680, 5040, 10080, 14000, None, None, None, None, None),
        (12, 15, 'property', 1600, 800, 128, 256, 640, 1920, 5760, 11520, 16000, None, None, None, None, None),
        (13, 16, 'transport', 2000, 1000, 250, 500, None, None, None, None, None, 500, 1000, 2000, None, None),
        (14, 17, 'property', 1800, 900, 144, 288, 720, 2160, 6480, 12960, 18000, None, None, None, None, None),
        (15, 18, 'property', 1800, 900, 144, 288, 720, 2160, 6480, 12960, 18000, None, None, None, None, None),
        (16, 19, 'property', 2000, 1000, 160, 320, 800, 2400, 7200, 14400, 20000, None, None, None, None, None),
        (17, 22, 'property', 2200, 1100, 180, 360, 902, 2706, 8118, 16236, 22550, None, None, None, None, None),
        (18, 23, 'property', 2200, 1100, 180, 360, 902, 2706, 8118, 16236, 22550, None, None, None, None, None),
        (19, 25, 'property', 2400, 1200, 196, 392, 984, 2952, 8856, 17712, 24600, None, None, None, None, None),
        (20, 26, 'transport', 2000, 1000, 250, 500, None, None, None, None, None, 500, 1000, 2000, None, None),
        (21, 27, 'property', 2600, 1300, 221, 442, 1105, 3315, 9945, 19890, 27625, None, None, None, None, None),
        (22, 28, 'utility', 1500, 750, 5, 15, None, None, None, None, None, None, None, None, 5, 15),
        (23, 29, 'property', 2600, 1300, 221, 442, 1105, 3315, 9945, 19890, 27625, None, None, None, None, None),
        (24, 30, 'property', 2800, 1400, 238, 476, 1190, 3570, 10710, 21420, 29750, None, None, None, None, None),
        (25, 32, 'property', 3000, 1500, 261, 522, 1305, 3915, 11745, 23490, 32625, None, None, None, None, None),
        (26, 34, 'property', 3000, 1500, 261, 522, 1305, 3915, 11745, 23490, 32625, None, None, None, None, None),
        (27, 35, 'property', 3200, 1600, 278, 556, 1392, 4176, 12528, 25056, 34800, None, None, None, None, None),
        (28, 36, 'transport', 2000, 1000, 250, 500, None, None, None, None, None, 500, 1000, 2000, None, None),
        (29, 38, 'property', 4000, 2000, 464, 928, 2320, 6960, 20880, 41760, 58000, None, None, None, None, None),
        (30, 39, 'penalty', -1000, -500, None, None, None, None, None, None, None, None, None, None, None, None),
        (31, 40, 'property', 5000, 2500, 625, 1250, 3125, 9375, 28125, 56250, 78125, None, None, None, None, None),
    ]
    for a in assets:
        session.execute(text(
            "INSERT INTO assets (asset_id, space_id, asset_type, purchase_price, mortgage_value, "
            "rent_base, rent_group, rent_house_1, rent_house_2, rent_house_3, rent_house_4, rent_hotel, "
            "rent_tier_2, rent_tier_3, rent_tier_4, utility_mult_single, utility_mult_double) "
            "VALUES (:aid, :sid, :atype, :pprice, :mval, :rb, :rg, :rh1, :rh2, :rh3, :rh4, :rht, "
            ":rt2, :rt3, :rt4, :ums, :umd)"
        ), {
            "aid": a[0], "sid": a[1], "atype": a[2], "pprice": a[3], "mval": a[4],
            "rb": a[5], "rg": a[6], "rh1": a[7], "rh2": a[8], "rh3": a[9], "rh4": a[10], "rht": a[11],
            "rt2": a[12], "rt3": a[13], "rt4": a[14], "ums": a[15], "umd": a[16],
        })

    session.execute(text("SELECT setval('assets_asset_id_seq', (SELECT MAX(asset_id) FROM assets))"))
    session.commit()
    print(f"  Seeded {len(assets)} assets.")


def seed_cards(session):
    count = session.execute(text("SELECT COUNT(*) FROM cards")).scalar()
    if count > 0:
        print(f"  cards already has {count} rows, skipping.")
        return

    # (card_id, deck_type, title, body_text, is_retainable, effect_code, effect_params)
    cards = [
        (1, 'welfare', 'You have been offered a free room upgrad', 'You have been offered a free room upgrade in a swanky hotel.  Collect $2000', 0, 'COLLECT', '{"amount": 2000}'),
        (2, 'welfare', 'Go to Jail directly.  You do not pass Sa', 'Go to Jail directly.  You do not pass Salary point nor do you collect $2000', 0, 'GO_TO_JAIL', None),
        (3, 'welfare', 'Tax Time.  You are Tax Assessment follow', 'Tax Time.  You are Tax Assessment follows: $500 per house and $1200 per hotel', 0, 'PAY_REPAIRS', '{"per_house": 500, "per_hotel": 1200}'),
        (4, 'welfare', 'Treat family to cruise along Swan River.', 'Treat family to cruise along Swan River.  Collect $250', 0, 'COLLECT', '{"amount": 250}'),
        (5, 'welfare', 'You received a complimentary overnight s', 'You received a complimentary overnight stay at the Samphire Lodge  - receive $1000', 0, 'COLLECT', '{"amount": 1000}'),
        (6, 'welfare', 'You make a charitable donation to Perth ', 'You make a charitable donation to Perth Zoo.  Pay $500 after a great day out.', 0, 'PAY_BANK', '{"amount": 500}'),
        (7, 'welfare', 'You have been caught trying to  sneak ba', 'You have been caught trying to  sneak backstage at a concert \u2013 pay $500 fine', 0, 'PAY_BANK', '{"amount": 500}'),
        (8, 'welfare', 'You are caught littering in St Georges T', 'You are caught littering in St Georges Terrace \u2013 Pay $1000', 0, 'PAY_BANK', '{"amount": 1000}'),
        (9, 'welfare', 'Visit Bell Tower and collect $1000 gift ', 'Visit Bell Tower and collect $1000 gift voucher', 0, 'COLLECT', '{"amount": 1000}'),
        (10, 'welfare', 'You come 2nd in surfing  competion at Tr', 'You come 2nd in surfing  competion at Trigg \u2013 Collect $200', 0, 'COLLECT', '{"amount": 200}'),
        (11, 'welfare', 'Bank dividend \u2013 collect $2000', 'Bank dividend \u2013 collect $2000', 0, 'COLLECT', '{"amount": 2000}'),
        (12, 'welfare', 'Get out of Jail \u2013 retain until need or t', 'Get out of Jail \u2013 retain until need or traded', 1, 'GET_OUT_OF_JAIL', None),
        (13, 'welfare', 'Ice-cream treat voucher \u2013 collect $100', 'Ice-cream treat voucher \u2013 collect $100', 0, 'COLLECT', '{"amount": 100}'),
        (14, 'welfare', 'You have won an award at the UWA arts fe', 'You have won an award at the UWA arts festival \u2013 collect $2000', 0, 'COLLECT', '{"amount": 2000}'),
        (15, 'welfare', 'You visit Fremantle Prison and win a pri', 'You visit Fremantle Prison and win a prize \u2013 collect $500', 0, 'COLLECT', '{"amount": 500}'),
        (16, 'welfare', 'Your friends treat you to a meal \u2013 colle', 'Your friends treat you to a meal \u2013 collect $100 from every player', 0, 'COLLECT_FROM_EACH_PLAYER', '{"amount": 100}'),
        (17, 'chance', 'Advance to nearest travel square \u2013 if un', 'Advance to nearest travel square \u2013 if unowned you may purchase and if owned pay owner twice normal rental', 0, 'ADVANCE_NEAREST_TRANSPORT', '{"rent_multiplier": 2}'),
        (18, 'chance', 'Get out of Jail free \u2013 This card may be ', 'Get out of Jail free \u2013 This card may be kept until needed or sold', 1, 'GET_OUT_OF_JAIL', None),
        (19, 'chance', 'You win a competion in Kings Park \u2013 Coll', 'You win a competion in Kings Park \u2013 Collect $500', 0, 'COLLECT', '{"amount": 500}'),
        (20, 'chance', 'Tax Time \u2013 General Repairs \u2013 Pay $250 fo', 'Tax Time \u2013 General Repairs \u2013 Pay $250 for each house and $1250 for each hotel', 0, 'PAY_REPAIRS', '{"per_house": 250, "per_hotel": 1250}'),
        (21, 'chance', 'Take you family and friends for a ride t', 'Take you family and friends for a ride to Kings Park', 0, 'MOVE_TO', '{"space_id": 40}'),
        (22, 'chance', 'Advance to nearest Utility \u2013 if unowned ', 'Advance to nearest Utility \u2013 if unowned you may purchase and if owned pay owner ten times normal rental', 0, 'ADVANCE_NEAREST_UTILITY', '{"rent_multiplier": 10}'),
        (23, 'chance', 'You have won tickets to Adventure World ', 'You have won tickets to Adventure World \u2013 advance to Adventure World \u2013 if you pass Payday then collect $2000', 0, 'MOVE_TO', '{"space_id": 19, "allow_pass_bonus": true}'),
        (24, 'chance', 'Go back three spaces', 'Go back three spaces', 0, 'MOVE_BACK', '{"steps": -3}'),
        (25, 'chance', 'Advance to nearest travel square \u2013 if un', 'Advance to nearest travel square \u2013 if unowned you may purchase and if owned pay owner twice normal rental', 0, 'ADVANCE_NEAREST_TRANSPORT', '{"rent_multiplier": 2}'),
        (26, 'chance', 'Take a trip to Transperth \u2013 if you pass ', 'Take a trip to Transperth \u2013 if you pass Payday then collect $2000', 0, 'MOVE_TO', '{"space_id": 6, "allow_pass_bonus": true}'),
        (27, 'chance', 'You have won a shopping spree.  Go to Ca', 'You have won a shopping spree.  Go to Carrillion City and  if you pass Payday then collect $2000', 0, 'MOVE_TO', '{"space_id": 25, "allow_pass_bonus": true}'),
        (28, 'chance', 'Bank pays you a dividend of $500', 'Bank pays you a dividend of $500', 0, 'COLLECT', '{"amount": 500}'),
        (29, 'chance', 'You go shopping at Freo Markets and pick', 'You go shopping at Freo Markets and pick ukp a bargain \u2013 pay $150', 0, 'PAY_BANK', '{"amount": 150}'),
        (30, 'chance', 'You have been elected loser of the year ', 'You have been elected loser of the year \u2013 pay each player $500 to keep the results quiet.', 0, 'PAY_EACH_PLAYER', '{"amount": 500}'),
        (31, 'chance', 'Advance to Start \u2013 Collect $2000', 'Advance to Start \u2013 Collect $2000', 0, 'MOVE_TO', '{"space_id": 1, "collect_on_land": 2000}'),
        (32, 'chance', 'Go to Jail \u2013 Do not pass Start/Payday or', 'Go to Jail \u2013 Do not pass Start/Payday or collect $2000', 0, 'GO_TO_JAIL', None),
    ]
    for c in cards:
        session.execute(text(
            "INSERT INTO cards (card_id, deck_type, title, body_text, is_retainable, effect_code, effect_params) "
            "VALUES (:cid, :dtype, :title, :body, :retain, :ecode, :eparams)"
        ), {
            "cid": c[0], "dtype": c[1], "title": c[2], "body": c[3],
            "retain": c[4], "ecode": c[5], "eparams": c[6],
        })

    session.execute(text("SELECT setval('cards_card_id_seq', (SELECT MAX(card_id) FROM cards))"))
    session.commit()
    print(f"  Seeded {len(cards)} cards.")


def main():
    print("Checking static data...")
    session = SessionLocal()
    try:
        seed_property_groups(session)
        seed_spaces(session)
        seed_assets(session)
        seed_cards(session)
        print("Static data check complete.")
    except Exception as e:
        session.rollback()
        print(f"Error seeding data: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
