import pytest
from app.services.arbitrage_engine import arbitrage_engine

def test_steam_fee_edge_cases():
    # Very small item (e.g. 3 cents)
    payout_3c = arbitrage_engine.calculate_steam_seller_receives(3)
    assert payout_3c == 1

    # $1.00 (100 cents) -> 100 / 1.15 = ~86.95 -> 86 cents
    payout_100c = arbitrage_engine.calculate_steam_seller_receives(100)
    # 86 + max(1, floor(86*0.05)=4) + max(1, floor(86*0.10)=8) = 86 + 4 + 8 = 98 <= 100 -> 86 cents
    assert payout_100c == 86

    # $100.00 (10000 cents)
    payout_10k = arbitrage_engine.calculate_steam_seller_receives(10000)
    # 8695 cents
    assert payout_10k == 8695
    # Total Steam fee = 10000 - 8695 = 1305 cents = 13.05%
    fee_pct = (10000 - payout_10k) / 10000 * 100
    assert pytest.approx(fee_pct, 0.1) == 13.05

def test_zero_and_negative_prices():
    assert arbitrage_engine.calculate_steam_seller_receives(0) == 0
    assert arbitrage_engine.calculate_steam_seller_receives(-50) == 0
