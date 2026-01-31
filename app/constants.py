# app/constants.py
# Shared constants for the Monopoly Perth game

# Board layout constants
BOARD_SIZE = 40
JAIL_SPACE_ID = 10  # "Visit Jail" space where players are held (0-based indexing)
GO_TO_JAIL_SPACE_ID = 30  # "Police Arrest – Imprisonment" trigger space (0-based indexing)
START_SPACE_ID = 0  # "Start" space (Go)

# Jail-related constants
MAX_JAIL_TURNS = 3
JAIL_FINE = 500

# Default game settings
DEFAULT_STARTING_CASH = 20000
DEFAULT_PASS_START_BONUS = 2000
