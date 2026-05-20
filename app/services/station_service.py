# app/services/station_service.py
import json
from sqlalchemy.orm import Session
from sqlalchemy import func
from app import models
from app.constants import (
    NATURAL_PADDOCK_PENS, IMPROVED_PADDOCK_PENS, IRRIGATED_PADDOCK_PENS,
    MAX_PADDOCKS, IMPROVED_PASTURE_COST, IRRIGATED_PASTURE_COST,
    MORTGAGE_NATURAL, MORTGAGE_IMPROVED, MORTGAGE_IRRIGATED,
    MORTGAGE_INTEREST_RATE, WOOL_CHEQUE_PER_PEN, STUD_RAM_WOOL_BONUS_PER_PEN,
    WIN_TOTAL_PENS, SHEEP_PER_PEN, EMERGENCY_SELL_PRICE_PER_PEN,
)


PADDOCK_CONFIG = {
    "natural": {"max_pens": NATURAL_PADDOCK_PENS, "mortgage": MORTGAGE_NATURAL},
    "improved": {"max_pens": IMPROVED_PADDOCK_PENS, "mortgage": MORTGAGE_IMPROVED},
    "irrigated": {"max_pens": IRRIGATED_PADDOCK_PENS, "mortgage": MORTGAGE_IRRIGATED},
}


class StationService:
    def __init__(self, session: Session, game_id: int):
        self.session = session
        self.game_id = game_id

    # ── Initialization ──────────────────────────────────────────────────

    def initialize_station(self, game_player_id: int, quick_game: bool = False):
        """Create 5 paddocks for a player at game start."""
        if quick_game:
            ptype = "improved"
            pens = IMPROVED_PADDOCK_PENS
            max_pens = IMPROVED_PADDOCK_PENS
        else:
            ptype = "natural"
            pens = NATURAL_PADDOCK_PENS
            max_pens = NATURAL_PADDOCK_PENS

        for i in range(1, MAX_PADDOCKS + 1):
            self.session.add(models.Paddock(
                game_id=self.game_id,
                owner_game_player_id=game_player_id,
                paddock_number=i,
                paddock_type=ptype,
                sheep_pens=pens,
                max_pens=max_pens,
                is_mortgaged=False,
            ))
        self.session.flush()

    def initialize_stud_ram_states(self):
        """Create StudRamState records for all stud ram spaces."""
        stud_spaces = (
            self.session.query(models.Space)
            .filter(models.Space.space_type == "stud_ram")
            .all()
        )
        for space in stud_spaces:
            self.session.add(models.StudRamState(
                game_id=self.game_id,
                space_id=space.space_id,
                owner_game_player_id=None,
                is_available=True,
            ))
        self.session.flush()

    # ── Queries ─────────────────────────────────────────────────────────

    def get_paddocks(self, game_player_id: int):
        return (
            self.session.query(models.Paddock)
            .filter_by(game_id=self.game_id, owner_game_player_id=game_player_id)
            .order_by(models.Paddock.paddock_number)
            .all()
        )

    def get_total_pens(self, game_player_id: int) -> int:
        result = (
            self.session.query(func.coalesce(func.sum(models.Paddock.sheep_pens), 0))
            .filter_by(game_id=self.game_id, owner_game_player_id=game_player_id)
            .scalar()
        )
        return int(result)

    def get_total_sheep(self, game_player_id: int) -> int:
        return self.get_total_pens(game_player_id) * SHEEP_PER_PEN

    def get_max_pens(self, game_player_id: int) -> int:
        result = (
            self.session.query(func.coalesce(func.sum(models.Paddock.max_pens), 0))
            .filter_by(game_id=self.game_id, owner_game_player_id=game_player_id)
            .scalar()
        )
        return int(result)

    def get_empty_pens(self, game_player_id: int) -> int:
        return self.get_max_pens(game_player_id) - self.get_total_pens(game_player_id)

    def is_fully_stocked(self, game_player_id: int) -> bool:
        return self.get_empty_pens(game_player_id) == 0

    def get_stud_rams_owned(self, game_player_id: int):
        return (
            self.session.query(models.StudRamState)
            .filter_by(game_id=self.game_id, owner_game_player_id=game_player_id)
            .all()
        )

    def count_stud_rams_owned(self, game_player_id: int) -> int:
        return (
            self.session.query(models.StudRamState)
            .filter_by(game_id=self.game_id, owner_game_player_id=game_player_id)
            .count()
        )

    def get_paddocks_by_type(self, game_player_id: int, paddock_type: str):
        return (
            self.session.query(models.Paddock)
            .filter_by(
                game_id=self.game_id,
                owner_game_player_id=game_player_id,
                paddock_type=paddock_type,
            )
            .all()
        )

    def count_paddocks_by_type(self, game_player_id: int, paddock_type: str) -> int:
        return len(self.get_paddocks_by_type(game_player_id, paddock_type))

    def has_any_mortgaged(self, game_player_id: int) -> bool:
        return (
            self.session.query(models.Paddock)
            .filter_by(
                game_id=self.game_id,
                owner_game_player_id=game_player_id,
                is_mortgaged=True,
            )
            .first()
        ) is not None

    # ── Sheep Management ────────────────────────────────────────────────

    def buy_sheep(self, game_player_id: int, pens: int, only_types=None):
        """Add sheep pens to station. Fills paddocks with available space.
        If only_types is provided (e.g. ("irrigated",)), restricts placement
        to paddocks of those types."""
        paddocks = self.get_paddocks(game_player_id)
        if only_types:
            paddocks = [p for p in paddocks if p.paddock_type in only_types]
        remaining = pens
        for p in paddocks:
            if remaining <= 0:
                break
            space = p.max_pens - p.sheep_pens
            if space > 0:
                add = min(space, remaining)
                p.sheep_pens += add
                remaining -= add
        self.session.flush()
        return pens - remaining  # actual pens added

    def get_empty_pens_by_type(self, game_player_id: int, paddock_type: str) -> int:
        return sum(
            (p.max_pens - p.sheep_pens)
            for p in self.get_paddocks_by_type(game_player_id, paddock_type)
        )

    def move_sheep(self, game_player_id: int, from_paddock_id: int,
                   to_paddock_id: int, pens: int) -> dict:
        """Move N pens of sheep between two paddocks owned by the same player.
        Validates ownership, source stock, destination capacity, and that the
        paddocks are not the same."""
        if pens <= 0:
            raise ValueError("Pens to move must be positive")
        if from_paddock_id == to_paddock_id:
            raise ValueError("Source and destination paddocks must differ")

        src = self.session.query(models.Paddock).filter_by(
            paddock_id=from_paddock_id,
            game_id=self.game_id,
            owner_game_player_id=game_player_id,
        ).first()
        dst = self.session.query(models.Paddock).filter_by(
            paddock_id=to_paddock_id,
            game_id=self.game_id,
            owner_game_player_id=game_player_id,
        ).first()
        if not src or not dst:
            raise ValueError("Both paddocks must be owned by the player")
        if src.is_mortgaged or dst.is_mortgaged:
            raise ValueError("Cannot move sheep to or from a mortgaged paddock")
        if src.sheep_pens < pens:
            raise ValueError(
                f"Source paddock #{src.paddock_number} only has {src.sheep_pens} pens"
            )
        space_left = dst.max_pens - dst.sheep_pens
        if space_left < pens:
            raise ValueError(
                f"Destination paddock #{dst.paddock_number} has space for only {space_left} more pens"
            )
        src.sheep_pens -= pens
        dst.sheep_pens += pens
        self.session.flush()
        return {
            "from": src.paddock_number, "from_type": src.paddock_type,
            "to": dst.paddock_number, "to_type": dst.paddock_type,
            "pens": pens,
        }

    def sell_sheep(self, game_player_id: int, pens: int, from_type: str = None):
        """Remove sheep pens from station. Removes from specified type first."""
        paddocks = self.get_paddocks(game_player_id)
        if from_type:
            # Sell from specific pasture type first
            typed = [p for p in paddocks if p.paddock_type == from_type and p.sheep_pens > 0]
            others = [p for p in paddocks if p.paddock_type != from_type and p.sheep_pens > 0]
            ordered = typed + others
        else:
            ordered = [p for p in paddocks if p.sheep_pens > 0]

        remaining = pens
        for p in ordered:
            if remaining <= 0:
                break
            remove = min(p.sheep_pens, remaining)
            p.sheep_pens -= remove
            remaining -= remove
        self.session.flush()
        return pens - remaining  # actual pens removed

    def sell_half_stock(self, game_player_id: int, exclude_irrigated: bool = True,
                        irrigated_only: bool = False,
                        return_breakdown: bool = False):
        """Sell half stock (for drought / bore dries up). irrigated_only restricts
        to irrigated paddocks; otherwise exclude_irrigated controls Natural/Improved
        scope. Returns pens sold (or breakdown dict)."""
        paddocks = self.get_paddocks(game_player_id)
        if irrigated_only:
            affected = [p for p in paddocks if p.paddock_type == "irrigated"]
        elif exclude_irrigated:
            affected = [p for p in paddocks if p.paddock_type != "irrigated"]
        else:
            affected = list(paddocks)

        total_pens = sum(p.sheep_pens for p in affected)
        pens_to_sell = (total_pens + 1) // 2  # round up per rules

        sold_by_type = {"natural": 0, "improved": 0, "irrigated": 0}
        remaining = pens_to_sell
        for p in affected:
            if remaining <= 0:
                break
            remove = min(p.sheep_pens, remaining)
            p.sheep_pens -= remove
            sold_by_type[p.paddock_type] += remove
            remaining -= remove
        self.session.flush()
        actual = pens_to_sell - remaining
        if return_breakdown:
            return {"total": actual, "by_type": sold_by_type}
        return actual

    def sell_fraction_stock(self, game_player_id: int, fraction: float,
                            return_breakdown: bool = False):
        """Sell a fraction of total stock (e.g., 1/3 for Lucerne Flea).
        Removes from paddocks in order; with return_breakdown=True returns
        {'total': pens_sold, 'by_type': {natural, improved, irrigated}}."""
        total_pens = self.get_total_pens(game_player_id)
        pens_to_sell = int(total_pens * fraction + 0.5)  # round

        if not return_breakdown:
            return self.sell_sheep(game_player_id, pens_to_sell)

        paddocks = self.get_paddocks(game_player_id)
        ordered = [p for p in paddocks if p.sheep_pens > 0]
        sold_by_type = {"natural": 0, "improved": 0, "irrigated": 0}
        remaining = pens_to_sell
        for p in ordered:
            if remaining <= 0:
                break
            remove = min(p.sheep_pens, remaining)
            p.sheep_pens -= remove
            sold_by_type[p.paddock_type] += remove
            remaining -= remove
        self.session.flush()
        return {"total": pens_to_sell - remaining, "by_type": sold_by_type}

    # ── Paddock Upgrades ────────────────────────────────────────────────

    def can_upgrade_to_improved(self, game_player_id: int) -> dict:
        """Check if player can upgrade any paddocks to improved.
        Per rules: stock on the paddock is NOT required before upgrading."""
        paddocks = self.get_paddocks(game_player_id)
        natural = [p for p in paddocks if p.paddock_type == "natural" and not p.is_mortgaged]
        return {
            "can_upgrade": len(natural) > 0,
            "available_paddocks": [p.paddock_number for p in natural],
            "cost_per_paddock": IMPROVED_PASTURE_COST,
        }

    def can_upgrade_to_irrigated(self, game_player_id: int) -> dict:
        """Check if player can upgrade to irrigated. Must have ALL 5 as improved/irrigated first."""
        paddocks = self.get_paddocks(game_player_id)
        improved = [p for p in paddocks if p.paddock_type == "improved"]
        irrigated = [p for p in paddocks if p.paddock_type == "irrigated"]
        all_upgraded = (len(improved) + len(irrigated)) >= MAX_PADDOCKS
        return {
            "can_upgrade": all_upgraded and len(improved) > 0,
            "improved_count": len(improved) + len(irrigated),
            "required": MAX_PADDOCKS,
            "cost_per_paddock": IRRIGATED_PASTURE_COST,
        }

    def upgrade_paddock(self, game_player_id: int, paddock_number: int, target_type: str):
        """Upgrade a paddock. Returns the paddock if successful."""
        paddock = (
            self.session.query(models.Paddock)
            .filter_by(
                game_id=self.game_id,
                owner_game_player_id=game_player_id,
                paddock_number=paddock_number,
            )
            .first()
        )
        if not paddock:
            raise ValueError(f"Paddock {paddock_number} not found")

        if target_type == "improved":
            if paddock.paddock_type != "natural":
                raise ValueError("Can only upgrade natural to improved")
            paddock.paddock_type = "improved"
            paddock.max_pens = IMPROVED_PADDOCK_PENS
            # Sheep stay on the paddock (move with it). Stock on the paddock is
            # NOT required to upgrade — per rules, an empty Natural can become Improved.

        elif target_type == "irrigated":
            if paddock.paddock_type != "improved":
                raise ValueError("Can only upgrade improved to irrigated")
            # Must have all 5 as improved first
            improved_count = self.count_paddocks_by_type(game_player_id, "improved")
            irrigated_count = self.count_paddocks_by_type(game_player_id, "irrigated")
            if improved_count + irrigated_count < MAX_PADDOCKS:
                raise ValueError("Must have all 5 paddocks as improved before upgrading to irrigated")
            paddock.paddock_type = "irrigated"
            paddock.max_pens = IRRIGATED_PADDOCK_PENS
        else:
            raise ValueError(f"Invalid target type: {target_type}")

        self.session.flush()
        return paddock

    # ── Mortgage ─────────────────────────────────────────────────────────

    def mortgage_paddock(self, game_player_id: int, paddock_number: int) -> int:
        """Mortgage a paddock. Returns mortgage amount received."""
        paddock = (
            self.session.query(models.Paddock)
            .filter_by(
                game_id=self.game_id,
                owner_game_player_id=game_player_id,
                paddock_number=paddock_number,
            )
            .first()
        )
        if not paddock:
            raise ValueError(f"Paddock {paddock_number} not found")
        if paddock.is_mortgaged:
            raise ValueError("Paddock is already mortgaged")

        paddock.is_mortgaged = True
        amount = PADDOCK_CONFIG[paddock.paddock_type]["mortgage"]
        self.session.flush()
        return amount

    def unmortgage_paddock(self, game_player_id: int, paddock_number: int) -> int:
        """Unmortgage a paddock. Returns cost (mortgage + 10% interest)."""
        paddock = (
            self.session.query(models.Paddock)
            .filter_by(
                game_id=self.game_id,
                owner_game_player_id=game_player_id,
                paddock_number=paddock_number,
            )
            .first()
        )
        if not paddock:
            raise ValueError(f"Paddock {paddock_number} not found")
        if not paddock.is_mortgaged:
            raise ValueError("Paddock is not mortgaged")

        mortgage_value = PADDOCK_CONFIG[paddock.paddock_type]["mortgage"]
        cost = int(mortgage_value * (1 + MORTGAGE_INTEREST_RATE))
        paddock.is_mortgaged = False
        self.session.flush()
        return cost

    def calculate_mortgage_interest(self, game_player_id: int) -> int:
        """Calculate total mortgage interest due when passing Wool Sale."""
        paddocks = self.get_paddocks(game_player_id)
        total = 0
        for p in paddocks:
            if p.is_mortgaged:
                mortgage_value = PADDOCK_CONFIG[p.paddock_type]["mortgage"]
                total += int(mortgage_value * MORTGAGE_INTEREST_RATE)
        return total

    # ── Wool Cheque ──────────────────────────────────────────────────────

    def calculate_wool_cheque(self, game_player_id: int) -> dict:
        """Calculate wool cheque amount. Returns breakdown."""
        total_pens = self.get_total_pens(game_player_id)
        stud_rams = self.count_stud_rams_owned(game_player_id)

        base = total_pens * WOOL_CHEQUE_PER_PEN
        ram_bonus = total_pens * stud_rams * STUD_RAM_WOOL_BONUS_PER_PEN

        # Check for card bonuses on the player
        player = self.session.query(models.GamePlayer).get(game_player_id)
        extra_bonus = player.wool_cheque_bonus if player else 0

        # Blowfly penalty
        blowfly_reduction = 0
        if player and player.wool_cheque_blowfly_penalty if hasattr(player, 'wool_cheque_blowfly_penalty') else False:
            blowfly_reduction = int((base + ram_bonus) * 0.10)

        total = base + ram_bonus + extra_bonus - blowfly_reduction

        return {
            "total_pens": total_pens,
            "stud_rams": stud_rams,
            "base_amount": base,
            "ram_bonus": ram_bonus,
            "extra_bonus": extra_bonus,
            "blowfly_reduction": blowfly_reduction,
            "total": total,
        }

    # ── Win Condition ────────────────────────────────────────────────────

    def check_win_condition(self, game_player_id: int) -> bool:
        """First to 6,000 sheep (30 pens) on fully irrigated farm, no mortgages.
        Note: 30 pens is only achievable on all-irrigated paddocks (capacities
        cap at 3/5/6 per Natural/Improved/Irrigated × 5 paddocks = 15/25/30),
        but the explicit check is preserved as a guard."""
        total_pens = self.get_total_pens(game_player_id)
        if total_pens < WIN_TOTAL_PENS:
            return False

        paddocks = self.get_paddocks(game_player_id)
        all_irrigated = all(p.paddock_type == "irrigated" for p in paddocks)
        no_mortgages = not any(p.is_mortgaged for p in paddocks)

        return all_irrigated and no_mortgages

    def declare_winner_if_eligible(self, player_id: int, turn_id) -> bool:
        """If the player meets the win condition AND the game is still in
        progress, mark the game completed and create a `game_won` pending
        action. Returns True if a winner was declared in this call.
        Safe to call repeatedly — only fires once per game."""
        if not self.check_win_condition(player_id):
            return False

        game = self.session.query(models.Game).get(self.game_id)
        if game.status == "completed":
            return False

        # Avoid duplicate game_won pending actions.
        existing = (
            self.session.query(models.PendingAction)
            .filter_by(game_id=self.game_id, action_type="game_won")
            .first()
        )
        if existing:
            return False

        player = self.session.query(models.GamePlayer).get(player_id)
        game.status = "completed"
        action = models.PendingAction(
            game_id=self.game_id,
            turn_id=turn_id,
            action_type="game_won",
            active_player_id=player_id,
            action_data=json.dumps({
                "winner_id": player_id,
                "winner_name": player.player_name if player else None,
            }),
        )
        self.session.add(action)
        self.session.flush()
        return True

    # ── Station Summary ─────────────────────────────────────────────────

    def get_station_summary(self, game_player_id: int) -> dict:
        paddocks = self.get_paddocks(game_player_id)
        stud_rams = self.get_stud_rams_owned(game_player_id)
        player = self.session.query(models.GamePlayer).get(game_player_id)

        return {
            "game_player_id": game_player_id,
            "paddocks": [
                {
                    "paddock_id": p.paddock_id,
                    "paddock_number": p.paddock_number,
                    "paddock_type": p.paddock_type,
                    "sheep_pens": p.sheep_pens,
                    "max_pens": p.max_pens,
                    "sheep_count": p.sheep_pens * SHEEP_PER_PEN,
                    "is_mortgaged": p.is_mortgaged,
                }
                for p in paddocks
            ],
            "total_pens": sum(p.sheep_pens for p in paddocks),
            "total_sheep": sum(p.sheep_pens for p in paddocks) * SHEEP_PER_PEN,
            "max_capacity_pens": sum(p.max_pens for p in paddocks),
            "is_fully_stocked": all(p.sheep_pens == p.max_pens for p in paddocks),
            "stud_rams": [
                {
                    "space_id": sr.space_id,
                    "space_name": sr.space.name if sr.space else None,
                }
                for sr in stud_rams
            ],
            "has_haystack": player.has_haystack if player else False,
            "is_in_drought": player.is_in_drought if player else False,
            "drought_spaces_remaining": player.drought_spaces_remaining if player else 0,
        }
