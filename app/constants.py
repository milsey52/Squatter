# app/constants.py
# Shared constants for the Squatter game

# Board layout
BOARD_SIZE = 44
WOOL_SALE_SPACE = 0
VISITING_TOWN_SPACES = [6, 7]
VISITING_TOWN_TURNS = 2

# Paddock capacities (pens per paddock)
NATURAL_PADDOCK_PENS = 3
IMPROVED_PADDOCK_PENS = 5
IRRIGATED_PADDOCK_PENS = 6
MAX_PADDOCKS = 5

# Paddock upgrade costs
IMPROVED_PASTURE_COST = 500
IRRIGATED_PASTURE_COST = 1500

# Mortgage rates per paddock
MORTGAGE_NATURAL = 100
MORTGAGE_IMPROVED = 250
MORTGAGE_IRRIGATED = 750
MORTGAGE_INTEREST_RATE = 0.10

# Stud rams
STUD_RAM_PURCHASE_PRICE = 500
STUD_RAM_SELL_PRICE = 400

# Haystack
HAYSTACK_COST = 500
HAYSTACK_COST_DROUGHT = 1000  # rule: cost doubles when the purchasing player is in a drought
HAYSTACK_SELL_PRICE = 350


def haystack_buy_price(player) -> int:
    """Return the haystack purchase price for this player ($1000 if in drought, else $500)."""
    return HAYSTACK_COST_DROUGHT if (player and player.is_in_drought) else HAYSTACK_COST

# Stock sale
MAX_PENS_PER_TRANSACTION = 15
EMERGENCY_SELL_PRICE_PER_PEN = 400
DROUGHT_SELL_PRICE_NO_HAYSTACK = 200  # flat per-pen price on Local Drought when player has no haystack
BORE_DRIES_UP_PRICE_NO_HAYSTACK = 300  # per pen, irrigated stock sold to Bank
BORE_DRIES_UP_PRICE_WITH_HAYSTACK = 500  # per pen when haystack offsets the bore

# Wool cheque
WOOL_CHEQUE_PER_PEN = 250
STUD_RAM_WOOL_BONUS_PER_PEN = 25

# Flood damage — flat repair expense paid to the bank
FLOOD_DAMAGE_REPAIR_COST = 1000

# Sheep
SHEEP_PER_PEN = 200

# Win condition
WIN_TOTAL_PENS = 30  # 6,000 sheep / 200 per pen

# Default game settings
DEFAULT_STARTING_CASH = 2000
QUICK_GAME_STARTING_CASH = 6000
