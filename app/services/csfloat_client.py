import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import httpx
from app.config import settings
from app.services.http_client import http_client

logger = logging.getLogger("scanner.csfloat")

class CSFloatClient:
    """Client for interacting with CSFloat API."""

    def __init__(self):
        self.base_url = settings.CSFLOAT_BASE_URL.rstrip("/")
        self.api_key = settings.CSFLOAT_API_KEY

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Origin": "https://csfloat.com",
            "Referer": "https://csfloat.com/",
        }
        if self.api_key:
            headers["Authorization"] = self.api_key
        return headers

    def has_api_key(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def fetch_listings(
        self,
        limit: int = 50,
        sort_by: str = "lowest_price",
        min_price_cents: Optional[int] = None,
        max_price_cents: Optional[int] = None,
        market_hash_name: Optional[str] = None,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetches active listings from CSFloat.
        Returns a dict: {"success": bool, "data": list, "cursor": str, "auth_required": bool, "error": str}
        """
        if not self.has_api_key():
            logger.warning("CSFloat API key not configured in .env. CSFloat queries require an API key.")
            return {
                "success": False,
                "data": [],
                "cursor": None,
                "auth_required": True,
                "error": "CSFLOAT_API_KEY is not configured in .env. Please generate a key at https://csfloat.com (Developer tab)."
            }

        url = f"{self.base_url}/listings"
        params: Dict[str, Any] = {
            "type": "buy_now",
            "sort_by": sort_by,
            "limit": min(limit, 50)
        }
        if min_price_cents is not None:
            params["min_price"] = min_price_cents
        if max_price_cents is not None:
            params["max_price"] = max_price_cents
        if market_hash_name:
            params["market_hash_name"] = market_hash_name
        if cursor:
            params["cursor"] = cursor

        try:
            response = await http_client.get(url, params=params, headers=self._get_headers())
            if response.status_code == 403:
                return {
                    "success": False,
                    "data": [],
                    "cursor": None,
                    "auth_required": True,
                    "error": "CSFloat rejected authorization. Please verify your CSFLOAT_API_KEY."
                }
            
            response.raise_for_status()
            data = response.json()

            # CSFloat can return a list directly or {"data": [...], "cursor": "..."}
            listings = []
            next_cursor = None

            if isinstance(data, list):
                listings = data
            elif isinstance(data, dict):
                listings = data.get("data", [])
                next_cursor = data.get("cursor")

            parsed_items = []
            for item in listings:
                item_data = item.get("item", {})
                name = item_data.get("market_hash_name") or item.get("market_hash_name")
                price = item.get("price")
                if name and price is not None:
                    parsed_items.append({
                        "listing_id": str(item.get("id")),
                        "market_hash_name": name,
                        "price_cents": int(price),
                        "float_value": item_data.get("float_value"),
                        "wear_name": item_data.get("wear_name"),
                        "is_stattrak": bool(item_data.get("is_stattrak")),
                        "is_souvenir": bool(item_data.get("is_souvenir")),
                        "icon_url": item_data.get("icon_url"),
                        "inspect_link": item_data.get("inspect_link"),
                        "created_at": datetime.now(timezone.utc)
                    })

            return {
                "success": True,
                "data": parsed_items,
                "cursor": next_cursor,
                "auth_required": False,
                "error": None
            }

        except Exception as e:
            logger.error(f"Error fetching CSFloat listings: {e}")
            return {
                "success": False,
                "data": [],
                "cursor": None,
                "auth_required": False,
                "error": str(e)
            }

csfloat_client = CSFloatClient()
