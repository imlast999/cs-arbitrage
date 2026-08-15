# CS2 Arbitrage Scanner — API Research Document

**Date of Research:** August 15, 2026  
**Status:** Verified via live network requests & real responses

---

## 1. CSFloat API

### 1.1 Endpoint Overview
- **Base URL:** `https://csfloat.com/api/v1`
- **Listings Endpoint:** `GET https://csfloat.com/api/v1/listings`
- **Single Listing / Inspect:** `GET https://csfloat.com/api/v1/listings/{id}`

### 1.2 Authentication
- **Mechanism:** API Key passed in the `Authorization` request header.
- **Header:** `Authorization: <CSFLOAT_API_KEY>`
- **Behavior without key:** Returns `HTTP 403 Forbidden` with body:
  ```json
  {"code": 1, "message": "You need to be logged in to search listings"}
  ```
- **How to obtain:** Users can generate an API key for free from their CSFloat Profile -> Developer tab.

### 1.3 Query Parameters
| Parameter | Type | Description |
|---|---|---|
| `type` | string | `buy_now` (instant purchase listings) or `auction` |
| `sort_by` | string | `lowest_price`, `best_deal`, `most_recent`, `expires_soon`, `lowest_float`, `highest_float` |
| `limit` | integer | Number of items per page (1 to 50, default: 50) |
| `cursor` | string | Opaque pagination cursor from the previous response |
| `market_hash_name`| string | Exact skin market hash name filter |
| `min_price` | integer | Minimum price in **cents** (e.g. `500` for $5.00) |
| `max_price` | integer | Maximum price in **cents** (e.g. `10000` for $100.00) |

### 1.4 Response Format
Listings return JSON arrays containing:
```json
[
  {
    "id": "123456789",
    "created_at": "2026-08-14T22:10:00.000Z",
    "type": "buy_now",
    "price": 3511,
    "seller": {
      "avatar": "...",
      "username": "..."
    },
    "item": {
      "market_hash_name": "AK-47 | Redline (Field-Tested)",
      "float_value": 0.18245,
      "wear_name": "Field-Tested",
      "is_stattrak": false,
      "is_souvenir": false,
      "icon_url": "..."
    }
  }
]
```

### 1.5 Rate Limits & Headers
- `x-ratelimit-limit`: Up to 50,000 requests per window.
- `x-ratelimit-remaining`: Decremented per request.
- `x-ratelimit-reset`: Unix timestamp of reset.
- Recommended client delay: 500ms to 1000ms between batch requests.

---

## 2. Steam Community Market API

### 2.1 Endpoint Overview
Steam operates an internal real-time JSON API used by its modern Server-Side Rendered (SSR) web client:
- **Endpoint:** `GET https://steamcommunity.com/market/orderbook`
- **Method:** `GET`
- **Authentication:** Public endpoint (no login required for reading order book data).

### 2.2 Parameters
| Parameter | Type | Example | Description |
|---|---|---|---|
| `q` | string | `Load` | Action trigger |
| `qp` | string | `[730,"AK-47 | Redline (Field-Tested)"]` | JSON-encoded array: `[appid, market_hash_name]` |
| `cc` | string | `US` | Country code for currency/regional formatting |
| `l` | string | `english` | Language |
| `currency`| integer| `1` | Currency ID (`1` = USD) |

### 2.3 Required Headers
- `x-valve-request-type: queryAction`
- `Referer: https://steamcommunity.com/market/listings/730/<URL_ENCODED_NAME>`
- `User-Agent: Mozilla/5.0 ...`

### 2.4 Response Structure
The endpoint returns real-time market depth:
```json
{
  "data": {
    "success": 1,
    "data": {
      "amtMaxBuyOrder": 3511,
      "amtMinSellOrder": 3513,
      "eCurrency": 1,
      "cBuyOrders": 53369,
      "cSellOrders": 1191,
      "rgCompactBuyOrders": [
        3511, 16,
        3510, 27,
        3474, 1,
        3473, 4
      ],
      "rgCompactSellOrders": [
        3513, 2,
        3515, 8
      ]
    }
  }
}
```

### 2.5 Interpretation of Data
- `amtMaxBuyOrder`: Highest active buy order in cents (e.g. `3511` = $35.11).
- `cBuyOrders`: Total count of active buy orders.
- `rgCompactBuyOrders`: Flat array structured as `[price_cents_tier1, quantity_tier1, price_cents_tier2, quantity_tier2, ...]`.
  - Example: `[3511, 16, 3510, 27]` means 16 orders at $35.11, and 27 orders at $35.10.

### 2.6 Steam Market Fees
Steam applies transaction and game fees upon order execution:
- **Steam Fee:** 5% (minimum $0.01)
- **CS2 Game Fee:** 10% (minimum $0.01)
- **Calculation Formula:**
  $$\text{Seller Receives} = \left\lfloor \frac{\text{Buyer Price}}{1.15} \right\rfloor$$
- **Example:** For a highest bid of $35.11 (3511 cents), the seller receives:
  $$\lfloor 3511 / 1.15 \rfloor = 3053\text{ cents} = \$30.53$$
- The scanner computes both **Gross Profit / ROI** and **Net Profit / ROI** so users have full visibility.

### 2.7 Steam Rate Limits & Resilience
- Steam enforces IP-based rate limiting (HTTP 429 if too many requests within a 60-second window).
- Mitigation in scanner:
  - Global token-bucket rate limiter (1 request every 1.5–2.0 seconds).
  - Concurrency limited to 1–2 simultaneous Steam requests.
  - Exponential backoff retry with jitter on 429 status.
  - In-memory & SQLite cache with TTL to avoid redundant calls.

---

## 3. Matching Specification

1. Matching is performed strictly via `market_hash_name`.
2. Exact string match required.
3. StatTrak items (`StatTrak™ ...`) are distinct items from vanilla variants.
4. Souvenir items (`Souvenir ...`) are distinct items from tournament/vanilla variants.
5. Exteriors (`Factory New`, `Minimal Wear`, `Field-Tested`, `Well-Worn`, `Battle-Scarred`) must match identically.
