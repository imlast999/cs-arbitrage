from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, Field

class OrderBookTier(BaseModel):
    price_cents: int
    price_usd: float
    quantity: int
    net_payout_usd: float  # After Steam fee per item at this tier

class SkinResponse(BaseModel):
    id: int
    market_hash_name: str
    weapon: Optional[str] = None
    skin_name: Optional[str] = None
    exterior: Optional[str] = None
    is_stattrak: bool = False
    is_souvenir: bool = False
    icon_url: Optional[str] = None

    class Config:
        from_attributes = True

class CSFloatListingResponse(BaseModel):
    id: int
    listing_id: str
    price_cents: int
    price_usd: float
    float_value: Optional[float] = None
    inspect_link: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class SteamOrderBookResponse(BaseModel):
    id: int
    highest_buy_order_cents: Optional[int] = None
    highest_buy_order_usd: Optional[float] = None
    lowest_sell_order_cents: Optional[int] = None
    lowest_sell_order_usd: Optional[float] = None
    total_buy_orders: int = 0
    tiers: List[OrderBookTier] = []
    updated_at: datetime

    class Config:
        from_attributes = True

class OpportunityResponse(BaseModel):
    id: int
    skin: SkinResponse
    csfloat_price_usd: float
    csfloat_price_cents: int
    steam_highest_bid_usd: float
    steam_highest_bid_cents: int
    gross_profit_usd: float
    gross_roi_percent: float
    net_profit_usd: float
    net_roi_percent: float
    available_quantity: int
    liquidity_score: str
    status: str
    data_age_seconds: int
    updated_at: datetime

    class Config:
        from_attributes = True

class OpportunityDetailResponse(OpportunityResponse):
    csfloat_listing: Optional[CSFloatListingResponse] = None
    steam_order_book: Optional[SteamOrderBookResponse] = None
    csfloat_url: str
    steam_url: str
    fee_breakdown: dict

class OpportunityFilterParams(BaseModel):
    min_roi: Optional[float] = None
    max_price: Optional[float] = None
    min_profit: Optional[float] = None
    min_liquidity: Optional[str] = None
    sort_by: Optional[str] = "roi_desc"  # roi_desc, profit_desc, price_asc, liquidity_desc

class ExecutionSimulationRequest(BaseModel):
    quantity: int = Field(gt=0, description="Number of skins to simulate selling into Steam order book")

class ExecutionSimulationResponse(BaseModel):
    target_quantity: int
    fulfilled_quantity: int
    is_fully_fulfilled: bool
    total_cost_csfloat_usd: float
    gross_execution_value_usd: float
    net_execution_value_usd: float  # After Steam fees
    total_gross_profit_usd: float
    total_net_profit_usd: float
    effective_gross_roi_percent: float
    effective_net_roi_percent: float
    filled_tiers: List[dict]

class SystemStatusResponse(BaseModel):
    app_name: str
    version: str
    csfloat_connected: bool
    csfloat_auth_status: str  # "AUTHENTICATED", "NO_API_KEY", "ERROR"
    steam_connected: bool
    steam_status: str        # "CONNECTED", "RATE_LIMITED", "ERROR"
    total_opportunities: int
    active_opportunities: int
    last_scan_timestamp: Optional[datetime] = None
    seconds_since_last_scan: Optional[int] = None
    is_scanning: bool
