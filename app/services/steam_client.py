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

    async def resolve_steam_id(self, identifier: str) -> Optional[str]:
        """Resolves custom URLs, profile links, or raw Steam64 IDs to a clean 17-digit Steam64 ID."""
        cleaned = identifier.strip().rstrip("/")
        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            parts = cleaned.split("/")
            if "profiles" in parts:
                idx = parts.index("profiles")
                if idx + 1 < len(parts):
                    return parts[idx + 1]
            elif "id" in parts:
                idx = parts.index("id")
                if idx + 1 < len(parts):
                    cleaned = parts[idx + 1]

        # If it's already a numeric Steam64 ID (17 digits)
        if cleaned.isdigit() and len(cleaned) == 17:
            return cleaned

        # Otherwise try vanity URL resolution
        url = "https://steamcommunity.com/id/" + urllib.parse.quote(cleaned) + "/?xml=1"
        try:
            resp = await http_client.get(url)
            if resp.status_code == 200 and "<steamID64>" in resp.text:
                import re
                match = re.search(r"<steamID64>(\d+)<\/steamID64>", resp.text)
                if match:
                    return match.group(1)
        except Exception as e:
            logger.warning(f"Failed to resolve Steam vanity URL '{identifier}': {e}")

        return cleaned if cleaned.isdigit() else None

    async def fetch_user_inventory(self, steam_id64: str) -> Dict[str, Any]:
        """
        Fetches user's CS2 Steam Inventory (AppID 730, ContextID 2)
        and cross-references each skin with the highest active Steam Buy Limit.
        """
        url = f"https://steamcommunity.com/inventory/{steam_id64}/730/2"
        params = {
            "l": "english",
            "count": 2000
        }
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": f"https://steamcommunity.com/profiles/{steam_id64}/inventory/"
        }

        try:
            resp = await http_client.get(url, params=params, headers=headers)
            if resp.status_code in (401, 403):
                return {
                    "success": False,
                    "steam_id64": steam_id64,
                    "total_items": 0,
                    "marketable_items": 0,
                    "total_liquidation_usd": 0.0,
                    "error": "El inventario de Steam es Privado o no se encuentra. Por favor cámbialo a Público en la configuración de privacidad de Steam.",
                    "items": []
                }
            if resp.status_code == 429:
                return {
                    "success": False,
                    "steam_id64": steam_id64,
                    "total_items": 0,
                    "marketable_items": 0,
                    "total_liquidation_usd": 0.0,
                    "error": "Steam Community rate limit (429). Por favor espera un momento.",
                    "items": []
                }
            
            resp.raise_for_status()
            data = resp.json()

            if not data or not data.get("assets"):
                return {
                    "success": True,
                    "steam_id64": steam_id64,
                    "total_items": 0,
                    "marketable_items": 0,
                    "total_liquidation_usd": 0.0,
                    "items": []
                }

            assets = data.get("assets", [])
            descriptions = data.get("descriptions", [])

            # Map description by classid_instanceid
            desc_map = {}
            for d in descriptions:
                key = f"{d.get('classid')}_{d.get('instanceid', '0')}"
                desc_map[key] = d

            parsed_inventory = []
            distinct_names = set()

            for a in assets:
                classid = a.get("classid")
                instanceid = a.get("instanceid", "0")
                key = f"{classid}_{instanceid}"
                desc = desc_map.get(key, {})

                market_hash_name = desc.get("market_hash_name")
                if not market_hash_name:
                    continue

                icon_url = desc.get("icon_url")
                full_icon = f"https://community.cloudflare.steamstatic.com/economy/image/{icon_url}/330x192" if icon_url else None
                marketable = bool(desc.get("marketable", 0) == 1)
                tradable = bool(desc.get("tradable", 0) == 1)

                # Extract inspect link if present
                inspect_link = None
                actions = desc.get("actions", [])
                if actions and len(actions) > 0:
                    inspect_link = actions[0].get("link")

                distinct_names.add(market_hash_name)
                parsed_inventory.append({
                    "asset_id": str(a.get("assetid")),
                    "class_id": str(classid),
                    "instance_id": str(instanceid),
                    "market_hash_name": market_hash_name,
                    "icon_url": full_icon,
                    "marketable": marketable,
                    "tradable": tradable,
                    "inspect_link": inspect_link,
                    "type": desc.get("type", "CS2 Item"),
                    "name_color": desc.get("name_color", "D2D2D2")
                })

            # Fetch live buy orders for distinct inventory skins (with concurrency limit)
            order_book_cache = {}
            for name in list(distinct_names)[:30]:  # batch check top 30 distinct skins
                try:
                    ob = await self.fetch_order_book(name, use_cache=True)
                    if ob.get("success") and ob.get("highest_buy_order_cents"):
                        highest_bid = ob["highest_buy_order_cents"]
                        net_payout = arbitrage_engine.calculate_steam_seller_receives(highest_bid)
                        order_book_cache[name] = {
                            "highest_buy_order_cents": highest_bid,
                            "highest_buy_order_usd": round(highest_bid / 100.0, 2),
                            "net_payout_cents": net_payout,
                            "net_payout_usd": round(net_payout / 100.0, 2),
                            "lowest_sell_order_usd": ob.get("lowest_sell_order_usd"),
                            "total_buy_orders": ob.get("total_buy_orders", 0)
                        }
                    else:
                        order_book_cache[name] = None
                except Exception:
                    order_book_cache[name] = None

            # Enrich items with buy limits
            total_liquidation_usd = 0.0
            enriched_items = []

            for item in parsed_inventory:
                name = item["market_hash_name"]
                ob_data = order_book_cache.get(name)

                highest_bid_usd = ob_data["highest_buy_order_usd"] if ob_data else None
                net_payout_usd = ob_data["net_payout_usd"] if ob_data else None
                total_bids = ob_data["total_buy_orders"] if ob_data else 0

                if net_payout_usd and item["marketable"]:
                    total_liquidation_usd += net_payout_usd

                encoded_name = urllib.parse.quote(name)
                steam_market_url = f"https://steamcommunity.com/market/listings/730/{encoded_name}"

                enriched_items.append({
                    **item,
                    "highest_buy_order_usd": highest_bid_usd,
                    "net_payout_usd": net_payout_usd,
                    "total_buy_orders": total_bids,
                    "has_active_buy_limit": bool(highest_bid_usd and highest_bid_usd > 0),
                    "steam_market_url": steam_market_url
                })

            return {
                "success": True,
                "steam_id64": steam_id64,
                "total_items": len(enriched_items),
                "marketable_items": len([i for i in enriched_items if i["marketable"]]),
                "total_liquidation_usd": round(total_liquidation_usd, 2),
                "items": enriched_items
            }

        except Exception as e:
            logger.error(f"Error fetching Steam inventory for {steam_id64}: {e}")
            return {
                "success": False,
                "steam_id64": steam_id64,
                "total_items": 0,
                "marketable_items": 0,
                "total_liquidation_usd": 0.0,
                "error": f"Error al cargar el inventario: {str(e)}",
                "items": []
            }

steam_client = SteamClient()
