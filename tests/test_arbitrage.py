import pytest
from datetime import datetime, timezone, timedelta
from app.services.arbitrage_engine import arbitrage_engine

def test_profit_and_roi_example_1():
    # Prompt specification test: CSFloat = $4.00 (400 cents), Steam = $6.00 (600 cents)
    csfloat_cents = 400
    steam_cents = 600

    profit = arbitrage_engine.calculate_gross_profit(steam_cents, csfloat_cents)
    roi = arbitrage_engine.calculate_gross_roi(steam_cents, csfloat_cents)

    assert profit == 2.00
    assert roi == 50.0

def test_profit_and_roi_example_2():
    # Prompt specification test: CSFloat = $27.00 (2700 cents), Steam = $32.00 (3200 cents)
    csfloat_cents = 2700
    steam_cents = 3200

    profit = arbitrage_engine.calculate_gross_profit(steam_cents, csfloat_cents)
    roi = arbitrage_engine.calculate_gross_roi(steam_cents, csfloat_cents)

    assert profit == 5.00
    assert pytest.approx(roi, 0.001) == 18.5185

def test_negative_spread():
    # CSFloat higher than Steam bid
    csfloat_cents = 1500
    steam_cents = 1000

    profit = arbitrage_engine.calculate_gross_profit(steam_cents, csfloat_cents)
    roi = arbitrage_engine.calculate_gross_roi(steam_cents, csfloat_cents)

    assert profit == -5.00
    assert roi == pytest.approx(-33.3333, 0.001)

def test_zero_price():
    roi = arbitrage_engine.calculate_gross_roi(500, 0)
    assert roi == 0.0

def test_steam_net_payout_and_net_roi():
    # CSFloat = $4.00 (400 cents), Steam = $5.20 (520 cents)
    # Steam seller receives = floor(520 / 1.15) = 452 cents ($4.52)
    seller_receives = arbitrage_engine.calculate_steam_seller_receives(520)
    assert seller_receives == 452

    net_profit = arbitrage_engine.calculate_net_profit(520, 400)
    assert net_profit == 0.52

    net_roi = arbitrage_engine.calculate_net_roi(520, 400)
    # Net profit = 52 cents on 400 cents => 13.0%
    assert net_roi == 13.0

def test_stale_data_evaluation():
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(seconds=150)
    fresh_time = now - timedelta(seconds=10)

    # Stale when older than 120s
    status_stale = arbitrage_engine.evaluate_status(
        csfloat_timestamp=old_time,
        steam_timestamp=fresh_time,
        max_data_age_seconds=120,
        has_active_listing=True,
        has_active_bid=True,
        is_name_matched=True
    )
    assert status_stale == "STALE"

    # Active when fresh
    status_active = arbitrage_engine.evaluate_status(
        csfloat_timestamp=fresh_time,
        steam_timestamp=fresh_time,
        max_data_age_seconds=120,
        has_active_listing=True,
        has_active_bid=True,
        is_name_matched=True
    )
    assert status_active == "ACTIVE"

    # Unverified when missing bid or name mismatch
    status_unverified = arbitrage_engine.evaluate_status(
        csfloat_timestamp=fresh_time,
        steam_timestamp=fresh_time,
        max_data_age_seconds=120,
        has_active_listing=True,
        has_active_bid=False,
        is_name_matched=True
    )
    assert status_unverified == "UNVERIFIED"
