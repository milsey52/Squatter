# app/services/stock_sale_service.py
import random
from sqlalchemy.orm import Session
from sqlalchemy import func
from app import models
from app.constants import MAX_PENS_PER_TRANSACTION


class StockSaleService:
    def __init__(self, session: Session, game_id: int):
        self.session = session
        self.game_id = game_id

    def draw_stock_card(self, turn_id: int) -> models.StockCard:
        """Draw a random stock card and record it."""
        all_cards = self.session.query(models.StockCard).all()
        if not all_cards:
            raise RuntimeError("No stock cards in database")

        card = random.choice(all_cards)

        draw_order = (
            self.session.query(func.coalesce(func.max(models.StockCardDraw.draw_order), 0))
            .filter_by(game_id=self.game_id)
            .scalar()
        ) + 1

        draw = models.StockCardDraw(
            game_id=self.game_id,
            turn_id=turn_id,
            stock_card_id=card.stock_card_id,
            draw_order=draw_order,
        )
        self.session.add(draw)
        self.session.flush()
        return card

    def get_card_for_turn(self, turn_id: int):
        """Get the stock card drawn for a specific turn."""
        draw = (
            self.session.query(models.StockCardDraw)
            .filter_by(game_id=self.game_id, turn_id=turn_id)
            .order_by(models.StockCardDraw.draw_order.desc())
            .first()
        )
        if draw:
            return draw.stock_card
        return None

    def get_buy_price(self, stock_card: models.StockCard, modifier_pct: int = 0) -> int:
        """Get buy price per pen, applying any modifier."""
        price = stock_card.buy_price_per_pen
        if modifier_pct:
            price = int(price * (1 + modifier_pct / 100))
        return price

    def get_sell_price(self, stock_card: models.StockCard, pasture_type: str,
                       modifier_pct: int = 0) -> int:
        """Get sell price per pen based on pasture type, applying any modifier."""
        if pasture_type == "natural":
            price = stock_card.sell_price_natural
        else:
            price = stock_card.sell_price_improved_irrigated
        if modifier_pct:
            price = int(price * (1 + modifier_pct / 100))
        return price

    def validate_transaction(self, pens: int):
        """Validate that the number of pens is within limits."""
        if pens < 1:
            raise ValueError("Must buy or sell at least 1 pen")
        if pens > MAX_PENS_PER_TRANSACTION:
            raise ValueError(f"Maximum {MAX_PENS_PER_TRANSACTION} pens per transaction")

    def get_last_drawn_card(self):
        """Get the most recently drawn stock card for this game."""
        draw = (
            self.session.query(models.StockCardDraw)
            .filter_by(game_id=self.game_id)
            .order_by(models.StockCardDraw.draw_order.desc())
            .first()
        )
        if draw:
            return draw.stock_card
        return None
