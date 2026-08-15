import json
import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from app.config import settings
from app.database import get_db
from app.models.schema import (
    Skin, CSFloatListing, SteamOrderBook, Opportunity, OpportunityHistory,
    UserConnection, FavoriteSkin, TradeRecord
)
from app.schemas.api_models import (
    OpportunityResponse,
    OpportunityDetailResponse,
    SkinResponse,
    CSFloatListingResponse,
    SteamOrderBookResponse,
    OrderBookTier,
    SystemStatusResponse,
    ExecutionSimulationRequest,
    ExecutionSimulationResponse,
    ConnectionsResponse,
    ConnectionStatusItem,
    CSFloatConnectRequest,
    SteamConnectRequest,
    FavoriteCreateRequest,
    FavoriteItemResponse,
    TradeCreateRequest,
    TradeUpdateRequest,
    TradeRecordResponse,
    TradeSummaryResponse,
    CashoutOpportunityResponse
)
from app.services.scanner_service import scanner_service
from app.services.arbitrage_engine import arbitrage_engine
from app.services.csfloat_client import csfloat_client
from app.services.steam_client import steam_client

router = APIRouter(prefix="/api", tags=["Arbitrage API"])

@router.get("/status", response_model=SystemStatusResponse)
def get_system_status(db: Session = Depends(get_db)):
    """Returns real-time health, connection states, and scan metadata."""
    now = datetime.now(timezone.utc)
    last_scan = scanner_service.last_scan_timestamp
    sec_since_scan = int((now - last_scan).total_seconds()) if last_scan else None

    total_opps = db.query(Opportunity).count()
    active_opps = db.query(Opportunity).filter(Opportunity.status == "ACTIVE").count()

    cs_auth = "AUTHENTICATED" if csfloat_client.has_api_key() else "NO_API_KEY"

    return SystemStatusResponse(
        app_name="CS2 Arbitrage Scanner",
        version="1.0.0",
        csfloat_connected=(scanner_service.csfloat_status == "CONNECTED"),
        csfloat_auth_status=cs_auth,
        steam_connected=(scanner_service.steam_status == "CONNECTED"),
        steam_status=scanner_service.steam_status,
        total_opportunities=total_opps,
        active_opportunities=active_opps,
        last_scan_timestamp=last_scan,
        seconds_since_last_scan=sec_since_scan,
        is_scanning=scanner_service.is_scanning
    )

@router.get("/opportunities", response_model=List[OpportunityResponse])
def list_opportunities(
    min_roi: Optional[float] = Query(None, description="Minimum Gross ROI %"),
    min_net_roi: Optional[float] = Query(None, description="Minimum Net ROI %"),
    max_price: Optional[float] = Query(None, description="Maximum CSFloat Price in USD"),
    min_profit: Optional[float] = Query(None, description="Minimum Gross Profit in USD"),
    min_liquidity: Optional[str] = Query(None, description="Minimum Liquidity Score: LOW, MEDIUM, HIGH"),
    sort_by: Optional[str] = Query("roi_desc", description="Sorting criteria: roi_desc, net_roi_desc, profit_desc, price_asc"),
    db: Session = Depends(get_db)
):
    """Returns filtered and sorted arbitrage opportunities with live data freshness."""
    query = db.query(Opportunity).options(joinedload(Opportunity.skin))

    # Apply filters
    if min_roi is not None:
        query = query.filter(Opportunity.gross_roi_percent >= min_roi)
    if min_net_roi is not None:
        query = query.filter(Opportunity.net_roi_percent >= min_net_roi)
    if max_price is not None:
        query = query.filter(Opportunity.csfloat_price_cents <= int(max_price * 100))
    if min_profit is not None:
        query = query.filter(Opportunity.gross_profit_usd >= min_profit)
    if min_liquidity:
        min_liq_upper = min_liquidity.upper()
        if min_liq_upper == "HIGH":
            query = query.filter(Opportunity.liquidity_score == "HIGH")
        elif min_liq_upper == "MEDIUM":
            query = query.filter(Opportunity.liquidity_score.in_(["HIGH", "MEDIUM"]))

    # Apply Sorting
    if sort_by == "roi_desc":
        query = query.order_by(Opportunity.gross_roi_percent.desc())
    elif sort_by == "net_roi_desc":
        query = query.order_by(Opportunity.net_roi_percent.desc())
    elif sort_by == "profit_desc":
        query = query.order_by(Opportunity.gross_profit_usd.desc())
    elif sort_by == "net_profit_desc":
        query = query.order_by(Opportunity.net_profit_usd.desc())
    elif sort_by == "price_asc":
        query = query.order_by(Opportunity.csfloat_price_cents.asc())
    else:
        query = query.order_by(Opportunity.gross_roi_percent.desc())

    records = query.all()
    now = datetime.now(timezone.utc)

    results = []
    for opp in records:
        updated_utc = opp.updated_at if opp.updated_at.tzinfo else opp.updated_at.replace(tzinfo=timezone.utc)
        data_age = int((now - updated_utc).total_seconds())

        # Live status check for staleness
        status = opp.status
        if data_age > settings.MAX_DATA_AGE_SECONDS and status == "ACTIVE":
            status = "STALE"

        results.append(OpportunityResponse(
            id=opp.id,
            skin=SkinResponse.model_validate(opp.skin),
            csfloat_price_usd=round(opp.csfloat_price_cents / 100.0, 2),
            csfloat_price_cents=opp.csfloat_price_cents,
            steam_highest_bid_usd=round(opp.steam_highest_bid_cents / 100.0, 2),
            steam_highest_bid_cents=opp.steam_highest_bid_cents,
            gross_profit_usd=opp.gross_profit_usd,
            gross_roi_percent=opp.gross_roi_percent,
            net_profit_usd=opp.net_profit_usd,
            net_roi_percent=opp.net_roi_percent,
            available_quantity=opp.available_quantity,
            liquidity_score=opp.liquidity_score,
            status=status,
            data_age_seconds=data_age,
            updated_at=opp.updated_at
        ))

    return results

@router.get("/opportunities/{opportunity_id}", response_model=OpportunityDetailResponse)
def get_opportunity_detail(opportunity_id: int, db: Session = Depends(get_db)):
    """Returns complete details of an opportunity, including listing info, full order book, and direct links."""
    opp = db.query(Opportunity).options(joinedload(Opportunity.skin)).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    skin = opp.skin
    cs_listing = db.query(CSFloatListing).filter(CSFloatListing.skin_id == skin.id).first()
    st_book = db.query(SteamOrderBook).filter(SteamOrderBook.skin_id == skin.id).first()

    now = datetime.now(timezone.utc)
    updated_utc = opp.updated_at if opp.updated_at.tzinfo else opp.updated_at.replace(tzinfo=timezone.utc)
    data_age = int((now - updated_utc).total_seconds())

    # Parse order book tiers
    tiers: List[OrderBookTier] = []
    if st_book and st_book.order_book_json:
        try:
            raw_pairs = json.loads(st_book.order_book_json)
            for p, q in raw_pairs:
                net_payout = arbitrage_engine.calculate_steam_seller_receives(p)
                tiers.append(OrderBookTier(
                    price_cents=p,
                    price_usd=round(p / 100.0, 2),
                    quantity=q,
                    net_payout_usd=round(net_payout / 100.0, 2)
                ))
        except Exception:
            pass

    st_response = None
    if st_book:
        st_response = SteamOrderBookResponse(
            id=st_book.id,
            highest_buy_order_cents=st_book.highest_buy_order_cents,
            highest_buy_order_usd=round(st_book.highest_buy_order_cents / 100.0, 2) if st_book.highest_buy_order_cents else None,
            lowest_sell_order_cents=st_book.lowest_sell_order_cents,
            lowest_sell_order_usd=round(st_book.lowest_sell_order_cents / 100.0, 2) if st_book.lowest_sell_order_cents else None,
            total_buy_orders=st_book.total_buy_orders,
            tiers=tiers,
            updated_at=st_book.updated_at
        )

    cs_response = None
    if cs_listing:
        cs_response = CSFloatListingResponse(
            id=cs_listing.id,
            listing_id=cs_listing.listing_id,
            price_cents=cs_listing.price_cents,
            price_usd=round(cs_listing.price_cents / 100.0, 2),
            float_value=cs_listing.float_value,
            inspect_link=cs_listing.inspect_link,
            created_at=cs_listing.created_at
        )

    # Clean URL links
    encoded_name = urllib.parse.quote(skin.market_hash_name)
    steam_url = f"https://steamcommunity.com/market/listings/730/{encoded_name}"
    csfloat_url = f"https://csfloat.com/item/{cs_listing.listing_id}" if (cs_listing and cs_listing.listing_id) else f"https://csfloat.com/search?market_hash_name={encoded_name}"

    # Steam fee detail
    seller_receives_cents = arbitrage_engine.calculate_steam_seller_receives(opp.steam_highest_bid_cents)
    steam_fee_cents = opp.steam_highest_bid_cents - seller_receives_cents

    fee_breakdown = {
        "steam_highest_bid_usd": round(opp.steam_highest_bid_cents / 100.0, 2),
        "steam_total_fee_usd": round(steam_fee_cents / 100.0, 2),
        "steam_seller_receives_usd": round(seller_receives_cents / 100.0, 2),
        "steam_fee_rate_effective": f"{round((steam_fee_cents / opp.steam_highest_bid_cents) * 100, 2)}%" if opp.steam_highest_bid_cents > 0 else "0%",
        "csfloat_cost_usd": round(opp.csfloat_price_cents / 100.0, 2),
        "gross_profit_usd": opp.gross_profit_usd,
        "net_profit_usd": opp.net_profit_usd,
        "gross_roi_percent": opp.gross_roi_percent,
        "net_roi_percent": opp.net_roi_percent
    }

    return OpportunityDetailResponse(
        id=opp.id,
        skin=SkinResponse.model_validate(skin),
        csfloat_price_usd=round(opp.csfloat_price_cents / 100.0, 2),
        csfloat_price_cents=opp.csfloat_price_cents,
        steam_highest_bid_usd=round(opp.steam_highest_bid_cents / 100.0, 2),
        steam_highest_bid_cents=opp.steam_highest_bid_cents,
        gross_profit_usd=opp.gross_profit_usd,
        gross_roi_percent=opp.gross_roi_percent,
        net_profit_usd=opp.net_profit_usd,
        net_roi_percent=opp.net_roi_percent,
        available_quantity=opp.available_quantity,
        liquidity_score=opp.liquidity_score,
        status=opp.status,
        data_age_seconds=data_age,
        updated_at=opp.updated_at,
        csfloat_listing=cs_response,
        steam_order_book=st_response,
        csfloat_url=csfloat_url,
        steam_url=steam_url,
        fee_breakdown=fee_breakdown
    )

@router.post("/opportunities/{opportunity_id}/simulate", response_model=ExecutionSimulationResponse)
def simulate_execution(
    opportunity_id: int,
    req: ExecutionSimulationRequest,
    db: Session = Depends(get_db)
):
    """Simulates real execution against the multi-tier Steam order book for N items."""
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    st_book = db.query(SteamOrderBook).filter(SteamOrderBook.skin_id == opp.skin_id).first()
    if not st_book or not st_book.order_book_json:
        raise HTTPException(status_code=400, detail="No Steam Order Book data available for this item")

    raw_pairs = json.loads(st_book.order_book_json)
    sim_result = arbitrage_engine.calculate_execution_value(
        target_quantity=req.quantity,
        order_book_tiers=raw_pairs,
        csfloat_price_cents=opp.csfloat_price_cents
    )

    return ExecutionSimulationResponse(**sim_result)

@router.post("/scan")
async def trigger_scan(market_hash_name: Optional[str] = None):
    """Triggers an on-demand market scan."""
    result = await scanner_service.perform_scan(specific_market_hash_name=market_hash_name)
    return result

@router.get("/history")
def get_opportunity_history(
    skin_id: Optional[int] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db)
):
    """Returns historical snapshot records of detected opportunities."""
    query = db.query(OpportunityHistory)
    if skin_id is not None:
        query = query.filter(OpportunityHistory.skin_id == skin_id)

    records = query.order_by(OpportunityHistory.snapshot_at.desc()).limit(limit).all()

    return [
        {
            "id": r.id,
            "skin_id": r.skin_id,
            "csfloat_price_usd": round(r.csfloat_price_cents / 100.0, 2),
            "steam_highest_bid_usd": round(r.steam_highest_bid_cents / 100.0, 2),
            "gross_profit_usd": r.gross_profit_usd,
            "net_profit_usd": r.net_profit_usd,
            "gross_roi_percent": r.gross_roi_percent,
            "net_roi_percent": r.net_roi_percent,
            "liquidity_score": r.liquidity_score,
            "snapshot_at": r.snapshot_at
        }
        for r in records
    ]


# ==========================================
# CONNECTIONS (CSFloat & Steam)
# ==========================================

@router.get("/connections", response_model=ConnectionsResponse)
def get_connections(db: Session = Depends(get_db)):
    """Returns current independent connection status for CSFloat and Steam."""
    cs_conn = db.query(UserConnection).filter(UserConnection.provider == "csfloat").first()
    st_conn = db.query(UserConnection).filter(UserConnection.provider == "steam").first()

    # Fallback to runtime config if CSFloat key in settings
    cs_connected = bool((cs_conn and cs_conn.is_connected) or csfloat_client.has_api_key())
    cs_name = cs_conn.account_name if cs_conn else ("API Key Loaded" if cs_connected else None)
    cs_balance = cs_conn.balance_usd if cs_conn else 0.0

    st_connected = bool(st_conn and st_conn.is_connected)
    st_name = st_conn.account_name if st_conn else None
    st_id = st_conn.account_id if st_conn else None
    st_trade_url = st_conn.trade_url if st_conn else None

    return ConnectionsResponse(
        csfloat=ConnectionStatusItem(
            provider="csfloat",
            is_connected=cs_connected,
            account_name=cs_name,
            balance_usd=cs_balance,
            updated_at=cs_conn.updated_at if cs_conn else None
        ),
        steam=ConnectionStatusItem(
            provider="steam",
            is_connected=st_connected,
            account_name=st_name,
            account_id=st_id,
            trade_url=st_trade_url,
            updated_at=st_conn.updated_at if st_conn else None
        )
    )

@router.post("/connections/csfloat")
async def connect_csfloat(req: CSFloatConnectRequest, db: Session = Depends(get_db)):
    """Connects CSFloat with API key and updates scanner runtime."""
    key = req.api_key.strip()
    if len(key) < 5:
        raise HTTPException(status_code=400, detail="Invalid API key format")

    # Update runtime config
    csfloat_client.api_key = key
    settings.CSFLOAT_API_KEY = key

    # Test CSFloat query with key
    test_res = await csfloat_client.fetch_listings(limit=1)
    if test_res.get("auth_required") and not test_res.get("success"):
        raise HTTPException(status_code=401, detail="CSFloat rejected this API key. Please check your credentials.")

    conn = db.query(UserConnection).filter(UserConnection.provider == "csfloat").first()
    if not conn:
        conn = UserConnection(provider="csfloat")
        db.add(conn)

    conn.is_connected = True
    conn.api_key = key
    conn.account_name = "CSFloat API Key"
    conn.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {"success": True, "message": "CSFloat connection verified and active!"}

@router.delete("/connections/csfloat")
def disconnect_csfloat(db: Session = Depends(get_db)):
    """Disconnects CSFloat."""
    csfloat_client.api_key = ""
    settings.CSFLOAT_API_KEY = ""

    conn = db.query(UserConnection).filter(UserConnection.provider == "csfloat").first()
    if conn:
        conn.is_connected = False
        conn.api_key = None
        conn.account_name = None
        db.commit()

    return {"success": True, "message": "CSFloat disconnected successfully"}

@router.post("/connections/steam")
async def connect_steam(req: SteamConnectRequest, db: Session = Depends(get_db)):
    """Connects Steam with persona, Trade URL, and Steam ID."""
    conn = db.query(UserConnection).filter(UserConnection.provider == "steam").first()
    if not conn:
        conn = UserConnection(provider="steam")
        db.add(conn)

    resolved_id = None
    if req.steam_id:
        resolved_id = await steam_client.resolve_steam_id(req.steam_id)

    conn.is_connected = True
    conn.account_name = req.account_name.strip() if req.account_name else "Steam User"
    conn.account_id = resolved_id or (req.steam_id.strip() if req.steam_id else None)
    conn.trade_url = req.trade_url.strip() if req.trade_url else None
    conn.api_key = req.api_key.strip() if req.api_key else None
    conn.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {
        "success": True,
        "steam_id64": conn.account_id,
        "message": f"Cuenta de Steam '{conn.account_name}' conectada con éxito!"
    }

@router.delete("/connections/steam")
def disconnect_steam(db: Session = Depends(get_db)):
    """Disconnects Steam."""
    conn = db.query(UserConnection).filter(UserConnection.provider == "steam").first()
    if conn:
        conn.is_connected = False
        conn.account_name = None
        conn.account_id = None
        conn.trade_url = None
        conn.api_key = None
        db.commit()

    return {"success": True, "message": "Steam disconnected successfully"}

@router.get("/steam/inventory")
async def get_steam_inventory(db: Session = Depends(get_db)):
    """Fetches user's CS2 Steam Inventory and matches every item against active Steam Buy Limits."""
    conn = db.query(UserConnection).filter(UserConnection.provider == "steam").first()
    if not conn or not conn.is_connected or not conn.account_id:
        return {
            "success": False,
            "is_connected": False,
            "error": "Debes conectar tu cuenta de Steam con tu SteamID64 o link de perfil para cargar tu inventario y liquidar skins a los Buy Limits.",
            "total_items": 0,
            "total_liquidation_usd": 0.0,
            "items": []
        }

    data = await steam_client.fetch_user_inventory(conn.account_id)
    data["is_connected"] = True
    data["account_name"] = conn.account_name
    return data


# ==========================================
# FAVORITE SKINS (Watchlist)
# ==========================================

@router.get("/favorites", response_model=List[FavoriteItemResponse])
def get_favorites(db: Session = Depends(get_db)):
    """Returns all favorite skins enriched with live market/opportunity data."""
    favs = db.query(FavoriteSkin).order_by(FavoriteSkin.created_at.desc()).all()
    results = []

    for f in favs:
        # Check if there is an opportunity or skin in DB
        skin = db.query(Skin).filter(Skin.market_hash_name == f.market_hash_name).first()
        opp = skin.opportunity if skin else None

        results.append(FavoriteItemResponse(
            id=f.id,
            market_hash_name=f.market_hash_name,
            weapon=f.weapon or (skin.weapon if skin else None),
            skin_name=f.skin_name or (skin.skin_name if skin else None),
            exterior=f.exterior or (skin.exterior if skin else None),
            icon_url=f.icon_url or (skin.icon_url if skin else None),
            notes=f.notes,
            created_at=f.created_at,
            latest_csfloat_price_usd=round(opp.csfloat_price_cents / 100.0, 2) if opp else None,
            latest_steam_bid_usd=round(opp.steam_highest_bid_cents / 100.0, 2) if opp else None,
            latest_gross_roi_percent=opp.gross_roi_percent if opp else None,
            latest_net_roi_percent=opp.net_roi_percent if opp else None,
            liquidity_score=opp.liquidity_score if opp else None,
            status=opp.status if opp else "UNTRACKED"
        ))

    return results

@router.post("/favorites", response_model=FavoriteItemResponse)
def add_favorite(req: FavoriteCreateRequest, db: Session = Depends(get_db)):
    """Adds a skin to favorites."""
    name = req.market_hash_name.strip()
    existing = db.query(FavoriteSkin).filter(FavoriteSkin.market_hash_name == name).first()
    if existing:
        return FavoriteItemResponse(
            id=existing.id,
            market_hash_name=existing.market_hash_name,
            weapon=existing.weapon,
            skin_name=existing.skin_name,
            exterior=existing.exterior,
            icon_url=existing.icon_url,
            notes=existing.notes,
            created_at=existing.created_at
        )

    skin = db.query(Skin).filter(Skin.market_hash_name == name).first()
    new_fav = FavoriteSkin(
        market_hash_name=name,
        weapon=skin.weapon if skin else None,
        skin_name=skin.skin_name if skin else None,
        exterior=skin.exterior if skin else None,
        icon_url=skin.icon_url if skin else None,
        notes=req.notes,
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_fav)
    db.commit()
    db.refresh(new_fav)

    opp = skin.opportunity if skin else None
    return FavoriteItemResponse(
        id=new_fav.id,
        market_hash_name=new_fav.market_hash_name,
        weapon=new_fav.weapon,
        skin_name=new_fav.skin_name,
        exterior=new_fav.exterior,
        icon_url=new_fav.icon_url,
        notes=new_fav.notes,
        created_at=new_fav.created_at,
        latest_csfloat_price_usd=round(opp.csfloat_price_cents / 100.0, 2) if opp else None,
        latest_steam_bid_usd=round(opp.steam_highest_bid_cents / 100.0, 2) if opp else None,
        latest_gross_roi_percent=opp.gross_roi_percent if opp else None,
        latest_net_roi_percent=opp.net_roi_percent if opp else None,
        liquidity_score=opp.liquidity_score if opp else None,
        status=opp.status if opp else "UNTRACKED"
    )

@router.delete("/favorites/{fav_id}")
def remove_favorite(fav_id: int, db: Session = Depends(get_db)):
    """Removes a skin from favorites by ID."""
    fav = db.query(FavoriteSkin).filter(FavoriteSkin.id == fav_id).first()
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")
    db.delete(fav)
    db.commit()
    return {"success": True, "message": "Removed from favorites"}

@router.delete("/favorites/by-name/{encoded_name}")
def remove_favorite_by_name(encoded_name: str, db: Session = Depends(get_db)):
    """Removes a skin from favorites by market hash name."""
    name = urllib.parse.unquote(encoded_name)
    fav = db.query(FavoriteSkin).filter(FavoriteSkin.market_hash_name == name).first()
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")
    db.delete(fav)
    db.commit()
    return {"success": True, "message": f"Removed '{name}' from favorites"}


# ==========================================
# TRADES / PnL TRACKER HISTORY
# ==========================================

@router.get("/trades", response_model=TradeSummaryResponse)
def get_trades(db: Session = Depends(get_db)):
    """Returns all recorded trades and summary PnL statistics."""
    records = db.query(TradeRecord).order_by(TradeRecord.created_at.desc()).all()

    total_invested = 0.0
    total_realized_profit = 0.0
    total_expected_profit = 0.0
    active_count = 0
    completed_count = 0
    total_roi_sum = 0.0

    trade_items = []
    for t in records:
        total_invested += t.buy_price_usd
        if t.status == "COMPLETED":
            completed_count += 1
            total_realized_profit += t.net_profit_usd
            total_roi_sum += t.net_roi_percent
        elif t.status != "CANCELLED":
            active_count += 1
            total_expected_profit += t.net_profit_usd
            total_roi_sum += t.net_roi_percent

        trade_items.append(TradeRecordResponse.model_validate(t))

    valid_trades_count = completed_count + active_count
    avg_roi = round(total_roi_sum / valid_trades_count, 2) if valid_trades_count > 0 else 0.0

    return TradeSummaryResponse(
        total_trades=len(records),
        active_trades=active_count,
        completed_trades=completed_count,
        total_invested_usd=round(total_invested, 2),
        total_realized_profit_usd=round(total_realized_profit, 2),
        total_expected_profit_usd=round(total_expected_profit, 2),
        average_roi_percent=avg_roi,
        trades=trade_items
    )

@router.post("/trades", response_model=TradeRecordResponse)
def create_trade(req: TradeCreateRequest, db: Session = Depends(get_db)):
    """Records a new trade execution / purchase."""
    # Calculate Steam net payout and profit
    steam_bid_cents = int(req.target_sell_price_usd * 100)
    seller_receives_cents = arbitrage_engine.calculate_steam_seller_receives(steam_bid_cents)
    net_payout_usd = round(seller_receives_cents / 100.0, 2)
    net_profit_usd = round(net_payout_usd - req.buy_price_usd, 2)
    net_roi_percent = round((net_profit_usd / req.buy_price_usd) * 100.0, 2) if req.buy_price_usd > 0 else 0.0

    from datetime import timedelta
    trade_lock_until = datetime.now(timezone.utc) + timedelta(days=8)

    trade = TradeRecord(
        market_hash_name=req.market_hash_name,
        buy_price_usd=req.buy_price_usd,
        buy_source=req.buy_source or "CSFloat",
        target_sell_price_usd=req.target_sell_price_usd,
        sell_source=req.sell_source or "Steam",
        net_profit_usd=net_profit_usd,
        net_roi_percent=net_roi_percent,
        status=req.status or "IN_TRADE_LOCK",
        trade_lock_until=trade_lock_until,
        notes=req.notes,
        created_at=datetime.now(timezone.utc)
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return TradeRecordResponse.model_validate(trade)

@router.patch("/trades/{trade_id}", response_model=TradeRecordResponse)
def update_trade(trade_id: int, req: TradeUpdateRequest, db: Session = Depends(get_db)):
    """Updates status or sale details of an existing trade."""
    trade = db.query(TradeRecord).filter(TradeRecord.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade record not found")

    if req.status is not None:
        trade.status = req.status
        if req.status == "COMPLETED":
            trade.completed_at = datetime.now(timezone.utc)
    if req.actual_sell_price_usd is not None:
        trade.actual_sell_price_usd = req.actual_sell_price_usd
        # Recalculate realized profit based on actual sell price
        sell_cents = int(req.actual_sell_price_usd * 100)
        net_payout_cents = arbitrage_engine.calculate_steam_seller_receives(sell_cents)
        trade.net_profit_usd = round((net_payout_cents / 100.0) - trade.buy_price_usd, 2)
        trade.net_roi_percent = round((trade.net_profit_usd / trade.buy_price_usd) * 100.0, 2)
    if req.notes is not None:
        trade.notes = req.notes

    db.commit()
    db.refresh(trade)
    return TradeRecordResponse.model_validate(trade)

@router.delete("/trades/{trade_id}")
def delete_trade(trade_id: int, db: Session = Depends(get_db)):
    """Deletes a trade record."""
    trade = db.query(TradeRecord).filter(TradeRecord.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade record not found")
    db.delete(trade)
    db.commit()
    return {"success": True, "message": "Trade record deleted"}


# ==========================================
# CASHOUT / REVERSE CYCLE (STEAM -> CSFLOAT)
# ==========================================

@router.get("/cashout-opportunities", response_model=List[CashoutOpportunityResponse])
def get_cashout_opportunities(
    min_ratio: Optional[float] = Query(None, description="Minimum cashout retention % (e.g. 70.0)"),
    max_price: Optional[float] = Query(None, description="Maximum Steam Buy Price in USD"),
    max_loss: Optional[float] = Query(None, description="Maximum cashout discount/loss %"),
    sort_by: Optional[str] = Query("ratio_desc", description="Sort criteria: ratio_desc, diff_asc, price_asc, profit_desc"),
    db: Session = Depends(get_db)
):
    """
    Reverse Scanner (Steam -> CSFloat):
    Finds skins with the lowest price difference / highest retention rate when buying on
    Steam Community Market and selling on CSFloat to cash out Steam Wallet with minimal loss.
    """
    now = datetime.now(timezone.utc)
    skins = db.query(Skin).options(
        joinedload(Skin.steam_order_books),
        joinedload(Skin.csfloat_listings)
    ).all()

    results = []
    for skin in skins:
        st_book = skin.steam_order_books[0] if skin.steam_order_books else None
        cs_listing = skin.csfloat_listings[0] if skin.csfloat_listings else None

        if not st_book or not st_book.lowest_sell_order_cents or st_book.lowest_sell_order_cents <= 0:
            continue
        if not cs_listing or not cs_listing.price_cents or cs_listing.price_cents <= 0:
            continue

        steam_ask_cents = st_book.lowest_sell_order_cents
        csfloat_cents = cs_listing.price_cents

        steam_ask_usd = round(steam_ask_cents / 100.0, 2)
        csfloat_usd = round(csfloat_cents / 100.0, 2)

        # CSFloat 2% fee
        csfloat_net_cents = int(csfloat_cents * 0.98)
        csfloat_net_usd = round(csfloat_net_cents / 100.0, 2)

        # Retention ratio % (How much real cash you retain per dollar of Steam Wallet)
        retention_ratio = round((csfloat_net_usd / steam_ask_usd) * 100.0, 2) if steam_ask_usd > 0 else 0.0
        loss_percent = round(100.0 - retention_ratio, 2)
        price_diff_usd = round(steam_ask_usd - csfloat_usd, 2)
        net_profit_usd = round(csfloat_net_usd - steam_ask_usd, 2)

        # Apply filters
        if min_ratio is not None and retention_ratio < min_ratio:
            continue
        if max_price is not None and steam_ask_usd > max_price:
            continue
        if max_loss is not None and loss_percent > max_loss:
            continue

        data_age = int((now - (st_book.updated_at.replace(tzinfo=timezone.utc) if st_book.updated_at.tzinfo is None else st_book.updated_at)).total_seconds())

        encoded_name = urllib.parse.quote(skin.market_hash_name)
        steam_url = f"https://steamcommunity.com/market/listings/730/{encoded_name}"
        csfloat_url = f"https://csfloat.com/item/{cs_listing.listing_id}" if cs_listing.listing_id else f"https://csfloat.com/search?market_hash_name={encoded_name}"

        results.append(CashoutOpportunityResponse(
            id=skin.id,
            skin=SkinResponse.model_validate(skin),
            steam_lowest_ask_usd=steam_ask_usd,
            steam_lowest_ask_cents=steam_ask_cents,
            csfloat_price_usd=csfloat_usd,
            csfloat_price_cents=csfloat_cents,
            csfloat_net_payout_usd=csfloat_net_usd,
            price_diff_usd=price_diff_usd,
            cashout_ratio_percent=retention_ratio,
            loss_percent=loss_percent,
            net_profit_usd=net_profit_usd,
            steam_url=steam_url,
            csfloat_url=csfloat_url,
            data_age_seconds=data_age,
            updated_at=st_book.updated_at
        ))

    # Apply sorting
    if sort_by == "ratio_desc":
        results.sort(key=lambda x: x.cashout_ratio_percent, reverse=True)
    elif sort_by == "diff_asc":
        results.sort(key=lambda x: x.price_diff_usd)
    elif sort_by == "price_asc":
        results.sort(key=lambda x: x.steam_lowest_ask_usd)
    elif sort_by == "profit_desc":
        results.sort(key=lambda x: x.net_profit_usd, reverse=True)
    else:
        results.sort(key=lambda x: x.cashout_ratio_percent, reverse=True)

    return results
