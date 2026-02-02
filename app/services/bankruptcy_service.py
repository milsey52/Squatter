# app/services/bankruptcy_service.py
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime
from app import models
from app.services.ledger_service import LedgerService, BANK_PLAYER_ID


class BankruptcyService:
    def __init__(self, session: Session, game_id: int):
        self.session = session
        self.game_id = game_id
        self.ledger = LedgerService(session, game_id)

    def check_can_afford(self, player_id: int, amount: int) -> bool:
        """Check if player has sufficient balance to afford payment."""
        balance = self.ledger.player_balance(player_id)
        return balance >= amount

    def create_debt_state(
        self,
        debtor_id: int,
        creditor_id: Optional[int],
        amount: int,
        reason: str,
        turn_id: Optional[int] = None,
        asset_id: Optional[int] = None
    ) -> models.DebtState:
        """Create a new debt state record when player cannot pay."""
        debt = models.DebtState(
            game_id=self.game_id,
            debtor_player_id=debtor_id,
            creditor_player_id=creditor_id,
            debt_amount=amount,
            debt_reason=reason,
            status="pending",
            asset_id=asset_id,
            turn_id=turn_id
        )
        self.session.add(debt)
        self.session.flush()
        return debt

    def get_pending_debt(self, player_id: int) -> Optional[models.DebtState]:
        """Get active pending debt for a player."""
        return self.session.query(models.DebtState).filter(
            and_(
                models.DebtState.game_id == self.game_id,
                models.DebtState.debtor_player_id == player_id,
                models.DebtState.status == "pending"
            )
        ).first()

    def calculate_liquidation_value(self, player_id: int) -> Dict[str, Any]:
        """Calculate total cash player can raise from selling/mortgaging assets."""
        current_balance = self.ledger.player_balance(player_id)

        # Get player's properties
        asset_states = self.session.query(models.AssetState).join(
            models.Asset
        ).filter(
            and_(
                models.AssetState.game_id == self.game_id,
                models.AssetState.owner_game_player_id == player_id
            )
        ).all()

        total_from_improvements = 0
        total_from_mortgages = 0
        properties_with_improvements = []
        mortgageable_properties = []

        # Calculate value from properties
        for asset_state in asset_states:
            asset = self.session.query(models.Asset).filter(
                models.Asset.asset_id == asset_state.asset_id
            ).first()

            # Only properties can have improvements or be mortgaged
            if asset.asset_type != "property":
                continue

            # Get property group for house cost
            space = self.session.query(models.Space).filter(
                models.Space.space_id == asset.space_id
            ).first()

            if space.group_id:
                group = self.session.query(models.PropertyGroup).filter(
                    models.PropertyGroup.group_id == space.group_id
                ).first()

                # Calculate improvement value (50% refund)
                if asset_state.has_hotel:
                    improvement_value = group.hotel_cost // 2
                    total_from_improvements += improvement_value
                    properties_with_improvements.append({
                        "asset_id": asset.asset_id,
                        "name": space.name,
                        "type": "hotel",
                        "value": improvement_value
                    })
                elif asset_state.improvement_level > 0:
                    improvement_value = (asset_state.improvement_level * group.house_cost) // 2
                    total_from_improvements += improvement_value
                    properties_with_improvements.append({
                        "asset_id": asset.asset_id,
                        "name": space.name,
                        "type": "houses",
                        "count": asset_state.improvement_level,
                        "value": improvement_value
                    })

            # Calculate mortgage value (only if not already mortgaged)
            if not asset_state.is_mortgaged:
                total_from_mortgages += asset.mortgage_value
                mortgageable_properties.append({
                    "asset_id": asset.asset_id,
                    "name": space.name,
                    "value": asset.mortgage_value
                })

        # Calculate value from Get Out of Jail Free cards
        jail_cards = self.session.query(models.CardDraw).join(
            models.Card
        ).filter(
            and_(
                models.CardDraw.game_id == self.game_id,
                models.CardDraw.kept_by_player_id == player_id,
                models.CardDraw.discarded_at.is_(None),
                models.Card.is_retainable == True
            )
        ).all()

        total_from_cards = len(jail_cards) * 500

        return {
            "current_balance": current_balance,
            "from_improvements": total_from_improvements,
            "from_mortgages": total_from_mortgages,
            "from_cards": total_from_cards,
            "total_available": current_balance + total_from_improvements + total_from_mortgages + total_from_cards,
            "breakdown": {
                "properties_with_improvements": properties_with_improvements,
                "mortgageable_properties": mortgageable_properties,
                "jail_cards": len(jail_cards)
            }
        }

    def resolve_debt(
        self,
        debt_state_id: int,
        turn_id: Optional[int] = None
    ) -> bool:
        """Process payment for a debt after player has liquidated assets."""
        debt = self.session.query(models.DebtState).filter(
            models.DebtState.debt_state_id == debt_state_id
        ).first()

        if not debt or debt.status != "pending":
            return False

        debtor = self.session.query(models.GamePlayer).filter(
            models.GamePlayer.game_player_id == debt.debtor_player_id
        ).first()

        # Check if player can now afford the debt
        if not self.check_can_afford(debt.debtor_player_id, debt.debt_amount):
            return False

        # Process the payment
        self.ledger.transfer(
            payer=debtor,
            payee_id=debt.creditor_player_id,
            amount=debt.debt_amount,
            txn_type=debt.debt_reason,
            turn_id=turn_id or debt.turn_id,
            asset_id=debt.asset_id,
            notes=f"Debt resolution: {debt.debt_reason}"
        )

        # Mark debt as resolved
        debt.status = "resolved"
        debt.resolved_at = datetime.now()
        self.session.flush()

        return True

    def resign_player(self, player_id: int, turn_id: Optional[int] = None):
        """Remove player from game and return all assets to bank."""
        player = self.session.query(models.GamePlayer).filter(
            models.GamePlayer.game_player_id == player_id
        ).first()

        if not player or not player.is_active:
            return False

        # Mark player as inactive
        player.is_active = False

        # Get all player's properties
        asset_states = self.session.query(models.AssetState).filter(
            and_(
                models.AssetState.game_id == self.game_id,
                models.AssetState.owner_game_player_id == player_id
            )
        ).all()

        # Process each property
        for asset_state in asset_states:
            # Remove all improvements (no refund on resignation)
            asset_state.improvement_level = 0
            asset_state.has_hotel = False

            # Unmortgage property
            asset_state.is_mortgaged = False

            # Release ownership (return to bank)
            asset_state.owner_game_player_id = None

        # Discard all cards
        card_draws = self.session.query(models.CardDraw).filter(
            and_(
                models.CardDraw.game_id == self.game_id,
                models.CardDraw.kept_by_player_id == player_id,
                models.CardDraw.discarded_at.is_(None)
            )
        ).all()

        for card_draw in card_draws:
            card_draw.discarded_at = datetime.now()

        # Forfeit remaining cash to bank (record transaction)
        balance = self.ledger.player_balance(player_id)
        if balance > 0:
            self.ledger.pay_bank(
                player=player,
                amount=balance,
                txn_type="resignation",
                turn_id=turn_id,
                notes="Player resigned - cash forfeited to bank"
            )

        # Mark any pending debts as defaulted
        pending_debts = self.session.query(models.DebtState).filter(
            and_(
                models.DebtState.game_id == self.game_id,
                models.DebtState.debtor_player_id == player_id,
                models.DebtState.status == "pending"
            )
        ).all()

        for debt in pending_debts:
            debt.status = "defaulted"
            debt.resolved_at = datetime.now()

        self.session.flush()

        # Check if game is over
        winner = self.check_game_over()

        return {
            "resigned": True,
            "player_id": player_id,
            "game_over": winner is not None,
            "winner_id": winner.game_player_id if winner else None
        }

    def check_game_over(self) -> Optional[models.GamePlayer]:
        """Check if only one active player remains. Returns winner or None."""
        active_players = self.session.query(models.GamePlayer).filter(
            and_(
                models.GamePlayer.game_id == self.game_id,
                models.GamePlayer.is_active == True
            )
        ).all()

        if len(active_players) == 1:
            # Game over - we have a winner
            winner = active_players[0]
            game = self.session.query(models.Game).filter(
                models.Game.game_id == self.game_id
            ).first()

            if game:
                game.status = "completed"
                self.session.flush()

            return winner

        return None

    def sell_jail_card(self, player_id: int, card_draw_id: int, turn_id: Optional[int] = None) -> bool:
        """Sell a Get Out of Jail Free card back to bank for $500."""
        card_draw = self.session.query(models.CardDraw).join(
            models.Card
        ).filter(
            and_(
                models.CardDraw.card_draw_id == card_draw_id,
                models.CardDraw.game_id == self.game_id,
                models.CardDraw.kept_by_player_id == player_id,
                models.CardDraw.discarded_at.is_(None),
                models.Card.is_retainable == True
            )
        ).first()

        if not card_draw:
            return False

        # Mark card as discarded
        card_draw.discarded_at = datetime.now()

        # Give player $500
        player = self.session.query(models.GamePlayer).filter(
            models.GamePlayer.game_player_id == player_id
        ).first()

        self.ledger.receive_from_bank(
            player=player,
            amount=500,
            txn_type="card_sale",
            turn_id=turn_id,
            card_id=card_draw.card_id,
            notes="Sold Get Out of Jail Free card"
        )

        self.session.flush()
        return True
