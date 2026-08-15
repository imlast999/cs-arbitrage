import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.schema import Skin, CSFloatListing, SteamOrderBook, Opportunity
from app.services.arbitrage_engine import arbitrage_engine

@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        # Seed test items
        skin1 = Skin(market_hash_name="AK-47 | Redline (Field-Tested)", weapon="AK-47", skin_name="Redline", exterior="Field-Tested")
        skin2 = Skin(market_hash_name="AWP | Safari Mesh (Field-Tested)", weapon="AWP", skin_name="Safari Mesh", exterior="Field-Tested")
        skin3 = Skin(market_hash_name="M4A1-S | Printstream (Field-Tested)", weapon="M4A1-S", skin_name="Printstream", exterior="Field-Tested")
        db.add_all([skin1, skin2, skin3])
        db.flush()

        opp1 = Opportunity(
            skin_id=skin1.id,
            csfloat_price_cents=400,
            steam_highest_bid_cents=600,
            gross_profit_usd=2.00,
            net_profit_usd=1.21,
            gross_roi_percent=50.0,
            net_roi_percent=30.25,
            available_quantity=10,
            liquidity_score="HIGH",
            status="ACTIVE",
            updated_at=datetime.now(timezone.utc)
        )
        opp2 = Opportunity(
            skin_id=skin2.id,
            csfloat_price_cents=10,
            steam_highest_bid_cents=12,
            gross_profit_usd=0.02,
            net_profit_usd=0.00,
            gross_roi_percent=20.0,
            net_roi_percent=0.0,
            available_quantity=500,
            liquidity_score="HIGH",
            status="ACTIVE",
            updated_at=datetime.now(timezone.utc)
        )
        opp3 = Opportunity(
            skin_id=skin3.id,
            csfloat_price_cents=20000,
            steam_highest_bid_cents=21000,
            gross_profit_usd=10.00,
            net_profit_usd=-17.39,
            gross_roi_percent=5.0,
            net_roi_percent=-8.69,
            available_quantity=1,
            liquidity_score="LOW",
            status="ACTIVE",
            updated_at=datetime.now(timezone.utc)
        )
        db.add_all([opp1, opp2, opp3])
        db.commit()
        yield db
    finally:
        db.close()

def test_filter_min_roi(test_db):
    # Only opp1 (50%) and opp2 (20%) have gross ROI >= 20%
    opps = test_db.query(Opportunity).filter(Opportunity.gross_roi_percent >= 20.0).all()
    assert len(opps) == 2

def test_filter_max_price(test_db):
    # Max price $10.00 (1000 cents) -> opp1 (400) and opp2 (10)
    opps = test_db.query(Opportunity).filter(Opportunity.csfloat_price_cents <= 1000).all()
    assert len(opps) == 2

def test_filter_min_profit(test_db):
    # Min profit $1.00 -> opp1 ($2.00) and opp3 ($10.00)
    opps = test_db.query(Opportunity).filter(Opportunity.gross_profit_usd >= 1.00).all()
    assert len(opps) == 2

def test_filter_liquidity(test_db):
    # Only HIGH liquidity -> opp1 and opp2
    opps = test_db.query(Opportunity).filter(Opportunity.liquidity_score == "HIGH").all()
    assert len(opps) == 2

def test_sort_by_gross_roi(test_db):
    opps = test_db.query(Opportunity).order_by(Opportunity.gross_roi_percent.desc()).all()
    assert opps[0].gross_roi_percent == 50.0
    assert opps[1].gross_roi_percent == 20.0
    assert opps[2].gross_roi_percent == 5.0
