# app/services/space_resolver.py
from typing import Optional, TYPE_CHECKING
from sqlalchemy.orm import Session
from sqlalchemy import func

from app import models
from app.constants import JAIL_SPACE_ID
from app.services.ledger_service import LedgerService
from app.services.jackpot_service import JackpotService

if TYPE_CHECKING:
    from .card_service import CardService

class SpaceResolver:
    def __init__(self, session: Session, game_id: int, card_service: Optional["CardService"] = None):
        self.session = session
        self.game_id = game_id
        self.ledger = LedgerService(session, game_id)
        self.jackpot = JackpotService(session, game_id)
        self.card_service = card_service  # TurnManager will assign this

    def resolve(self, player: models.GamePlayer, space: models.Space, turn, passed_start: bool):
        handler = getattr(self, f"_handle_{space.space_type}", self._handle_default)
        handler(player, space, turn, passed_start)

    # ------------------------------------------------------------------ #
    # Space types
    def _handle_property(self, player, space, turn, passed_start):
        asset = self._get_asset(space.space_id)
        state = self._get_asset_state(asset.asset_id)

        if state.owner_game_player_id is None:
            self._offer_purchase(player, asset, state, turn)
        elif state.owner_game_player_id != player.game_player_id:
            self._collect_rent(player, state, asset, turn)

    def _handle_transport(self, player, space, turn, passed_start):
        asset = self._get_asset(space.space_id)
        state = self._get_asset_state(asset.asset_id)

        if state.owner_game_player_id is None:
            self._offer_purchase(player, asset, state, turn)
        elif state.owner_game_player_id != player.game_player_id:
            rent = self._transport_rent(asset, state.owner_game_player_id)
            card_multiplier = getattr(self, "_temp_rent_multiplier", None)
            if card_multiplier:
                rent = int(rent * card_multiplier)
            self.ledger.transfer(
                payer=player,
                payee_id=state.owner_game_player_id,
                amount=rent,
                txn_type="transport_rent",
                turn_id=turn.turn_id,
                asset_id=asset.asset_id,
            )

    def _handle_utility(self, player, space, turn, passed_start):
        asset = self._get_asset(space.space_id)
        state = self._get_asset_state(asset.asset_id)

        if state.owner_game_player_id is None:
            self._offer_purchase(player, asset, state, turn)
        elif state.owner_game_player_id != player.game_player_id:
            dice_total = (turn.dice_roll_1 or 0) + (turn.dice_roll_2 or 0)
            owned = self._count_assets_owned(state.owner_game_player_id, "utility")
            multiplier = asset.utility_mult_single if owned == 1 else asset.utility_mult_double
            rent = dice_total * (multiplier or 0)
            card_multiplier = getattr(self, "_temp_rent_multiplier", None)
            if card_multiplier:
                rent = int(rent * card_multiplier)
            self.ledger.transfer(
                payer=player,
                payee_id=state.owner_game_player_id,
                amount=rent,
                txn_type="utility_rent",
                turn_id=turn.turn_id,
                asset_id=asset.asset_id,
            )

    def _handle_chance(self, player, space, turn, passed_start):
        if getattr(self, "_skip_card_spaces", False):
            return
        self.card_service.draw_and_apply(player, "chance", turn)

    def _handle_welfare(self, player, space, turn, passed_start):
        if getattr(self, "_skip_card_spaces", False):
            return
        self.card_service.draw_and_apply(player, "welfare", turn)

    def _handle_penalty(self, player, space, turn, passed_start):
        name = space.name.lower()
        if "income tax" in name:
            self.ledger.pay_bank(player, 2000, "income_tax", turn.turn_id)
        elif "mortgage payment" in name:
            self.ledger.pay_bank(player, 1000, "mortgage_payment", turn.turn_id)
        elif "go to jail" in name:
            self._send_player_to_jail(player, turn)
        else:
            pass  # add other penalty spaces here

    def _handle_rest(self, player, space, turn, passed_start):
        if "salvo rest home" in space.name.lower() and self.jackpot.enabled:
            amount = self.jackpot.payout(turn.turn_id, player)
            if amount > 0:
                self.ledger.record_bank_reward(
                    player,
                    amount,
                    "jackpot_payout",
                    turn.turn_id,
                    notes="Collected jackpot",
                )

    def _handle_start(self, player, space, turn, passed_start):
        # pass-start bonus handled elsewhere
        pass

    def _handle_default(self, player, space, turn, passed_start):
        pass  # Free Parking / Visit Jail, etc.

    # ------------------------------------------------------------------ #
    # Helpers
    def _get_asset(self, space_id):
        asset = (
            self.session.query(models.Asset)
            .filter(models.Asset.space_id == space_id)
            .first()
        )
        if asset is None:
            raise ValueError(f"No asset found for space_id={space_id}")
        return asset

    def _get_asset_state(self, asset_id):
        state = (
            self.session.query(models.AssetState)
            .filter_by(game_id=self.game_id, asset_id=asset_id)
            .first()
        )
        if state is None:
            raise ValueError(f"No asset state found for game_id={self.game_id}, asset_id={asset_id}")
        return state

    def _offer_purchase(self, player, asset, state, turn):
        price = asset.purchase_price or 0
        balance = self.ledger.player_balance(player.game_player_id)

        if balance < price:
            # TODO: trigger auction if desired
            return

        self.ledger.pay_bank(player, price, "property_purchase", turn.turn_id, asset_id=asset.asset_id)
        state.owner_game_player_id = player.game_player_id
        state.is_mortgaged = False
        state.improvement_level = 0
        state.has_hotel = False
        self.session.flush()

    def _collect_rent(self, player, state, asset, turn):
        rent = self._calculate_rent(asset, state)
        if rent <= 0:
            return
        self.ledger.transfer(
            payer=player,
            payee_id=state.owner_game_player_id,
            amount=rent,
            txn_type="rent",
            turn_id=turn.turn_id,
            asset_id=asset.asset_id,
        )

    def _calculate_rent(self, asset, state):
        if state.is_mortgaged:
            return 0

        if state.has_hotel and asset.rent_hotel:
            return asset.rent_hotel

        level = state.improvement_level or 0
        if level == 0:
            if self._owner_has_full_group(state.owner_game_player_id, asset):
                return asset.rent_group or asset.rent_base or 0
            return asset.rent_base or 0
        elif level == 1:
            return asset.rent_house_1 or asset.rent_base or 0
        elif level == 2:
            return asset.rent_house_2 or 0
        elif level == 3:
            return asset.rent_house_3 or 0
        elif level == 4:
            return asset.rent_house_4 or 0
        return asset.rent_base or 0

    def _transport_rent(self, asset, owner_id):
        owned = self._count_assets_owned(owner_id, "transport")
        if owned <= 1:
            return asset.rent_base or 0
        elif owned == 2:
            return asset.rent_tier_2 or asset.rent_base or 0
        elif owned == 3:
            return asset.rent_tier_3 or asset.rent_tier_2 or asset.rent_base or 0
        else:
            return asset.rent_tier_4 or asset.rent_tier_3 or asset.rent_tier_2 or asset.rent_base or 0

    def _count_assets_owned(self, owner_id, asset_type):
        return (
            self.session.query(func.count(models.AssetState.asset_state_id))
            .join(models.Asset, models.Asset.asset_id == models.AssetState.asset_id)
            .filter(
                models.AssetState.game_id == self.game_id,
                models.AssetState.owner_game_player_id == owner_id,
                models.AssetState.is_mortgaged == False,
                models.Asset.asset_type == asset_type,
            )
            .scalar()
        ) or 0

    def _owner_has_both_utilities(self, owner_id):
        return self._count_assets_owned(owner_id, "utility") >= 2

    def _owner_has_full_group(self, owner_id, asset):
        """Returns True if owner controls every property in the asset's group (and none are mortgaged)."""
        space = (
            self.session.query(models.Space)
            .filter(models.Space.space_id == asset.space_id)
            .first()
        )
        if not space or not space.group_id:
            return False

        total_in_group = (
            self.session.query(func.count(models.Space.space_id))
            .filter(models.Space.group_id == space.group_id)
            .scalar()
        )

        owned_in_group = (
            self.session.query(func.count(models.AssetState.asset_state_id))
            .join(models.Asset, models.Asset.asset_id == models.AssetState.asset_id)
            .join(models.Space, models.Space.space_id == models.Asset.space_id)
            .filter(
                models.AssetState.game_id == self.game_id,
                models.AssetState.owner_game_player_id == owner_id,
                models.AssetState.is_mortgaged == False,
                models.Space.group_id == space.group_id,
            )
            .scalar()
        )

        return owned_in_group == total_in_group

    def _send_player_to_jail(self, player, turn):
        player.in_jail = True
        player.jail_turns = 0
        player.current_space_id = JAIL_SPACE_ID

    def resolve_from_card(self, player, space, turn, passed_start, rent_multiplier=None, skip_cards=False):
        prev_multiplier = getattr(self, "_temp_rent_multiplier", None)
        prev_skip_cards = getattr(self, "_skip_card_spaces", False)

        self._temp_rent_multiplier = rent_multiplier
        self._skip_card_spaces = skip_cards

        try:
            handler = getattr(self, f"_handle_{space.space_type}", self._handle_default)
            handler(player, space, turn, passed_start)
        finally:
            self._temp_rent_multiplier = prev_multiplier
            self._skip_card_spaces = prev_skip_cards     