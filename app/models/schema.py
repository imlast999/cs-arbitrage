from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

def utc_now():
    return datetime.now(timezone.utc)

class Skin(Base):
    __tablename__ = "skins"

    id = Column(Integer, primary_key=True, index=True)
    market_hash_name = Column(String, unique=True, index=True, nullable=False)
    weapon = Column(String, nullable=True)
    skin_name = Column(String, nullable=True)
    exterior = Column(String, nullable=True)
    is_stattrak = Column(Boolean, default=False, nullable=False)
    is_souvenir = Column(Boolean, default=False, nullable=False)
    icon_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    csfloat_listings = relationship("CSFloatListing", back_populates="skin", cascade="all, delete-orphan")
    steam_order_books = relationship("SteamOrderBook", back_populates="skin", cascade="all, delete-orphan")
    opportunity = relationship("Opportunity", back_populates="skin", uselist=False, cascade="all, delete-orphan")
    history_records = relationship("OpportunityHistory", back_populates="skin", cascade="all, delete-orphan")


class CSFloatListing(Base):
    __tablename__ = "csfloat_listings"

    id = Column(Integer, primary_key=True, index=True)
    skin_id = Column(Integer, ForeignKey("skins.id"), nullable=False, index=True)
    listing_id = Column(String, unique=True, index=True, nullable=False)
    price_cents = Column(Integer, nullable=False)
    float_value = Column(Float, nullable=True)
    inspect_link = Column(String, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    skin = relationship("Skin", back_populates="csfloat_listings")


class SteamOrderBook(Base):
    __tablename__ = "steam_order_books"

    id = Column(Integer, primary_key=True, index=True)
    skin_id = Column(Integer, ForeignKey("skins.id"), nullable=False, index=True)
    highest_buy_order_cents = Column(Integer, nullable=True)
    lowest_sell_order_cents = Column(Integer, nullable=True)
    total_buy_orders = Column(Integer, default=0)
    order_book_json = Column(Text, nullable=True)  # JSON-encoded array of [price_cents, qty]
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    skin = relationship("Skin", back_populates="steam_order_books")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(Integer, primary_key=True, index=True)
    skin_id = Column(Integer, ForeignKey("skins.id"), nullable=False, unique=True, index=True)
    csfloat_price_cents = Column(Integer, nullable=False)
    steam_highest_bid_cents = Column(Integer, nullable=False)
    gross_profit_usd = Column(Float, nullable=False)
    net_profit_usd = Column(Float, nullable=False)
    gross_roi_percent = Column(Float, nullable=False)
    net_roi_percent = Column(Float, nullable=False)
    available_quantity = Column(Integer, default=1)
    liquidity_score = Column(String, default="LOW")  # HIGH, MEDIUM, LOW
    status = Column(String, default="ACTIVE")  # ACTIVE, STALE, UNVERIFIED
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    skin = relationship("Skin", back_populates="opportunity")


class OpportunityHistory(Base):
    __tablename__ = "opportunity_history"

    id = Column(Integer, primary_key=True, index=True)
    skin_id = Column(Integer, ForeignKey("skins.id"), nullable=False, index=True)
    csfloat_price_cents = Column(Integer, nullable=False)
    steam_highest_bid_cents = Column(Integer, nullable=False)
    gross_profit_usd = Column(Float, nullable=False)
    net_profit_usd = Column(Float, nullable=False)
    gross_roi_percent = Column(Float, nullable=False)
    net_roi_percent = Column(Float, nullable=False)
    liquidity_score = Column(String, default="LOW")
    snapshot_at = Column(DateTime, default=utc_now, index=True)

    skin = relationship("Skin", back_populates="history_records")


class UserConnection(Base):
    __tablename__ = "user_connections"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, unique=True, index=True, nullable=False)  # "csfloat" or "steam"
    is_connected = Column(Boolean, default=False, nullable=False)
    account_name = Column(String, nullable=True)
    account_id = Column(String, nullable=True)
    api_key = Column(String, nullable=True)
    trade_url = Column(String, nullable=True)
    balance_usd = Column(Float, default=0.0)
    meta_json = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class FavoriteSkin(Base):
    __tablename__ = "favorite_skins"

    id = Column(Integer, primary_key=True, index=True)
    market_hash_name = Column(String, unique=True, index=True, nullable=False)
    weapon = Column(String, nullable=True)
    skin_name = Column(String, nullable=True)
    exterior = Column(String, nullable=True)
    icon_url = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=utc_now)


class TradeRecord(Base):
    __tablename__ = "trade_records"

    id = Column(Integer, primary_key=True, index=True)
    market_hash_name = Column(String, nullable=False, index=True)
    buy_price_usd = Column(Float, nullable=False)
    buy_source = Column(String, default="CSFloat")
    target_sell_price_usd = Column(Float, nullable=False)
    actual_sell_price_usd = Column(Float, nullable=True)
    sell_source = Column(String, default="Steam")
    net_profit_usd = Column(Float, nullable=False)
    net_roi_percent = Column(Float, nullable=False)
    status = Column(String, default="IN_TRADE_LOCK")  # IN_TRADE_LOCK, IN_INVENTORY, LISTED, COMPLETED, CANCELLED
    trade_lock_until = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    completed_at = Column(DateTime, nullable=True)
