"""AI 'thinking out loud' narration — truthful, rule-derived summaries shown
during the autopilot pacing pause. These must never mutate state."""
import json

import pytest

from app import models
from app.services.ai_service import AIPlayerService
from tests.conftest import drain_cash


def svc(session, game, name="Jim"):
    player = session.query(models.GamePlayer).get(game.players[name])
    return AIPlayerService(session, game.game_id, player)


def test_roll_summary_explains_upgrade_shortfall(session, game_factory):
    # Medium AI, all natural paddocks (can upgrade to improved), $600 — below
    # the $500 cost + $1500 buffer, so it rolls and says why.
    g = game_factory(sheep_per_paddock=3, starting_cash=2000, current="Jim")
    drain_cash(session, g.game_id, g.players["Jim"], 1400)  # -> $600
    s = svc(session, g)
    text = s.thinking_summary(("roll", g.players["Jim"]))
    assert "improve" in text.lower()
    assert "rolling" in text.lower()


def test_mortgage_summary(session, game_factory):
    g = game_factory(sheep_per_paddock=1, starting_cash=2000, current="Jim")
    drain_cash(session, g.game_id, g.players["Jim"], 1950)  # $50, cash crunch
    s = svc(session, g)
    text = s.thinking_summary(("mortgage", g.players["Jim"], 3))
    assert "paddock 3" in text and "mortgag" in text.lower()


def test_upgrade_summary_mentions_target(session, game_factory):
    g = game_factory(sheep_per_paddock=3, starting_cash=3000, current="Jim")
    s = svc(session, g)
    text = s.thinking_summary(("upgrade", g.players["Jim"], 2, "improved"))
    assert "paddock 2" in text and "improved" in text


def test_stock_sale_pending_summary_buy_vs_drought(session, game_factory, stock_sale_pending):
    g = game_factory(sheep_per_paddock=0, starting_cash=2800, current="Jim")
    s = svc(session, g)
    # Not in drought, under pen goal, cash available -> "looking to buy".
    p_buy = stock_sale_pending(g.game_id, g.players["Jim"], card_prices=(400,))
    assert "buy" in s.pending_thinking_summary(p_buy).lower()
    # In drought -> leans toward passing.
    jim = session.query(models.GamePlayer).get(g.players["Jim"])
    jim.is_in_drought = True
    session.commit()
    p_drought = stock_sale_pending(g.game_id, g.players["Jim"], card_prices=(400,),
                                   in_drought=True)
    assert "drought" in s.pending_thinking_summary(p_drought).lower()


def test_summary_is_read_only(session, game_factory, stock_sale_pending):
    g = game_factory(sheep_per_paddock=3, starting_cash=2000, current="Jim")
    s = svc(session, g)
    before = (
        session.query(models.GamePlayer).get(g.players["Jim"]).is_in_drought,
        sum(p.sheep_pens for p in session.query(models.Paddock).filter_by(game_id=g.game_id)),
        session.query(models.Transaction).filter_by(game_id=g.game_id).count(),
    )
    s.thinking_summary(("roll", g.players["Jim"]))
    p = stock_sale_pending(g.game_id, g.players["Jim"], card_prices=(400,))
    s.pending_thinking_summary(p)
    after = (
        session.query(models.GamePlayer).get(g.players["Jim"]).is_in_drought,
        sum(pk.sheep_pens for pk in session.query(models.Paddock).filter_by(game_id=g.game_id)),
        session.query(models.Transaction).filter_by(game_id=g.game_id).count(),
    )
    assert before == after
