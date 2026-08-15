# CS2 Arbitrage Scanner — System Architecture

## Overview

The **CS2 Arbitrage Scanner** is a high-accuracy, real-time market scanner that identifies price discrepancies between CSFloat lowest ask listings and Steam Community Market highest buy orders (with granular order book depth).

```
 ┌─────────────────────────────────────────────────────────┐
 │                   Frontend (SPA Dashboard)              │
 │   - Dark glassmorphism UI                               │
 │   - Real-time opportunities table                       │
 │   - Order book visualizer & execution simulator         │
 │   - Dynamic filters & live data freshness counters      │
 └────────────────────────────┬────────────────────────────┘
                              │ HTTP / JSON
                              ▼
 ┌─────────────────────────────────────────────────────────┐
 │                  FastAPI Application Server             │
 │   - REST Endpoints (/api/status, /api/opportunities...) │
 │   - Background Async Scanner Task                       │
 └─────────────┬─────────────────────────────┬─────────────┘
               │                             │
       ┌───────▼────────┐           ┌────────▼────────┐
       │ CSFloat Client │           │  Steam Client   │
       │ (/api/v1/...)  │           │ (/orderbook...) │
       └───────┬────────┘           └────────┬────────┘
               │ Rate-limited HTTP Pool      │
               └──────────────┬──────────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │    Arbitrage Engine Core     │
               │  - Strict market_hash_name   │
               │  - Gross & Net ROI / Profit  │
               │  - Multi-tier Order Book     │
               │  - Liquidity Scoring         │
               │  - Freshness & Staleness     │
               └──────────────┬───────────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │   SQLite Database (SQLAlchemy)│
               │  - Skins                     │
               │  - CSFloat Listings          │
               │  - Steam Order Books         │
               │  - Opportunities             │
               │  - Opportunity History       │
               └──────────────────────────────┘
```

---

## 1. Core Modules

### 1.1 `services/http_client.py`
Centralized asynchronous HTTP client wrapping `httpx.AsyncClient`:
- **Domain-specific rate limiting:** Configurable requests-per-second per target domain.
- **Concurrency control:** Async `Semaphore` to restrict simultaneous open sockets.
- **Resilience:** Automatic retry with exponential backoff on HTTP 429 (Too Many Requests) or 5xx server errors.
- **Safe logging:** Strips API keys and credentials before emitting logs.

### 1.2 `services/matching_service.py`
Guarantees zero false positives across skin types:
- Identifies skin category, weapon, skin name, exterior wear, StatTrak status, and Souvenir status.
- Strict equality on canonical `market_hash_name`.

### 1.3 `services/arbitrage_engine.py`
Pure computation engine with zero external dependencies:
- **Gross Profit:** `highest_steam_bid - lowest_csfloat_price`
- **Gross ROI:** `(gross_profit / lowest_csfloat_price) * 100`
- **Steam Fee Engine:** Valve transaction fee ($5\%$) + CS2 fee ($10\%$) with minimum $0.01 threshold.
- **Net Profit & Net ROI:** Calculated after subtracting exact Steam fees.
- **Order Book Depth Walk (`calculate_execution_value`):** Simulates selling $N$ units into successive bid tiers.
- **Liquidity Score:** Categorized as `HIGH`, `MEDIUM`, or `LOW` based on total active bids and depth within 5% of top bid.
- **Freshness Evaluation:** Flags items as `STALE` if the last price update exceeds `MAX_DATA_AGE_SECONDS`.

### 1.4 `services/scanner_service.py`
Orchestrator that executes periodic or on-demand scanning cycles:
1. Fetches CSFloat listings within price/type criteria.
2. Resolves corresponding Steam Market order books.
3. Computes arbitrage metrics, liquidity, and validity.
4. Updates SQLite database records and appends snapshot rows to `opportunity_history`.

---

## 2. Database Schema

### `skins`
| Column | Type | Description |
|---|---|---|
| `id` | Integer (PK) | Auto-increment primary key |
| `market_hash_name` | String (Unique, Index) | Canonical CS2 item name |
| `weapon` | String | e.g. "AK-47", "AWP" |
| `skin_name` | String | e.g. "Redline", "Printstream" |
| `exterior` | String | e.g. "Field-Tested", "Factory New" |
| `is_stattrak` | Boolean | True if StatTrak™ |
| `is_souvenir` | Boolean | True if Souvenir |
| `icon_url` | String | Image asset URL |
| `created_at` | DateTime | Timestamp of creation |
| `updated_at` | DateTime | Timestamp of last update |

### `csfloat_listings`
| Column | Type | Description |
|---|---|---|
| `id` | Integer (PK) | Auto-increment primary key |
| `skin_id` | Integer (FK -> skins.id) | Referenced skin |
| `listing_id` | String (Unique) | CSFloat listing identifier |
| `price_cents` | Integer | Listing price in USD cents |
| `float_value` | Float | Item float value |
| `inspect_link` | String | In-game inspect link |
| `created_at` | DateTime | Timestamp of listing fetch |

### `steam_order_books`
| Column | Type | Description |
|---|---|---|
| `id` | Integer (PK) | Auto-increment primary key |
| `skin_id` | Integer (FK -> skins.id) | Referenced skin |
| `highest_buy_order_cents` | Integer | Top buy order in USD cents |
| `lowest_sell_order_cents` | Integer | Lowest sell listing in USD cents |
| `total_buy_orders` | Integer | Total active bids count |
| `order_book_json` | Text | Granular `[price, qty]` order book tiers |
| `updated_at` | DateTime | Timestamp of order book fetch |

### `opportunities`
| Column | Type | Description |
|---|---|---|
| `id` | Integer (PK) | Auto-increment primary key |
| `skin_id` | Integer (FK -> skins.id) | Referenced skin |
| `csfloat_price_cents` | Integer | CSFloat lowest ask in cents |
| `steam_highest_bid_cents`| Integer | Steam highest buy order in cents |
| `gross_profit_usd` | Float | Gross profit in USD |
| `gross_roi_percent` | Float | Gross ROI % |
| `net_profit_usd` | Float | Net profit after Steam fees |
| `net_roi_percent` | Float | Net ROI % |
| `available_quantity` | Integer | Buy order volume at highest bid |
| `liquidity_score` | String | HIGH, MEDIUM, LOW |
| `status` | String | ACTIVE, STALE, UNVERIFIED |
| `updated_at` | DateTime | Last calculation timestamp |

### `opportunity_history`
| Column | Type | Description |
|---|---|---|
| `id` | Integer (PK) | Auto-increment primary key |
| `skin_id` | Integer (FK -> skins.id) | Referenced skin |
| `csfloat_price_cents` | Integer | Price snapshot |
| `steam_highest_bid_cents`| Integer | Bid snapshot |
| `gross_roi_percent` | Float | Gross ROI snapshot |
| `net_roi_percent` | Float | Net ROI snapshot |
| `liquidity_score` | String | Liquidity snapshot |
| `snapshot_at` | DateTime | Timestamp of snapshot |
