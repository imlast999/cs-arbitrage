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


# Connections Schemas
class CSFloatConnectRequest(BaseModel):
    api_key: str = Field(min_length=5, description="CSFloat Developer API Key")

class SteamConnectRequest(BaseModel):
    account_name: Optional[str] = Field(None, description="Steam Persona / Custom Name")
    steam_id: Optional[str] = Field(None, description="Steam64 ID or Profile ID")
    trade_url: Optional[str] = Field(None, description="Steam Trade URL for receiving trades")
    api_key: Optional[str] = Field(None, description="Steam Web API Key (Optional)")
    session_id: Optional[str] = Field(None, description="Steam sessionid cookie (for 1-click automated market sell)")
    steam_login_secure: Optional[str] = Field(None, description="Steam steamLoginSecure cookie (for 1-click automated market sell)")

class SteamSellItemRequest(BaseModel):
    asset_id: str
    price_cents: int

class ConnectionStatusItem(BaseModel):
    provider: str
    is_connected: bool
    account_name: Optional[str] = None
    account_id: Optional[str] = None
    trade_url: Optional[str] = None
    balance_usd: Optional[float] = None
    avatar_url: Optional[str] = None
    has_market_session: bool = False
    updated_at: Optional[datetime] = None

class ConnectionsResponse(BaseModel):
    csfloat: ConnectionStatusItem
    steam: ConnectionStatusItem


# Favorites Schemas
class FavoriteCreateRequest(BaseModel):
    market_hash_name: str = Field(min_length=2)
    notes: Optional[str] = None

class FavoriteItemResponse(BaseModel):
    id: int
    market_hash_name: str
    weapon: Optional[str] = None
    skin_name: Optional[str] = None
    exterior: Optional[str] = None
    icon_url: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    # Enriched live data if available
    latest_csfloat_price_usd: Optional[float] = None
    latest_steam_bid_usd: Optional[float] = None
    latest_gross_roi_percent: Optional[float] = None
    latest_net_roi_percent: Optional[float] = None
    liquidity_score: Optional[str] = None
    status: Optional[str] = None

    class Config:
        from_attributes = True


# Trade Tracker / History Schemas
class TradeCreateRequest(BaseModel):
    market_hash_name: str
    buy_price_usd: float = Field(gt=0)
    target_sell_price_usd: float = Field(gt=0)
    buy_source: Optional[str] = "CSFloat"
    sell_source: Optional[str] = "Steam"
    status: Optional[str] = "IN_TRADE_LOCK"  # IN_TRADE_LOCK, IN_INVENTORY, LISTED, COMPLETED, CANCELLED
    notes: Optional[str] = None

class TradeUpdateRequest(BaseModel):
    status: Optional[str] = None
    actual_sell_price_usd: Optional[float] = None
    notes: Optional[str] = None

class TradeRecordResponse(BaseModel):
    id: int
    market_hash_name: str
    buy_price_usd: float
    buy_source: str
    target_sell_price_usd: float
    actual_sell_price_usd: Optional[float] = None
    sell_source: str
    net_profit_usd: float
    net_roi_percent: float
    status: str
    trade_lock_until: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TradeSummaryResponse(BaseModel):
    total_trades: int
    active_trades: int
    completed_trades: int
    total_invested_usd: float
    total_realized_profit_usd: float
    total_expected_profit_usd: float
    average_roi_percent: float
    trades: List[TradeRecordResponse]


# Reverse / Cashout Opportunities Schemas (Steam -> CSFloat)
class CashoutOpportunityResponse(BaseModel):
    id: int
    skin: SkinResponse
    steam_lowest_ask_usd: float
    steam_lowest_ask_cents: int
    csfloat_price_usd: float
    csfloat_price_cents: int
    csfloat_net_payout_usd: float  # After CSFloat 2% fee
    price_diff_usd: float          # Steam Ask - CSFloat Ask
    cashout_ratio_percent: float   # Retention % (CSFloat Net / Steam Ask * 100)
    loss_percent: float            # Discount % (100 - Cashout Ratio)
    net_profit_usd: float          # csfloat_net - steam_cost
    steam_url: str
    csfloat_url: str
    data_age_seconds: int
    updated_at: datetime

    class Config:
        from_attributes = True
