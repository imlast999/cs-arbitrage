// CS2 Arbitrage Scanner — Frontend Application Logic

let currentOpportunities = [];
let autoRefreshTimer = null;
let currentSelectedOppId = null;

// Initialize app on DOM ready
document.addEventListener("DOMContentLoaded", () => {
    setupEventListeners();
    fetchSystemStatus();
    loadOpportunities();
    setupAutoRefresh();

    // Periodic system status poll
    setInterval(fetchSystemStatus, 5000);
});

function setupEventListeners() {
    // Manual scan button
    document.getElementById("btn-manual-scan").addEventListener("click", () => {
        triggerScan();
    });

    // Quick skin probe button
    document.getElementById("btn-quick-scan").addEventListener("click", () => {
        const input = document.getElementById("input-custom-skin");
        const skinName = input.value.trim();
        if (skinName) {
            triggerScan(skinName);
        }
    });

    // Filter changes
    const filterInputs = [
        "filter-min-roi",
        "filter-min-net-roi",
        "filter-max-price",
        "filter-min-profit",
        "filter-liquidity",
        "filter-sort"
    ];

    filterInputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener("change", () => loadOpportunities());
            if (el.tagName === "INPUT") {
                el.addEventListener("keyup", debounce(() => loadOpportunities(), 400));
            }
        }
    });

    // Refresh interval dropdown
    document.getElementById("filter-refresh").addEventListener("change", (e) => {
        setupAutoRefresh();
    });

    // Modal close
    document.getElementById("btn-close-modal").addEventListener("click", closeModal);
    document.getElementById("detail-modal").addEventListener("click", (e) => {
        if (e.target.id === "detail-modal") {
            closeModal();
        }
    });

    // Execution Simulator Button
    document.getElementById("btn-run-sim").addEventListener("click", () => {
        runSimulation();
    });
}

function setupAutoRefresh() {
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
        autoRefreshTimer = null;
    }

    const val = parseInt(document.getElementById("filter-refresh").value, 10);
    if (val > 0) {
        autoRefreshTimer = setInterval(() => {
            loadOpportunities(true);
        }, val * 1000);
    }
}

// Fetch System Status & Health
async function fetchSystemStatus() {
    try {
        const resp = await fetch("/api/status");
        if (!resp.ok) return;
        const data = await resp.json();

        // Update CSFloat Status Badge
        const csBadge = document.getElementById("csfloat-status-badge");
        const csText = document.getElementById("csfloat-status-text");
        const authBanner = document.getElementById("auth-warning-banner");

        if (data.csfloat_connected) {
            csBadge.className = "status-item status-connected";
            csText.innerText = "Connected";
            authBanner.style.display = "none";
        } else if (data.csfloat_auth_status === "NO_API_KEY") {
            csBadge.className = "status-item status-warn";
            csText.innerText = "Auth Required";
            authBanner.style.display = "flex";
        } else {
            csBadge.className = "status-item status-error";
            csText.innerText = "Error";
        }

        // Update Steam Status Badge
        const steamBadge = document.getElementById("steam-status-badge");
        const steamText = document.getElementById("steam-status-text");

        if (data.steam_connected) {
            steamBadge.className = "status-item status-connected";
            steamText.innerText = "Connected";
        } else if (data.steam_status === "RATE_LIMITED") {
            steamBadge.className = "status-item status-warn";
            steamText.innerText = "Rate Limited";
        } else {
            steamBadge.className = "status-item status-connected";
            steamText.innerText = "Ready";
        }

        // Last scan timer
        const syncText = document.getElementById("last-sync-time");
        if (data.seconds_since_last_scan !== null) {
            syncText.innerText = `${data.seconds_since_last_scan}s ago`;
        } else {
            syncText.innerText = "Never";
        }

        // Scan button spinner
        const scanBtn = document.getElementById("btn-manual-scan");
        const scanBtnText = document.getElementById("btn-scan-text");
        if (data.is_scanning) {
            scanBtn.disabled = true;
            scanBtnText.innerText = "Scanning...";
        } else {
            scanBtn.disabled = false;
            scanBtnText.innerText = "Scan Now";
        }

        // Update stats
        document.getElementById("stat-total-count").innerText = data.total_opportunities;
        document.getElementById("stat-active-count").innerText = data.active_opportunities;

    } catch (e) {
        console.error("Error fetching system status:", e);
    }
}

// Fetch & Render Opportunities Table
async function loadOpportunities(isBackground = false) {
    const tbody = document.getElementById("opps-tbody");
    if (!isBackground && currentOpportunities.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="12">
                    <div class="loading-state">
                        <div class="spinner"></div>
                        <p>Fetching active opportunities...</p>
                    </div>
                </td>
            </tr>
        `;
    }

    try {
        const minRoi = document.getElementById("filter-min-roi").value;
        const minNetRoi = document.getElementById("filter-min-net-roi").value;
        const maxPrice = document.getElementById("filter-max-price").value;
        const minProfit = document.getElementById("filter-min-profit").value;
        const minLiq = document.getElementById("filter-liquidity").value;
        const sortBy = document.getElementById("filter-sort").value;

        const params = new URLSearchParams();
        if (minRoi) params.append("min_roi", minRoi);
        if (minNetRoi) params.append("min_net_roi", minNetRoi);
        if (maxPrice) params.append("max_price", maxPrice);
        if (minProfit) params.append("min_profit", minProfit);
        if (minLiq) params.append("min_liquidity", minLiq);
        if (sortBy) params.append("sort_by", sortBy);

        const resp = await fetch(`/api/opportunities?${params.toString()}`);
        if (!resp.ok) throw new Error("Failed to load opportunities");

        const data = await resp.json();
        currentOpportunities = data;

        renderOpportunitiesTable(data);

        // Update top ROI stats
        if (data.length > 0) {
            const topGross = Math.max(...data.map(o => o.gross_roi_percent));
            const topNet = Math.max(...data.map(o => o.net_roi_percent));
            document.getElementById("stat-top-roi").innerText = `${topGross.toFixed(1)}%`;
            document.getElementById("stat-top-net-roi").innerText = `${topNet.toFixed(1)}%`;
        }

    } catch (err) {
        console.error("Failed to load opportunities:", err);
        if (!isBackground) {
            tbody.innerHTML = `
                <tr class="empty-row">
                    <td colspan="12">
                        <div class="loading-state">
                            <p style="color: var(--accent-rose);">Error connecting to API. Please verify server status.</p>
                        </div>
                    </td>
                </tr>
            `;
        }
    }
}

function renderOpportunitiesTable(opps) {
    const tbody = document.getElementById("opps-tbody");
    if (opps.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="12">
                    <div class="loading-state">
                        <p>No arbitrage opportunities matching current filters.</p>
                        <span style="font-size: 0.8rem; color: var(--text-muted);">Try lowering the Min ROI or trigger a fresh scan above.</span>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    let rowsHtml = "";
    opps.forEach((opp, index) => {
        const rank = index + 1;
        const skin = opp.skin;

        let badgesHtml = "";
        if (skin.is_stattrak) badgesHtml += `<span class="badge-tag badge-stattrak">StatTrak™</span>`;
        if (skin.is_souvenir) badgesHtml += `<span class="badge-tag badge-souvenir">Souvenir</span>`;
        if (skin.exterior) badgesHtml += `<span class="badge-tag badge-wear">${escapeHtml(skin.exterior)}</span>`;

        const profitClass = opp.gross_profit_usd >= 0 ? "profit-val" : "text-danger";
        const netProfitClass = opp.net_profit_usd >= 0 ? "stat-purple" : "text-danger";

        rowsHtml += `
            <tr class="opp-row" onclick="openDetailModal(${opp.id})">
                <td class="rank-badge">#${rank}</td>
                <td>
                    <div class="skin-cell">
                        <span class="skin-name">${escapeHtml(skin.market_hash_name)}</span>
                        <div class="skin-sub">${badgesHtml}</div>
                    </div>
                </td>
                <td class="price-val">$${opp.csfloat_price_usd.toFixed(2)}</td>
                <td class="price-val">$${opp.steam_highest_bid_usd.toFixed(2)}</td>
                <td class="${profitClass}">+$${opp.gross_profit_usd.toFixed(2)}</td>
                <td class="roi-val">${opp.gross_roi_percent.toFixed(1)}%</td>
                <td class="net-roi-val">${opp.net_roi_percent.toFixed(1)}%</td>
                <td class="price-val">${opp.available_quantity}</td>
                <td><span class="badge-liq liq-${opp.liquidity_score}">${opp.liquidity_score}</span></td>
                <td><span class="badge-age">${opp.data_age_seconds}s</span></td>
                <td><span class="badge-status status-${opp.status}">${opp.status}</span></td>
                <td>
                    <button class="btn-secondary" onclick="event.stopPropagation(); openDetailModal(${opp.id})">
                        Details ➔
                    </button>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = rowsHtml;
}

// Open Detail Modal & Load Full Granular Order Book
async function openDetailModal(opportunityId) {
    currentSelectedOppId = opportunityId;
    const modal = document.getElementById("detail-modal");
    modal.style.display = "flex";

    // Set initial loading state
    document.getElementById("modal-skin-name").innerText = "Loading details...";
    document.getElementById("modal-badges").innerHTML = "";
    document.getElementById("modal-orderbook-tbody").innerHTML = `<tr><td colspan="3" class="text-center text-muted">Loading order book tiers...</td></tr>`;
    document.getElementById("sim-results-box").style.display = "none";

    try {
        const resp = await fetch(`/api/opportunities/${opportunityId}`);
        if (!resp.ok) throw new Error("Failed to load opportunity detail");
        const data = await resp.json();

        // Title & Badges
        document.getElementById("modal-skin-name").innerText = data.skin.market_hash_name;
        let badgesHtml = "";
        if (data.skin.is_stattrak) badgesHtml += `<span class="badge-tag badge-stattrak">StatTrak™</span>`;
        if (data.skin.is_souvenir) badgesHtml += `<span class="badge-tag badge-souvenir">Souvenir</span>`;
        if (data.skin.exterior) badgesHtml += `<span class="badge-tag badge-wear">${escapeHtml(data.skin.exterior)}</span>`;
        badgesHtml += `<span class="badge-status status-${data.status}">${data.status}</span>`;
        document.getElementById("modal-badges").innerHTML = badgesHtml;

        // CSFloat Card
        document.getElementById("modal-csfloat-price").innerText = `$${data.csfloat_price_usd.toFixed(2)}`;
        document.getElementById("modal-csfloat-link").href = data.csfloat_url;
        document.getElementById("modal-float-val").innerText = data.csfloat_listing && data.csfloat_listing.float_value !== null ? data.csfloat_listing.float_value.toFixed(5) : "N/A";
        document.getElementById("modal-listing-id").innerText = data.csfloat_listing ? data.csfloat_listing.listing_id : "N/A";

        const inspectWrap = document.getElementById("modal-inspect-wrap");
        if (data.csfloat_listing && data.csfloat_listing.inspect_link) {
            inspectWrap.innerHTML = `<a href="${data.csfloat_listing.inspect_link}" class="link-external">Inspect in Game</a>`;
        } else {
            inspectWrap.innerHTML = `<span class="text-muted">None</span>`;
        }

        // Steam Card
        document.getElementById("modal-steam-bid").innerText = `$${data.steam_highest_bid_usd.toFixed(2)}`;
        document.getElementById("modal-steam-link").href = data.steam_url;
        document.getElementById("modal-steam-ask").innerText = data.steam_order_book && data.steam_order_book.lowest_sell_order_usd ? `$${data.steam_order_book.lowest_sell_order_usd.toFixed(2)}` : "N/A";
        document.getElementById("modal-total-bids").innerText = data.steam_order_book ? data.steam_order_book.total_buy_orders.toLocaleString() : "0";
        document.getElementById("modal-liquidity-val").innerText = data.liquidity_score;

        // Arbitrage Metrics & Fee Breakdown
        document.getElementById("modal-gross-profit").innerText = `+$${data.gross_profit_usd.toFixed(2)}`;
        document.getElementById("modal-gross-roi").innerText = `${data.gross_roi_percent.toFixed(1)}%`;
        document.getElementById("modal-steam-fee").innerText = `-$${data.fee_breakdown.steam_total_fee_usd.toFixed(2)}`;
        document.getElementById("modal-seller-receives").innerText = `$${data.fee_breakdown.steam_seller_receives_usd.toFixed(2)}`;
        document.getElementById("modal-net-profit").innerText = `+$${data.net_profit_usd.toFixed(2)}`;
        document.getElementById("modal-net-roi").innerText = `${data.net_roi_percent.toFixed(1)}%`;

        // Render Granular Order Book Tiers
        const obTbody = document.getElementById("modal-orderbook-tbody");
        if (data.steam_order_book && data.steam_order_book.tiers && data.steam_order_book.tiers.length > 0) {
            let obHtml = "";
            data.steam_order_book.tiers.slice(0, 15).forEach(tier => {
                obHtml += `
                    <tr>
                        <td class="stat-cyan">$${tier.price_usd.toFixed(2)}</td>
                        <td>${tier.quantity} orders</td>
                        <td class="stat-purple">$${tier.net_payout_usd.toFixed(2)}</td>
                    </tr>
                `;
            });
            obTbody.innerHTML = obHtml;
        } else {
            obTbody.innerHTML = `<tr><td colspan="3" class="text-center text-muted">No live order book tiers available</td></tr>`;
        }

        // Auto-run simulation for default qty 5
        runSimulation();

    } catch (e) {
        console.error("Error opening detail modal:", e);
    }
}

// Run Multi-Item Execution Simulation against real Steam order book
async function runSimulation() {
    if (!currentSelectedOppId) return;

    const qtyInput = document.getElementById("sim-quantity-input");
    const qty = parseInt(qtyInput.value, 10) || 1;

    try {
        const resp = await fetch(`/api/opportunities/${currentSelectedOppId}/simulate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ quantity: qty })
        });

        if (!resp.ok) throw new Error("Simulation failed");
        const sim = await resp.json();

        const resBox = document.getElementById("sim-results-box");
        resBox.style.display = "flex";

        document.getElementById("sim-fulfilled-qty").innerText = `${sim.fulfilled_quantity} / ${sim.target_quantity} items`;
        document.getElementById("sim-total-cost").innerText = `$${sim.total_cost_csfloat_usd.toFixed(2)}`;
        document.getElementById("sim-gross-payout").innerText = `$${sim.gross_execution_value_usd.toFixed(2)}`;
        document.getElementById("sim-net-payout").innerText = `$${sim.net_execution_value_usd.toFixed(2)}`;
        
        const netProfitEl = document.getElementById("sim-net-profit");
        netProfitEl.innerText = `${sim.total_net_profit_usd >= 0 ? '+' : ''}$${sim.total_net_profit_usd.toFixed(2)}`;
        netProfitEl.className = sim.total_net_profit_usd >= 0 ? "stat-purple" : "text-danger";

        const netRoiEl = document.getElementById("sim-net-roi");
        netRoiEl.innerText = `${sim.effective_net_roi_percent.toFixed(1)}%`;
        netRoiEl.className = sim.effective_net_roi_percent >= 0 ? "stat-purple" : "text-danger";

    } catch (err) {
        console.error("Simulation error:", err);
    }
}

function closeModal() {
    document.getElementById("detail-modal").style.display = "none";
    currentSelectedOppId = null;
}

// Trigger Manual or Quick Scan
async function triggerScan(skinName = null) {
    const scanBtn = document.getElementById("btn-manual-scan");
    const scanBtnText = document.getElementById("btn-scan-text");
    scanBtn.disabled = true;
    scanBtnText.innerText = "Scanning...";

    try {
        let url = "/api/scan";
        if (skinName) {
            url += `?market_hash_name=${encodeURIComponent(skinName)}`;
        }
        const resp = await fetch(url, { method: "POST" });
        await resp.json();
        await fetchSystemStatus();
        await loadOpportunities();
    } catch (e) {
        console.error("Scan error:", e);
    } finally {
        scanBtn.disabled = false;
        scanBtnText.innerText = "Scan Now";
    }
}

// Helper utilities
function escapeHtml(str) {
    if (!str) return "";
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
