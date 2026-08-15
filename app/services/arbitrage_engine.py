from datetime import datetime, timezone
import math
from typing import List, Tuple, Dict, Any, Optional

class ArbitrageEngine:
    """
    Pure computation engine for arbitrage metrics, Steam fee deduction,
    real multi-tier order book depth execution simulation, and liquidity scoring.
    """

    @staticmethod
    def calculate_steam_seller_receives(buyer_price_cents: int) -> int:
        """
        Calculates the net amount in cents that the seller receives after Steam's
        5% Steam transaction fee and 10% CS2 game fee.
        Formula adheres to Valve's market fee distribution algorithm.
        """
        if buyer_price_cents <= 0:
            return 0
        if buyer_price_cents <= 2:
            return 1 # Minimum payout

        # Base estimate
        seller_receives = int(buyer_price_cents / 1.15)
        # Refine to match Steam's exact fee integer arithmetic
        steam_fee = max(1, int(seller_receives * 0.05))
        game_fee = max(1, int(seller_receives * 0.10))
        
        while (seller_receives + steam_fee + game_fee) > buyer_price_cents and seller_receives > 1:
            seller_receives -= 1
            steam_fee = max(1, int(seller_receives * 0.05))
            game_fee = max(1, int(seller_receives * 0.10))

        return seller_receives

    @staticmethod
    def calculate_gross_profit(highest_steam_bid_cents: int, lowest_csfloat_price_cents: int) -> float:
        """Gross Profit in USD = (Steam Highest Bid - CSFloat Lowest Ask) / 100"""
        return round((highest_steam_bid_cents - lowest_csfloat_price_cents) / 100.0, 2)

    @staticmethod
    def calculate_gross_roi(highest_steam_bid_cents: int, lowest_csfloat_price_cents: int) -> float:
        """Gross ROI % = (Gross Profit / CSFloat Price) * 100"""
        if lowest_csfloat_price_cents <= 0:
            return 0.0
        profit = highest_steam_bid_cents - lowest_csfloat_price_cents
        return round((profit / lowest_csfloat_price_cents) * 100.0, 4)

    @staticmethod
    def calculate_net_profit(highest_steam_bid_cents: int, lowest_csfloat_price_cents: int) -> float:
        """Net Profit in USD = (Steam Seller Receives - CSFloat Lowest Ask) / 100"""
        seller_receives = ArbitrageEngine.calculate_steam_seller_receives(highest_steam_bid_cents)
        return round((seller_receives - lowest_csfloat_price_cents) / 100.0, 2)

    @staticmethod
    def calculate_net_roi(highest_steam_bid_cents: int, lowest_csfloat_price_cents: int) -> float:
        """Net ROI % = (Net Profit / CSFloat Price) * 100"""
        if lowest_csfloat_price_cents <= 0:
            return 0.0
        seller_receives = ArbitrageEngine.calculate_steam_seller_receives(highest_steam_bid_cents)
        net_profit_cents = seller_receives - lowest_csfloat_price_cents
        return round((net_profit_cents / lowest_csfloat_price_cents) * 100.0, 4)

    @staticmethod
    def calculate_execution_value(
        target_quantity: int,
        order_book_tiers: List[Tuple[int, int]],
        csfloat_price_cents: int
    ) -> Dict[str, Any]:
        """
        Simulates selling 'target_quantity' skins into the real Steam Order Book tiers.
        order_book_tiers: List of (price_cents, quantity) sorted descending by price.
        """
        if target_quantity <= 0 or not order_book_tiers:
            return {
                "target_quantity": target_quantity,
                "fulfilled_quantity": 0,
                "is_fully_fulfilled": False,
                "total_cost_csfloat_usd": 0.0,
                "gross_execution_value_usd": 0.0,
                "net_execution_value_usd": 0.0,
                "total_gross_profit_usd": 0.0,
                "total_net_profit_usd": 0.0,
                "effective_gross_roi_percent": 0.0,
                "effective_net_roi_percent": 0.0,
                "filled_tiers": []
            }

        remaining_needed = target_quantity
        gross_proceeds_cents = 0
        net_proceeds_cents = 0
        filled_tiers = []

        for tier_price_cents, tier_qty in order_book_tiers:
            if remaining_needed <= 0:
                break
            fill_qty = min(remaining_needed, tier_qty)
            tier_seller_receives = ArbitrageEngine.calculate_steam_seller_receives(tier_price_cents)

            gross_proceeds_cents += fill_qty * tier_price_cents
            net_proceeds_cents += fill_qty * tier_seller_receives
            remaining_needed -= fill_qty

            filled_tiers.append({
                "price_usd": round(tier_price_cents / 100.0, 2),
                "quantity_filled": fill_qty,
                "net_payout_per_unit_usd": round(tier_seller_receives / 100.0, 2),
                "total_net_payout_usd": round((fill_qty * tier_seller_receives) / 100.0, 2)
            })

        fulfilled_qty = target_quantity - remaining_needed
        total_cost_cents = fulfilled_qty * csfloat_price_cents
        gross_profit_cents = gross_proceeds_cents - total_cost_cents
        net_profit_cents = net_proceeds_cents - total_cost_cents

        gross_roi = (gross_profit_cents / total_cost_cents * 100.0) if total_cost_cents > 0 else 0.0
        net_roi = (net_profit_cents / total_cost_cents * 100.0) if total_cost_cents > 0 else 0.0

        return {
            "target_quantity": target_quantity,
            "fulfilled_quantity": fulfilled_qty,
            "is_fully_fulfilled": (remaining_needed == 0),
            "total_cost_csfloat_usd": round(total_cost_cents / 100.0, 2),
            "gross_execution_value_usd": round(gross_proceeds_cents / 100.0, 2),
            "net_execution_value_usd": round(net_proceeds_cents / 100.0, 2),
            "total_gross_profit_usd": round(gross_profit_cents / 100.0, 2),
            "total_net_profit_usd": round(net_profit_cents / 100.0, 2),
            "effective_gross_roi_percent": round(gross_roi, 2),
            "effective_net_roi_percent": round(net_roi, 2),
            "filled_tiers": filled_tiers
        }

    @staticmethod
    def calculate_liquidity_score(
        highest_bid_cents: int,
        order_book_tiers: List[Tuple[int, int]],
        total_buy_orders: int
    ) -> str:
        """
        Evaluates liquidity based on top tier quantity and depth within 5% of highest bid.
        Returns: 'HIGH', 'MEDIUM', or 'LOW'
        """
        if not order_book_tiers or highest_bid_cents <= 0:
            return "LOW"

        top_tier_qty = order_book_tiers[0][1] if order_book_tiers else 0
        min_5pct_price = highest_bid_cents * 0.95

        qty_within_5pct = 0
        for price, qty in order_book_tiers:
            if price >= min_5pct_price:
                qty_within_5pct += qty
            else:
                break

        if top_tier_qty >= 10 or qty_within_5pct >= 25 or total_buy_orders >= 1000:
            return "HIGH"
        elif top_tier_qty >= 3 or qty_within_5pct >= 8 or total_buy_orders >= 100:
            return "MEDIUM"
        else:
            return "LOW"

    @staticmethod
    def evaluate_status(
        csfloat_timestamp: Optional[datetime],
        steam_timestamp: Optional[datetime],
        max_data_age_seconds: int,
        has_active_listing: bool,
        has_active_bid: bool,
        is_name_matched: bool
    ) -> str:
        """
        Validates opportunity state:
        - UNVERIFIED: Missing listing, missing bid, or name mismatch
        - STALE: Timestamp older than max_data_age_seconds
        - ACTIVE: Verified, fresh, and active
        """
        if not has_active_listing or not has_active_bid or not is_name_matched:
            return "UNVERIFIED"

        now = datetime.now(timezone.utc)
        if csfloat_timestamp:
            csfloat_utc = csfloat_timestamp if csfloat_timestamp.tzinfo else csfloat_timestamp.replace(tzinfo=timezone.utc)
            if (now - csfloat_utc).total_seconds() > max_data_age_seconds:
                return "STALE"

        if steam_timestamp:
            steam_utc = steam_timestamp if steam_timestamp.tzinfo else steam_timestamp.replace(tzinfo=timezone.utc)
            if (now - steam_utc).total_seconds() > max_data_age_seconds:
                return "STALE"

        return "ACTIVE"

arbitrage_engine = ArbitrageEngine()
