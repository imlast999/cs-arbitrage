import json
import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from app.config import settings
from app.services.http_client import http_client
from app.services.arbitrage_engine import arbitrage_engine

logger = logging.getLogger("scanner.steam")

class SteamClient:
    """Client for querying real-time Steam Community Market order books."""

    def __init__(self):
        self.base_url = settings.STEAM_BASE_URL.rstrip("/")
        # In-memory cache: market_hash_name -> (timestamp, data)
        self._cache: Dict[str, Tuple[datetime, Dict[str, Any]]] = {}
        self.cache_ttl_seconds = 60

    async def fetch_order_book(self, market_hash_name: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Fetches the complete, real-time buy order book and pricing for a CS2 skin.
        """
        now = datetime.now(timezone.utc)

        # Check cache
        if use_cache and market_hash_name in self._cache:
            cached_time, cached_data = self._cache[market_hash_name]
            if (now - cached_time).total_seconds() < self.cache_ttl_seconds:
                return cached_data

        url = f"{self.base_url}/orderbook"
        encoded_name = urllib.parse.quote(market_hash_name)
        referer = f"https://steamcommunity.com/market/listings/730/{encoded_name}"

        params = {
            "q": "Load",
            "qp": json.dumps([730, market_hash_name]),
            "cc": "US",
            "l": "english",
            "currency": 1  # USD
        }

        headers = {
            "Accept": "application/json, text/plain, */*",
            "x-valve-request-type": "queryAction",
            "Referer": referer
        }

        try:
            response = await http_client.get(url, params=params, headers=headers)
            if response.status_code == 429:
                return {
                    "success": False,
                    "market_hash_name": market_hash_name,
                    "highest_buy_order_cents": None,
                    "lowest_sell_order_cents": None,
                    "total_buy_orders": 0,
                    "tiers": [],
                    "raw_order_book": [],
                    "updated_at": now,
                    "error": "Steam Community Market rate limit exceeded (HTTP 429)."
                }

            response.raise_for_status()
            res_json = response.json()

            # The response payload is nested under data -> data
            orderbook_data = res_json.get("data", {}).get("data", {})
            if not orderbook_data and "amtMaxBuyOrder" in res_json:
                orderbook_data = res_json

            highest_buy_order = orderbook_data.get("amtMaxBuyOrder")
            lowest_sell_order = orderbook_data.get("amtMinSellOrder")
            total_buy_orders = orderbook_data.get("cBuyOrders", 0) or 0
            rg_compact_buy = orderbook_data.get("rgCompactBuyOrders", []) or []

            # Parse compact order book pairs [price_cents, qty, price_cents, qty, ...]
            parsed_tiers = []
            raw_pairs = []
            for i in range(0, len(rg_compact_buy), 2):
                if i + 1 < len(rg_compact_buy):
                    tier_price = int(rg_compact_buy[i])
                    tier_qty = int(rg_compact_buy[i + 1])
                    net_payout = arbitrage_engine.calculate_steam_seller_receives(tier_price)
                    raw_pairs.append((tier_price, tier_qty))
                    parsed_tiers.append({
                        "price_cents": tier_price,
                        "price_usd": round(tier_price / 100.0, 2),
                        "quantity": tier_qty,
                        "net_payout_usd": round(net_payout / 100.0, 2)
                    })

            result = {
                "success": True,
                "market_hash_name": market_hash_name,
                "highest_buy_order_cents": int(highest_buy_order) if highest_buy_order is not None else None,
                "highest_buy_order_usd": round(int(highest_buy_order) / 100.0, 2) if highest_buy_order is not None else None,
                "lowest_sell_order_cents": int(lowest_sell_order) if lowest_sell_order is not None else None,
                "lowest_sell_order_usd": round(int(lowest_sell_order) / 100.0, 2) if lowest_sell_order is not None else None,
                "total_buy_orders": int(total_buy_orders),
                "tiers": parsed_tiers,
                "raw_order_book": raw_pairs,
                "updated_at": now,
                "error": None
            }

            self._cache[market_hash_name] = (now, result)
            return result

        except Exception as e:
            logger.error(f"Error fetching Steam order book for '{market_hash_name}': {e}")
            return {
                "success": False,
                "market_hash_name": market_hash_name,
                "highest_buy_order_cents": None,
                "lowest_sell_order_cents": None,
                "total_buy_orders": 0,
                "tiers": [],
                "raw_order_book": [],
                "updated_at": now,
                "error": str(e)
            }

steam_client = SteamClient()
