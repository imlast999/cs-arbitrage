import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.config import settings
from app.database import SessionLocal
from app.models.schema import Skin, CSFloatListing, SteamOrderBook, Opportunity, OpportunityHistory
from app.services.matching_service import matching_service
from app.services.csfloat_client import csfloat_client
from app.services.steam_client import steam_client
from app.services.arbitrage_engine import arbitrage_engine
from app.services.catalog_service import POPULAR_BASE_SKINS

logger = logging.getLogger("scanner.service")

class ScannerService:
    """Orchestrates market scans, matching, calculation, and database persistence."""

    def __init__(self):
        self.is_scanning: bool = False
        self.last_scan_timestamp: Optional[datetime] = None
        self.csfloat_status: str = "INITIALIZING"
        self.steam_status: str = "INITIALIZING"
        self._task: Optional[asyncio.Task] = None

    async def start_background_loop(self):
        """Starts the periodic background scanner."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop())
            logger.info("Background scanner task initiated.")

    async def stop_background_loop(self):
        """Cancels background scanner task."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("Background scanner task stopped.")

    async def _run_loop(self):
        while True:
            try:
                await self.perform_scan()
            except Exception as e:
                logger.error(f"Error during periodic scan cycle: {e}", exc_info=True)
            await asyncio.sleep(settings.REFRESH_INTERVAL_SECONDS)

    async def perform_scan(self, specific_market_hash_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes a complete market scanning pass.
        1. Queries CSFloat deals & liquid popular skins
        2. Queries Steam Community Market order books
        3. Calculates arbitrage opportunities
        4. Persists records to database incrementally in real time
        """
        if self.is_scanning:
            logger.info("Scan already in progress. Skipping duplicate invocation.")
            return {"status": "already_scanning"}

        self.is_scanning = True
        scan_start_time = datetime.now(timezone.utc)
        logger.info(f"{scan_start_time.strftime('%Y-%m-%d %H:%M:%S')} INFO Scan cycle started")

        try:
            # 1. Fetch CSFloat Listings
            min_price_cents = int(settings.MIN_PROFIT_USD * 100) if settings.MIN_PROFIT_USD else None
            max_price_cents = int(settings.MAX_SKIN_PRICE_USD * 100) if settings.MAX_SKIN_PRICE_USD else None

            candidate_items: Dict[str, Dict[str, Any]] = {}

            if specific_market_hash_name:
                cs_res = await csfloat_client.fetch_listings(
                    limit=1,
                    sort_by="lowest_price",
                    market_hash_name=specific_market_hash_name
                )
                if cs_res.get("data"):
                    candidate_items[specific_market_hash_name] = cs_res["data"][0]
            else:
                # Primary feed: best_deal (top arbitrage deals on CSFloat)
                cs_deals = await csfloat_client.fetch_listings(
                    limit=30,
                    sort_by="best_deal",
                    min_price_cents=min_price_cents,
                    max_price_cents=max_price_cents
                )

                if cs_deals.get("auth_required"):
                    self.csfloat_status = "AUTH_REQUIRED"
                    logger.warning("CSFloat requires API key in .env to fetch listings.")
                elif not cs_deals.get("success"):
                    self.csfloat_status = "ERROR"
                else:
                    self.csfloat_status = "CONNECTED"

                for item in cs_deals.get("data", []):
                    name = item["market_hash_name"]
                    if matching_service.is_weapon_or_knife(name):
                        if name not in candidate_items or item["price_cents"] < candidate_items[name]["price_cents"]:
                            candidate_items[name] = item

                # Secondary feed: Sample of high-liquidity popular skins
                for base in POPULAR_BASE_SKINS[:12]:
                    target_ft = f"{base} (Field-Tested)"
                    if target_ft not in candidate_items:
                        res = await csfloat_client.fetch_listings(
                            limit=1,
                            sort_by="lowest_price",
                            market_hash_name=target_ft
                        )
                        if res.get("data"):
                            candidate_items[target_ft] = res["data"][0]

            logger.info(f"Target skins to scan: {len(candidate_items)}")

            # Process skins found & commit incrementally to DB so UI updates in real time
            opportunities_updated = 0
            for hash_name, item in candidate_items.items():
                cs_price_cents = item["price_cents"]

                # 2. Fetch Steam Order Book
                steam_result = await steam_client.fetch_order_book(hash_name)
                if steam_result.get("success"):
                    self.steam_status = "CONNECTED"
                else:
                    if "429" in str(steam_result.get("error")):
                        self.steam_status = "RATE_LIMITED"
                    else:
                        self.steam_status = "ERROR"

                steam_highest_bid = steam_result.get("highest_buy_order_cents")
                steam_lowest_ask = steam_result.get("lowest_sell_order_cents")
                total_buy_orders = steam_result.get("total_buy_orders", 0)
                raw_pairs = steam_result.get("raw_order_book", [])
                steam_updated_at = steam_result.get("updated_at", scan_start_time)

                db: Session = SessionLocal()
                try:
                    # Resolve or create Skin in database
                    skin = db.query(Skin).filter(Skin.market_hash_name == hash_name).first()
                    parsed = matching_service.parse_market_hash_name(hash_name)
                    if not skin:
                        skin = Skin(
                            market_hash_name=hash_name,
                            weapon=parsed["weapon"],
                            skin_name=parsed["skin_name"],
                            exterior=parsed["exterior"],
                            is_stattrak=parsed["is_stattrak"],
                            is_souvenir=parsed["is_souvenir"],
                            icon_url=item.get("icon_url")
                        )
                        db.add(skin)
                        db.flush()
                    elif item.get("icon_url") and not skin.icon_url:
                        skin.icon_url = item.get("icon_url")

                    # Update CSFloat listing
                    cs_listing = db.query(CSFloatListing).filter(CSFloatListing.skin_id == skin.id).first()
                    if not cs_listing:
                        cs_listing = CSFloatListing(
                            skin_id=skin.id,
                            listing_id=item["listing_id"],
                            price_cents=cs_price_cents,
                            float_value=item.get("float_value"),
                            inspect_link=item.get("inspect_link"),
                            created_at=item["created_at"]
                        )
                        db.add(cs_listing)
                    else:
                        cs_listing.listing_id = item["listing_id"]
                        cs_listing.price_cents = cs_price_cents
                        cs_listing.float_value = item.get("float_value")
                        cs_listing.inspect_link = item.get("inspect_link")
                        cs_listing.created_at = item["created_at"]

                    # Update Steam Order Book
                    st_book = db.query(SteamOrderBook).filter(SteamOrderBook.skin_id == skin.id).first()
                    if not st_book:
                        st_book = SteamOrderBook(
                            skin_id=skin.id,
                            highest_buy_order_cents=steam_highest_bid,
                            lowest_sell_order_cents=steam_lowest_ask,
                            total_buy_orders=total_buy_orders,
                            order_book_json=json.dumps(raw_pairs),
                            updated_at=steam_updated_at
                        )
                        db.add(st_book)
                    else:
                        st_book.highest_buy_order_cents = steam_highest_bid
                        st_book.lowest_sell_order_cents = steam_lowest_ask
                        st_book.total_buy_orders = total_buy_orders
                        st_book.order_book_json = json.dumps(raw_pairs)
                        st_book.updated_at = steam_updated_at

                    # 3. Arbitrage Engine Calculations
                    if steam_highest_bid is not None and steam_highest_bid > 0 and cs_price_cents > 0:
                        gross_profit = arbitrage_engine.calculate_gross_profit(steam_highest_bid, cs_price_cents)
                        net_profit = arbitrage_engine.calculate_net_profit(steam_highest_bid, cs_price_cents)
                        gross_roi = arbitrage_engine.calculate_gross_roi(steam_highest_bid, cs_price_cents)
                        net_roi = arbitrage_engine.calculate_net_roi(steam_highest_bid, cs_price_cents)
                        liquidity = arbitrage_engine.calculate_liquidity_score(steam_highest_bid, raw_pairs, total_buy_orders)
                        top_qty = raw_pairs[0][1] if raw_pairs else 1

                        status = arbitrage_engine.evaluate_status(
                            csfloat_timestamp=cs_listing.created_at,
                            steam_timestamp=steam_updated_at,
                            max_data_age_seconds=settings.MAX_DATA_AGE_SECONDS,
                            has_active_listing=True,
                            has_active_bid=(steam_highest_bid > 0),
                            is_name_matched=matching_service.are_strictly_identical(hash_name, skin.market_hash_name)
                        )

                        opp = db.query(Opportunity).filter(Opportunity.skin_id == skin.id).first()
                        if not opp:
                            opp = Opportunity(
                                skin_id=skin.id,
                                csfloat_price_cents=cs_price_cents,
                                steam_highest_bid_cents=steam_highest_bid,
                                gross_profit_usd=gross_profit,
                                net_profit_usd=net_profit,
                                gross_roi_percent=gross_roi,
                                net_roi_percent=net_roi,
                                available_quantity=top_qty,
                                liquidity_score=liquidity,
                                status=status,
                                updated_at=scan_start_time
                            )
                            db.add(opp)
                        else:
                            opp.csfloat_price_cents = cs_price_cents
                            opp.steam_highest_bid_cents = steam_highest_bid
                            opp.gross_profit_usd = gross_profit
                            opp.net_profit_usd = net_profit
                            opp.gross_roi_percent = gross_roi
                            opp.net_roi_percent = net_roi
                            opp.available_quantity = top_qty
                            opp.liquidity_score = liquidity
                            opp.status = status
                            opp.updated_at = scan_start_time

                        # Record snapshot in history
                        history_record = OpportunityHistory(
                            skin_id=skin.id,
                            csfloat_price_cents=cs_price_cents,
                            steam_highest_bid_cents=steam_highest_bid,
                            gross_profit_usd=gross_profit,
                            net_profit_usd=net_profit,
                            gross_roi_percent=gross_roi,
                            net_roi_percent=net_roi,
                            liquidity_score=liquidity,
                            snapshot_at=scan_start_time
                        )
                        db.add(history_record)
                        opportunities_updated += 1
                        logger.info(f"Scanned: {hash_name} -> CSFloat: ${cs_price_cents/100:.2f} | Steam Bid: ${steam_highest_bid/100:.2f} (+{gross_roi:.1f}% Gross / +{net_roi:.1f}% Net)")

                    # Commit immediately so the opportunity is visible in UI instantly
                    db.commit()
                except Exception as ex_item:
                    db.rollback()
                    logger.error(f"Error saving skin {hash_name}: {ex_item}")
                finally:
                    db.close()

            self.last_scan_timestamp = scan_start_time
            logger.info(f"Scan cycle complete. Opportunities updated: {opportunities_updated}")

            return {
                "status": "success",
                "listings_fetched": len(candidate_items),
                "opportunities_updated": opportunities_updated,
                "timestamp": scan_start_time.isoformat()
            }

        except Exception as ex:
            logger.error(f"Scan failed with error: {ex}", exc_info=True)
            return {"status": "error", "error": str(ex)}
        finally:
            self.is_scanning = False

    async def scan_canonical_skin(self, base_skin_name: str) -> Dict[str, Any]:
        """
        Scans all 10 official market variants (5 Vanilla + 5 StatTrak) for a given CS2 base skin,
        updates listings, order books, and returns detected arbitrage opportunities.
        """
        from app.services.catalog_service import catalog_service
        variants = catalog_service.generate_10_variants(base_skin_name)
        if not variants:
            variants = [{"market_hash_name": base_skin_name, "is_stattrak": False, "exterior": None, "exterior_short": "N/A"}]

        scan_time = datetime.now(timezone.utc)
        results = []

        for v in variants:
            h_name = v["market_hash_name"]
            try:
                cs_res = await csfloat_client.fetch_listings(limit=1, sort_by="lowest_price", market_hash_name=h_name)
                cs_listings = cs_res.get("data", [])
                if not cs_listings:
                    continue

                item = cs_listings[0]
                steam_result = await steam_client.fetch_order_book(h_name)

                cs_price_cents = item["price_cents"]
                steam_highest_bid = steam_result.get("highest_buy_order_cents")
                steam_lowest_ask = steam_result.get("lowest_sell_order_cents")
                total_buy_orders = steam_result.get("total_buy_orders", 0)
                raw_pairs = steam_result.get("raw_order_book", [])
                steam_updated_at = steam_result.get("updated_at", scan_time)

                db: Session = SessionLocal()
                try:
                    skin = db.query(Skin).filter(Skin.market_hash_name == h_name).first()
                    parsed = matching_service.parse_market_hash_name(h_name)
                    if not skin:
                        skin = Skin(
                            market_hash_name=h_name,
                            weapon=parsed["weapon"],
                            skin_name=parsed["skin_name"],
                            exterior=parsed["exterior"],
                            is_stattrak=parsed["is_stattrak"],
                            is_souvenir=parsed["is_souvenir"],
                            icon_url=item.get("icon_url")
                        )
                        db.add(skin)
                        db.flush()
                    elif item.get("icon_url") and not skin.icon_url:
                        skin.icon_url = item.get("icon_url")

                    cs_listing = db.query(CSFloatListing).filter(CSFloatListing.skin_id == skin.id).first()
                    if not cs_listing:
                        cs_listing = CSFloatListing(
                            skin_id=skin.id,
                            listing_id=item["listing_id"],
                            price_cents=cs_price_cents,
                            float_value=item.get("float_value"),
                            inspect_link=item.get("inspect_link"),
                            created_at=item["created_at"]
                        )
                        db.add(cs_listing)
                    else:
                        cs_listing.listing_id = item["listing_id"]
                        cs_listing.price_cents = cs_price_cents
                        cs_listing.float_value = item.get("float_value")
                        cs_listing.inspect_link = item.get("inspect_link")
                        cs_listing.created_at = item["created_at"]

                    st_book = db.query(SteamOrderBook).filter(SteamOrderBook.skin_id == skin.id).first()
                    if not st_book:
                        st_book = SteamOrderBook(
                            skin_id=skin.id,
                            highest_buy_order_cents=steam_highest_bid,
                            lowest_sell_order_cents=steam_lowest_ask,
                            total_buy_orders=total_buy_orders,
                            order_book_json=json.dumps(raw_pairs),
                            updated_at=steam_updated_at
                        )
                        db.add(st_book)
                    else:
                        st_book.highest_buy_order_cents = steam_highest_bid
                        st_book.lowest_sell_order_cents = steam_lowest_ask
                        st_book.total_buy_orders = total_buy_orders
                        st_book.order_book_json = json.dumps(raw_pairs)
                        st_book.updated_at = steam_updated_at

                    if steam_highest_bid is not None and steam_highest_bid > 0 and cs_price_cents > 0:
                        gross_profit = arbitrage_engine.calculate_gross_profit(steam_highest_bid, cs_price_cents)
                        net_profit = arbitrage_engine.calculate_net_profit(steam_highest_bid, cs_price_cents)
                        gross_roi = arbitrage_engine.calculate_gross_roi(steam_highest_bid, cs_price_cents)
                        net_roi = arbitrage_engine.calculate_net_roi(steam_highest_bid, cs_price_cents)
                        liquidity = arbitrage_engine.calculate_liquidity_score(steam_highest_bid, raw_pairs, total_buy_orders)

                        opp = db.query(Opportunity).filter(Opportunity.skin_id == skin.id).first()
                        if not opp:
                            opp = Opportunity(
                                skin_id=skin.id,
                                csfloat_price_cents=cs_price_cents,
                                steam_highest_bid_cents=steam_highest_bid,
                                gross_profit_usd=gross_profit,
                                net_profit_usd=net_profit,
                                gross_roi_percent=gross_roi,
                                net_roi_percent=net_roi,
                                available_quantity=1,
                                liquidity_score=liquidity,
                                status="ACTIVE",
                                updated_at=scan_time
                            )
                            db.add(opp)
                        else:
                            opp.csfloat_price_cents = cs_price_cents
                            opp.steam_highest_bid_cents = steam_highest_bid
                            opp.gross_profit_usd = gross_profit
                            opp.net_profit_usd = net_profit
                            opp.gross_roi_percent = gross_roi
                            opp.net_roi_percent = net_roi
                            opp.liquidity_score = liquidity
                            opp.status = "ACTIVE"
                            opp.updated_at = scan_time

                        results.append({
                            "market_hash_name": h_name,
                            "exterior": v.get("exterior"),
                            "exterior_short": v.get("exterior_short", ""),
                            "is_stattrak": v.get("is_stattrak", False),
                            "csfloat_price_usd": round(cs_price_cents / 100.0, 2),
                            "steam_highest_bid_usd": round(steam_highest_bid / 100.0, 2),
                            "gross_profit_usd": gross_profit,
                            "net_profit_usd": net_profit,
                            "gross_roi_percent": gross_roi,
                            "net_roi_percent": net_roi,
                            "liquidity_score": liquidity
                        })

                    db.commit()
                except Exception as ex_db:
                    db.rollback()
                    logger.error(f"DB error persisting variant {h_name}: {ex_db}")
                finally:
                    db.close()

            except Exception as ex_net:
                logger.error(f"Network error fetching variant {h_name}: {ex_net}")

        return {
            "success": True,
            "base_skin": base_skin_name,
            "variants_checked": len(variants),
            "variants_found": len(results),
            "opportunities": results
        }

scanner_service = ScannerService()
