import pytest
from app.services.arbitrage_engine import arbitrage_engine

def test_multi_tier_execution_simulation():
    # Scenario from user specification:
    # 10 skins bought at $4.00 (400 cents) on CSFloat
    # Steam Order book tiers:
    #   $5.20 (520c) x 1
    #   $5.15 (515c) x 3
    #   $5.10 (510c) x 6
    #   $5.00 (500c) x 20
    order_book_tiers = [
        (520, 1),
        (515, 3),
        (510, 6),
        (500, 20)
    ]
    target_qty = 10
    csfloat_price_cents = 400

    result = arbitrage_engine.calculate_execution_value(
        target_quantity=target_qty,
        order_book_tiers=order_book_tiers,
        csfloat_price_cents=csfloat_price_cents
    )

    assert result["target_quantity"] == 10
    assert result["fulfilled_quantity"] == 10
    assert result["is_fully_fulfilled"] is True
    assert result["total_cost_csfloat_usd"] == 40.00

    # Gross proceeds: 1*5.20 + 3*5.15 + 6*5.10 = 5.20 + 15.45 + 30.60 = $51.25
    assert result["gross_execution_value_usd"] == 51.25
    assert result["total_gross_profit_usd"] == 11.25
    assert result["effective_gross_roi_percent"] == 28.12  # 11.25 / 40 * 100

    # Net proceeds:
    # 520c net = 452c
    # 515c net = 447c * 3 = 1341c
    # 510c net = 443c * 6 = 2658c
    # Total net proceeds = 452 + 1341 + 2658 = 4451c ($44.51)
    assert result["net_execution_value_usd"] == 44.51
    assert result["total_net_profit_usd"] == 4.51
    assert result["effective_net_roi_percent"] == 11.28  # 4.51 / 40 * 100
    assert len(result["filled_tiers"]) == 3

def test_partial_orderbook_fill():
    # Only 3 total units in order book when user wants 5
    order_book_tiers = [
        (1000, 1),
        (900, 2)
    ]
    result = arbitrage_engine.calculate_execution_value(
        target_quantity=5,
        order_book_tiers=order_book_tiers,
        csfloat_price_cents=700
    )

    assert result["target_quantity"] == 5
    assert result["fulfilled_quantity"] == 3
    assert result["is_fully_fulfilled"] is False
    assert result["total_cost_csfloat_usd"] == 21.00 # 3 * $7.00
    assert result["gross_execution_value_usd"] == 28.00 # 10.00 + 18.00

def test_empty_orderbook():
    result = arbitrage_engine.calculate_execution_value(
        target_quantity=5,
        order_book_tiers=[],
        csfloat_price_cents=500
    )
    assert result["fulfilled_quantity"] == 0
    assert result["is_fully_fulfilled"] is False
    assert result["gross_execution_value_usd"] == 0.0

def test_liquidity_score_calculation():
    # High liquidity: top tier >= 10
    score_high = arbitrage_engine.calculate_liquidity_score(
        highest_bid_cents=1000,
        order_book_tiers=[(1000, 15), (990, 20)],
        total_buy_orders=500
    )
    assert score_high == "HIGH"

    # Medium liquidity: top tier = 4
    score_med = arbitrage_engine.calculate_liquidity_score(
        highest_bid_cents=1000,
        order_book_tiers=[(1000, 4), (990, 5)],
        total_buy_orders=50
    )
    assert score_med == "MEDIUM"

    # Low liquidity: top tier = 1, shallow depth
    score_low = arbitrage_engine.calculate_liquidity_score(
        highest_bid_cents=1000,
        order_book_tiers=[(1000, 1), (900, 1)],
        total_buy_orders=5
    )
    assert score_low == "LOW"
