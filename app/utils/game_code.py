"""Game code generation utility for multiplayer games."""
import random
import string
from sqlalchemy.orm import Session
from app import models


def generate_game_code(session: Session) -> str:
    """
    Generate a unique 6-character game code.

    Uses a mix of consonants, vowels, and digits to create pronounceable,
    easy-to-share codes (e.g., "BAZO4P", "KENU2X").

    Args:
        session: Database session for uniqueness checking

    Returns:
        6-character unique game code
    """
    consonants = 'BCDFGHJKLMNPQRSTVWXYZ'
    vowels = 'AEIOU'

    max_attempts = 100
    for _ in range(max_attempts):
        # Pattern: Consonant-Vowel-Consonant-Digit-Consonant-Vowel
        # Example: BAZO4P
        code = ''.join([
            random.choice(consonants),
            random.choice(vowels),
            random.choice(consonants),
            random.choice(string.digits),
            random.choice(consonants),
            random.choice(vowels)
        ])

        # Check uniqueness
        existing = session.query(models.Game).filter_by(game_code=code).first()
        if not existing:
            return code

    # Fallback to fully random if somehow all attempts fail
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        existing = session.query(models.Game).filter_by(game_code=code).first()
        if not existing:
            return code
