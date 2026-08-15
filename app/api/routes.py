import json
import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from app.config import settings
from app.database import get_db
from app.models.schema import Skin, CSFloatListing, SteamOrderBook, Opportunity, OpportunityHistory
from app.schemas.api_models import (
    OpportunityResponse,
    OpportunityDetailResponse,
    SkinResponse,
    CSFloatListingResponse,
    SteamOrderBookResponse,
    OrderBookTier,
    SystemStatusResponse,
    ExecutionSimulationRequest,
    ExecutionSimulationResponse
)
from app.services.scanner_service import scanner_service
from app.services.arbitrage_engine import arbitrage_engine
from app.services.csfloat_client import csfloat_client

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
