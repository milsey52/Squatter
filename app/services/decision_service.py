# app/services/decision_service.py
import json
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from app import models
from app.services.ledger_service import LedgerService

MIN_BID_INCREMENT = 10


class DecisionService:
    def __init__(self, session: Session, game_id: int):
        self.session = session
        self.game_id = game_id
        self.ledger = LedgerService(session, game_id)

    def get_pending_action(self) -> Optional[models.PendingAction]:
        """Get current unresolved pending action for the game."""
        return (
            self.session.query(models.PendingAction)
            .filter(
                models.PendingAction.game_id == self.game_id,
                models.PendingAction.resolved_at.is_(None),
            )
            .first()
        )

    def buy_property(self, player_id: int) -> dict:
        """Execute purchase and resolve the pending action."""
        pending = self.get_pending_action()
        if not pending:
            raise ValueError("No pending action")
        if pending.action_type != "purchase_decision":
            raise ValueError("Pending action is not a purchase decision")
        if pending.active_player_id != player_id:
            raise ValueError("Not this player's decision")

        asset = self.session.query(models.Asset).get(pending.asset_id)
        state = (
            self.session.query(models.AssetState)
            .filter_by(game_id=self.game_id, asset_id=pending.asset_id)
            .first()
        )
        player = self.session.query(models.GamePlayer).get(player_id)

        price = asset.purchase_price or 0
        balance = self.ledger.player_balance(player_id)

        if balance < price:
            raise ValueError(f"Insufficient funds: need ${price}, have ${balance}")

        # Execute purchase
        self.ledger.pay_bank(
            player, price, "property_purchase", pending.turn_id, asset_id=asset.asset_id
        )
        state.owner_game_player_id = player_id
        state.is_mortgaged = False
        state.improvement_level = 0
        state.has_hotel = False

        # Resolve pending action
        pending.resolved_at = func.now()
        self.session.flush()

        space = self.session.query(models.Space).filter_by(space_id=asset.space_id).first()
        return {"status": "purchased", "property": space.name if space else f"Asset {asset.asset_id}", "price": price}

    def pass_property(self, player_id: int) -> dict:
        """Player passes on purchase - start auction."""
        pending = self.get_pending_action()
        if not pending:
            raise ValueError("No pending action")
        if pending.action_type != "purchase_decision":
            raise ValueError("Pending action is not a purchase decision")
        if pending.active_player_id != player_id:
            raise ValueError("Not this player's decision")

        # Get house rules to check if auctions are enabled
        house_rules = (
            self.session.query(models.HouseRule)
            .filter_by(game_id=self.game_id)
            .first()
        )

        if not house_rules or not house_rules.allow_auctions:
            # Auctions disabled - just resolve the action
            pending.resolved_at = func.now()
            self.session.flush()
            return {"status": "passed", "auction": False}

        # Start auction
        return self._start_auction(pending)

    def _start_auction(self, pending: models.PendingAction) -> dict:
        """Initialize auction state."""
        # Get all active players in turn order
        players = (
            self.session.query(models.GamePlayer)
            .filter(
                models.GamePlayer.game_id == self.game_id,
                models.GamePlayer.is_active == True,
            )
            .order_by(models.GamePlayer.turn_order)
            .all()
        )

        # Find the player who passed and start auction from the next player
        passer_order = None
        for p in players:
            if p.game_player_id == pending.active_player_id:
                passer_order = p.turn_order
                break

        # Build bidders list starting from next player after the passer
        bidder_ids = []
        for p in players:
            bidder_ids.append(p.game_player_id)

        # Rotate so next player after passer is first
        if passer_order is not None:
            # Find index of next player
            next_idx = 0
            for i, p in enumerate(players):
                if p.turn_order > passer_order:
                    next_idx = i
                    break
                if i == len(players) - 1:
                    next_idx = 0  # wrap to first player
            bidder_ids = [players[(next_idx + i) % len(players)].game_player_id for i in range(len(players))]

        # Starting bid is 25% of purchase price
        asset = self.session.query(models.Asset).get(pending.asset_id)
        starting_bid = int((asset.purchase_price or 0) * 0.25)

        auction_data = {
            "current_bid": 0,
            "current_bidder_id": None,
            "starting_bid": starting_bid,
            "bidder_order": bidder_ids,
            "active_bidders": bidder_ids.copy(),
            "current_bidder_index": 0,
        }

        pending.action_type = "auction"
        pending.action_data = json.dumps(auction_data)
        self.session.flush()

        return {
            "status": "auction_started",
            "asset_id": pending.asset_id,
            "current_bidder_id": bidder_ids[0] if bidder_ids else None,
        }

    def place_bid(self, player_id: int, amount: int) -> dict:
        """Record bid and rotate to next bidder."""
        pending = self.get_pending_action()
        if not pending:
            raise ValueError("No pending action")
        if pending.action_type != "auction":
            raise ValueError("No active auction")

        auction = json.loads(pending.action_data)
        active_bidders = auction["active_bidders"]
        current_idx = auction["current_bidder_index"]

        if not active_bidders:
            raise ValueError("No active bidders")

        expected_bidder = active_bidders[current_idx % len(active_bidders)]
        if player_id != expected_bidder:
            raise ValueError("Not this player's turn to bid")

        # Validate bid amount
        current_bid = auction["current_bid"]
        starting_bid = auction.get("starting_bid", 1)
        min_bid = current_bid + MIN_BID_INCREMENT if current_bid > 0 else starting_bid
        if amount < min_bid:
            raise ValueError(f"Bid must be at least ${min_bid}")

        # Check player can afford it
        balance = self.ledger.player_balance(player_id)
        if balance < amount:
            raise ValueError(f"Insufficient funds: need ${amount}, have ${balance}")

        # Record bid
        auction["current_bid"] = amount
        auction["current_bidder_id"] = player_id
        auction["current_bidder_index"] = (current_idx + 1) % len(active_bidders)

        pending.action_data = json.dumps(auction)
        self.session.flush()

        next_bidder = active_bidders[auction["current_bidder_index"]]
        return {
            "status": "bid_placed",
            "amount": amount,
            "bidder_id": player_id,
            "next_bidder_id": next_bidder,
            "current_bid": amount,
        }

    def pass_auction(self, player_id: int) -> dict:
        """Player passes - remove from auction, check if auction ends."""
        pending = self.get_pending_action()
        if not pending:
            raise ValueError("No pending action")
        if pending.action_type != "auction":
            raise ValueError("No active auction")

        auction = json.loads(pending.action_data)
        active_bidders = auction["active_bidders"]
        current_idx = auction["current_bidder_index"]

        if not active_bidders:
            raise ValueError("No active bidders")

        expected_bidder = active_bidders[current_idx % len(active_bidders)]
        if player_id != expected_bidder:
            raise ValueError("Not this player's turn to bid")

        # Remove player from active bidders
        active_bidders.remove(player_id)
        auction["active_bidders"] = active_bidders

        # Adjust index if needed
        if active_bidders:
            auction["current_bidder_index"] = current_idx % len(active_bidders)

        pending.action_data = json.dumps(auction)
        self.session.flush()

        # Check if auction ends
        if len(active_bidders) <= 1:
            return self._resolve_auction(pending, auction)

        next_bidder = active_bidders[auction["current_bidder_index"]]
        return {
            "status": "passed",
            "player_id": player_id,
            "remaining_bidders": len(active_bidders),
            "next_bidder_id": next_bidder,
        }

    def _resolve_auction(self, pending: models.PendingAction, auction: dict) -> dict:
        """Award property to highest bidder or return to bank."""
        winner_id = auction.get("current_bidder_id")
        winning_bid = auction.get("current_bid", 0)

        asset = self.session.query(models.Asset).get(pending.asset_id)
        state = (
            self.session.query(models.AssetState)
            .filter_by(game_id=self.game_id, asset_id=pending.asset_id)
            .first()
        )
        space = self.session.query(models.Space).filter_by(space_id=asset.space_id).first()
        property_name = space.name if space else f"Asset {asset.asset_id}"

        if winner_id and winning_bid > 0:
            # Award to winner
            winner = self.session.query(models.GamePlayer).get(winner_id)
            self.ledger.pay_bank(
                winner, winning_bid, "auction_purchase", pending.turn_id, asset_id=asset.asset_id
            )
            state.owner_game_player_id = winner_id
            state.is_mortgaged = False
            state.improvement_level = 0
            state.has_hotel = False

            pending.resolved_at = func.now()
            self.session.flush()

            return {
                "status": "auction_won",
                "winner_id": winner_id,
                "winner_name": winner.player_name,
                "property": property_name,
                "price": winning_bid,
            }
        else:
            # No winner - property stays unowned
            pending.resolved_at = func.now()
            self.session.flush()

            return {
                "status": "auction_no_winner",
                "property": property_name,
            }

    def get_auction_state(self) -> Optional[dict]:
        """Get current auction state for frontend display."""
        pending = self.get_pending_action()
        if not pending:
            return None

        asset = self.session.query(models.Asset).get(pending.asset_id)
        space = self.session.query(models.Space).filter_by(space_id=asset.space_id).first()
        property_name = space.name if space else f"Asset {asset.asset_id}"

        result = {
            "action_type": pending.action_type,
            "asset_id": pending.asset_id,
            "property_name": property_name,
            "purchase_price": asset.purchase_price,
            "active_player_id": pending.active_player_id,
        }

        if pending.action_type == "auction" and pending.action_data:
            auction = json.loads(pending.action_data)
            current_bid = auction.get("current_bid", 0)
            starting_bid = auction.get("starting_bid", int((asset.purchase_price or 0) * 0.25))
            result["current_bid"] = current_bid
            result["current_bidder_id"] = auction.get("current_bidder_id")
            result["active_bidders"] = auction.get("active_bidders", [])
            result["starting_bid"] = starting_bid
            current_idx = auction.get("current_bidder_index", 0)
            active_bidders = auction.get("active_bidders", [])
            if active_bidders:
                result["next_bidder_id"] = active_bidders[current_idx % len(active_bidders)]
            result["min_bid"] = (current_bid + MIN_BID_INCREMENT) if current_bid > 0 else starting_bid

        return result
