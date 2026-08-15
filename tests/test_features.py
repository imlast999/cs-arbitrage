import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, init_db
from app.models.schema import UserConnection, FavoriteSkin, TradeRecord

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    db = SessionLocal()
    # Clean up test records
    db.query(FavoriteSkin).delete()
    db.query(TradeRecord).delete()
    db.commit()
    db.close()

def test_connections_status():
    resp = client.get("/api/connections")
    assert resp.status_code == 200
    data = resp.json()
    assert "csfloat" in data
    assert "steam" in data
    assert "is_connected" in data["csfloat"]
    assert "is_connected" in data["steam"]

def test_steam_connect_and_disconnect():
    connect_payload = {
        "account_name": "TraderPro",
        "trade_url": "https://steamcommunity.com/tradeoffer/new/?partner=123456&token=abcdef",
        "steam_id": "76561198000000000"
    }
    resp = client.post("/api/connections/steam", json=connect_payload)
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Verify status
    resp = client.get("/api/connections")
    data = resp.json()
    assert data["steam"]["is_connected"] is True
    assert data["steam"]["account_name"] == "TraderPro"

    # Disconnect
    resp = client.delete("/api/connections/steam")
    assert resp.status_code == 200
    resp = client.get("/api/connections")
    assert resp.json()["steam"]["is_connected"] is False

def test_favorites_workflow():
    # Add favorite
    add_resp = client.post("/api/favorites", json={
        "market_hash_name": "AK-47 | Redline (Field-Tested)",
        "notes": "Low float target"
    })
    assert add_resp.status_code == 200
    fav_data = add_resp.json()
    assert fav_data["market_hash_name"] == "AK-47 | Redline (Field-Tested)"

    # List favorites
    list_resp = client.get("/api/favorites")
    assert list_resp.status_code == 200
    favs = list_resp.json()
    assert len(favs) == 1
    assert favs[0]["market_hash_name"] == "AK-47 | Redline (Field-Tested)"

    # Delete favorite by name
    del_resp = client.delete("/api/favorites/by-name/AK-47%20%7C%20Redline%20%28Field-Tested%29")
    assert del_resp.status_code == 200

    # Verify empty
    list_resp = client.get("/api/favorites")
    assert len(list_resp.json()) == 0

def test_trades_pnl_workflow():
    # Record trade
    trade_payload = {
        "market_hash_name": "AWP | Atheris (Field-Tested)",
        "buy_price_usd": 4.50,
        "target_sell_price_usd": 7.00,
        "status": "IN_TRADE_LOCK",
        "notes": "Fast flip"
    }
    trade_resp = client.post("/api/trades", json=trade_payload)
    assert trade_resp.status_code == 200
    trade = trade_resp.json()
    assert trade["market_hash_name"] == "AWP | Atheris (Field-Tested)"
    assert trade["buy_price_usd"] == 4.50
    assert trade["status"] == "IN_TRADE_LOCK"

    # List trades & summary
    summary_resp = client.get("/api/trades")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_trades"] == 1
    assert summary["active_trades"] == 1
    assert summary["total_invested_usd"] == 4.50

    # Update trade to completed
    trade_id = trade["id"]
    update_resp = client.patch(f"/api/trades/{trade_id}", json={
        "status": "COMPLETED",
        "actual_sell_price_usd": 7.50
    })
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["status"] == "COMPLETED"
    assert updated["actual_sell_price_usd"] == 7.50

    # Verify summary after completion
    summary_resp = client.get("/api/trades")
    summary = summary_resp.json()
    assert summary["completed_trades"] == 1
    assert summary["active_trades"] == 0
    assert summary["total_realized_profit_usd"] > 0

def test_steam_inventory_endpoint():
    # When not connected
    client.delete("/api/connections/steam")
    resp = client.get("/api/steam/inventory")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_connected"] is False

    # When connected
    client.post("/api/connections/steam", json={"steam_id": "76561198000000000", "account_name": "TestUser"})
    resp = client.get("/api/steam/inventory")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_connected"] is True
    assert "total_liquidation_usd" in data
    assert "items" in data

def test_cashout_opportunities_endpoint():
    from app.models.schema import Skin, SteamOrderBook, CSFloatListing
    db = SessionLocal()
    skin = db.query(Skin).filter(Skin.market_hash_name == "AK-47 | Slate (Field-Tested)").first()
    if not skin:
        skin = Skin(market_hash_name="AK-47 | Slate (Field-Tested)")
        db.add(skin)
        db.flush()

    st_book = db.query(SteamOrderBook).filter(SteamOrderBook.skin_id == skin.id).first()
    if not st_book:
        st_book = SteamOrderBook(
            skin_id=skin.id,
            lowest_sell_order_cents=500,  # Steam cost $5.00
            highest_buy_order_cents=450
        )
        db.add(st_book)
    else:
        st_book.lowest_sell_order_cents = 500
        st_book.highest_buy_order_cents = 450

    cs_listing = db.query(CSFloatListing).filter(CSFloatListing.skin_id == skin.id).first()
    if not cs_listing:
        cs_listing = CSFloatListing(
            skin_id=skin.id,
            listing_id="cs_123",
            price_cents=450  # CSFloat price $4.50 -> Net after 2% is $4.41 -> 88.2% retention
        )
        db.add(cs_listing)
    else:
        cs_listing.price_cents = 450

    db.commit()
    db.close()

    resp = client.get("/api/cashout-opportunities")
    assert resp.status_code == 200
    opps = resp.json()
    assert len(opps) >= 1
    found = next((o for o in opps if o["skin"]["market_hash_name"] == "AK-47 | Slate (Field-Tested)"), None)
    assert found is not None
    assert found["steam_lowest_ask_usd"] == 5.00
    assert found["csfloat_price_usd"] == 4.50
    assert found["cashout_ratio_percent"] > 85.0

def test_steam_openid_login_and_callback():
    # Test openid redirect
    resp = client.get("/api/auth/steam/login", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "steamcommunity.com/openid/login" in resp.headers["location"]

    # Test openid callback with claimed_id
    cb_resp = client.get("/api/auth/steam/callback?openid.claimed_id=https://steamcommunity.com/openid/id/76561198012345678", follow_redirects=False)
    assert cb_resp.status_code in (302, 307)
    assert "steam_connected=1" in cb_resp.headers["location"]

    # Verify user connection was updated
    status_resp = client.get("/api/connections")
    data = status_resp.json()
    assert data["steam"]["is_connected"] is True
    assert data["steam"]["account_id"] == "76561198012345678"

def test_steam_sell_item_without_session():
    # Calling sell without session cookies returns requires_session: True
    sell_resp = client.post("/api/steam/sell-item", json={"asset_id": "123456789", "price_cents": 500})
    assert sell_resp.status_code == 200
    data = sell_resp.json()
    assert data["success"] is False
    assert data.get("requires_session") is True
