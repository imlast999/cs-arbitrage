# CS2 Arbitrage Scanner

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue?logo=python&logoColor=white" alt="Python Versions">
  <img src="https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License: MIT">
  <img src="https://img.shields.io/badge/Tests-Pytest%20Passing-brightgreen?logo=pytest&logoColor=white" alt="Tests">
  <img src="https://img.shields.io/badge/Aesthetic-Dark%20Glassmorphism-6366f1" alt="Glassmorphism UI">
</p>

A real-time, high-precision market scanner that detects arbitrage opportunities between **CSFloat** (lowest ask listings) and **Steam Community Market** (highest buy orders & multi-tier order book depth).

---

## 🚀 Key Features

- **Strict Skin Matching:** Canonical matching via `market_hash_name` to prevent cross-matching between vanilla skins, `StatTrak™`, `Souvenir` editions, and differing wear conditions (`Factory New`, `Minimal Wear`, `Field-Tested`, `Well-Worn`, `Battle-Scarred`).
- **Real Multi-Tier Order Book:** Integrates Steam's modern `/market/orderbook` API to retrieve exact price and quantity order tiers rather than relying solely on isolated top bids.
- **Granular Execution Simulator:** Walk real order book depth to calculate the exact executable value, cost, proceeds, and ROI when buying and selling $N$ units.
- **Transparent Steam Fee Calculation:** Accurately computes Valve's $5\%$ transaction fee + $10\%$ CS2 game fee ($\approx 13.04\%$ total fee) using Steam's exact integer arithmetic ($\lfloor P / 1.15 \rfloor$), displaying both **Gross** and **Net** profit/ROI.
- **Liquidity Scoring:** Evaluates order book volume and depth within $5\%$ of the highest bid, classifying markets into `HIGH`, `MEDIUM`, or `LOW` liquidity.
- **Data Freshness & Staleness Engine:** Real-time relative age counters with automatic `STALE` status transitions when data exceeds `MAX_DATA_AGE_SECONDS`.
- **Zero Fake / Hardcoded Data Policy:** Strictly queries live APIs or flags unverified states transparently.
- **Centralized Resilient HTTP Client:** Per-domain token bucket rate limiting, concurrency semaphores, and exponential backoff retry on HTTP 429 and 5xx.
- **Modern Dark Glassmorphism UI:** Built with dark theme aesthetics, interactive filters, auto-refresh intervals, and interactive detail modals.

---

## 🏗️ System Architecture

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

- [API Research Documentation](docs/API_RESEARCH.md)
- [Architecture Details](docs/ARCHITECTURE.md)

---

## 📦 Installation & Quickstart

### Local Setup
```bash
# 1. Clone repository
git clone https://github.com/imlast999/cs-arbitrage.git
cd cs-arbitrage

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env

# 4. Start backend server
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Open **[http://localhost:8000](http://localhost:8000)** in your web browser.

---

### 🐳 Docker & Docker Compose Setup
```bash
docker compose up -d --build
```
The scanner will be live at **[http://localhost:8000](http://localhost:8000)**.

---

## ⚙️ Configuration (`.env`)

```env
# CSFloat API Configuration
# Obtain your free developer key at: https://csfloat.com -> Profile -> Developer
CSFLOAT_API_KEY=your_csfloat_api_key_here
CSFLOAT_BASE_URL=https://csfloat.com/api/v1

# Steam Community Market Configuration
STEAM_BASE_URL=https://steamcommunity.com/market

# Database
DATABASE_URL=sqlite:///./arbitrage.db

# Scanner Settings
REFRESH_INTERVAL_SECONDS=60
MAX_DATA_AGE_SECONDS=120
MAX_CONCURRENT_REQUESTS=2

# Arbitrage Filter Defaults
MIN_ROI_PERCENT=10.0
MIN_PROFIT_USD=1.00
MAX_SKIN_PRICE_USD=1000.00
MIN_STEAM_QUANTITY=1
```

---

## 🧪 Running Tests

```bash
python -m pytest -v
```

---

## 📊 Understanding Metrics

### 1. Gross vs Net ROI
- **Gross ROI:** Calculated strictly on the spread between the Steam Highest Buy Order and CSFloat Lowest Ask:
  $$\text{Gross Profit} = \text{Steam Bid} - \text{CSFloat Ask}$$
  $$\text{Gross ROI} = \frac{\text{Gross Profit}}{\text{CSFloat Ask}} \times 100$$
- **Net ROI:** Accounts for Steam Community Market transaction fees (Valve 5% + CS2 10%):
  $$\text{Seller Receives} = \left\lfloor \frac{\text{Steam Bid}}{1.15} \right\rfloor$$
  $$\text{Net Profit} = \text{Seller Receives} - \text{CSFloat Ask}$$
  $$\text{Net ROI} = \frac{\text{Net Profit}}{\text{CSFloat Ask}} \times 100$$

### 2. Liquidity Score
- **`HIGH`:** $\ge 10$ orders at top bid tier OR $\ge 25$ total orders within $5\%$ of highest bid.
- **`MEDIUM`:** $\ge 3$ orders at top tier OR $\ge 8$ orders within $5\%$ of highest bid.
- **`LOW`:** Thin order book with only 1–2 orders at top bid.

---

## ⚠️ Disclaimer & Safe Usage

1. **Potential Arbitrage:** Detected opportunities reflect current market order books. Market conditions can change rapidly.
2. **7-Day Steam Trade Hold:** Skins purchased on CSFloat are subject to Valve's standard 7-day inventory trade cooldown before they can be relisted on Steam.
3. **No Account Automation:** This tool is strictly a **market scanner** and **does not** execute trades, manage Steam credentials, or store private account cookies.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
