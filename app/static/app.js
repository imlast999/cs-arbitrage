// CS2 Arbitrage Terminal — Frontend Application Logic

let currentOpportunities = [];
let favoriteItems = [];
let favoriteNamesSet = new Set();
let tradeRecords = [];
let steamInventoryData = null;
let autoRefreshTimer = null;
let currentSelectedOppDetail = null;

// Initialize app on DOM ready
document.addEventListener("DOMContentLoaded", () => {
    setupEventListeners();
    setupTabNavigation();
    fetchConnections();
    fetchFavorites();
    fetchTrades();
    fetchSystemStatus();
    loadOpportunities();
    setupAutoRefresh();

    // Periodic system & connection status poll
    setInterval(() => {
        fetchSystemStatus();
        fetchConnections();
    }, 5000);
});

// ==============================================
// TAB NAVIGATION
// ==============================================
function setupTabNavigation() {
    const tabs = document.querySelectorAll(".nav-tab");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");

            const targetPaneId = tab.getAttribute("data-tab");
            document.querySelectorAll(".tab-pane").forEach(pane => {
                pane.classList.remove("active");
                pane.style.display = "none";
            });

            const activePane = document.getElementById(targetPaneId);
            if (activePane) {
                activePane.classList.add("active");
                activePane.style.display = "block";
            }

            // Refresh specific data when tab is opened
            if (targetPaneId === "tab-inventory") {
                fetchSteamInventory();
            } else if (targetPaneId === "tab-favorites") {
                fetchFavorites();
            } else if (targetPaneId === "tab-trades") {
                fetchTrades();
            } else if (targetPaneId === "tab-opportunities") {
                loadOpportunities(true);
            }
        });
    });
}

// ==============================================
// EVENT LISTENERS SETUP
// ==============================================
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
    document.getElementById("filter-refresh").addEventListener("change", () => {
        setupAutoRefresh();
    });

    // Banner CSFloat connect button
    const bannerBtn = document.getElementById("btn-banner-open-csfloat");
    if (bannerBtn) {
        bannerBtn.addEventListener("click", () => openCsfloatModal());
    }

    // Banner Steam connect button in inventory tab
    const bannerSteamBtn = document.getElementById("btn-banner-connect-steam");
    if (bannerSteamBtn) {
        bannerSteamBtn.addEventListener("click", () => openSteamModal());
    }

    // Sync Steam Inventory button
    const syncInvBtn = document.getElementById("btn-sync-steam-inv");
    if (syncInvBtn) {
        syncInvBtn.addEventListener("click", () => fetchSteamInventory(true));
    }

    // Modal Close buttons
    document.getElementById("btn-close-modal").addEventListener("click", closeModal);
    document.getElementById("detail-modal").addEventListener("click", (e) => {
        if (e.target.id === "detail-modal") closeModal();
    });

    // Steam Modal Events
    document.getElementById("btn-steam-connect").addEventListener("click", openSteamModal);
    document.getElementById("btn-close-steam-modal").addEventListener("click", closeSteamModal);
    document.getElementById("modal-steam").addEventListener("click", (e) => {
        if (e.target.id === "modal-steam") closeSteamModal();
    });
    document.getElementById("form-steam-connect").addEventListener("submit", handleSteamConnectSubmit);
    document.getElementById("btn-disconnect-steam").addEventListener("click", handleSteamDisconnect);

    // CSFloat Modal Events
    document.getElementById("btn-csfloat-connect").addEventListener("click", openCsfloatModal);
    document.getElementById("btn-close-csfloat-modal").addEventListener("click", closeCsfloatModal);
    document.getElementById("modal-csfloat").addEventListener("click", (e) => {
        if (e.target.id === "modal-csfloat") closeCsfloatModal();
    });
    document.getElementById("form-csfloat-connect").addEventListener("submit", handleCsfloatConnectSubmit);
    document.getElementById("btn-disconnect-csfloat").addEventListener("click", handleCsfloatDisconnect);

    // Favorites events
    document.getElementById("btn-add-favorite").addEventListener("click", handleAddFavoriteFromInput);
    document.getElementById("input-add-fav").addEventListener("keydown", (e) => {
        if (e.key === "Enter") handleAddFavoriteFromInput();
    });

    // Detail Modal Favorite & Trade buttons
    document.getElementById("modal-btn-toggle-fav").addEventListener("click", handleModalFavToggle);
    document.getElementById("modal-btn-record-trade").addEventListener("click", handleRecordTradeFromModal);

    // Manual Trade Modal
    document.getElementById("btn-open-manual-trade").addEventListener("click", openManualTradeModal);
    document.getElementById("btn-close-manual-trade").addEventListener("click", closeManualTradeModal);
    document.getElementById("modal-manual-trade").addEventListener("click", (e) => {
        if (e.target.id === "modal-manual-trade") closeManualTradeModal();
    });
    document.getElementById("form-manual-trade").addEventListener("submit", handleManualTradeSubmit);

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

// ==============================================
// ACCOUNT CONNECTIONS (STEAM & CSFLOAT)
// ==============================================
async function fetchConnections() {
    try {
        const resp = await fetch("/api/connections");
        if (!resp.ok) return;
        const data = await resp.json();

        // Update Steam Button UI
        const steamBtn = document.getElementById("btn-steam-connect");
        const steamLabel = document.getElementById("steam-btn-label");
        const invBanner = document.getElementById("steam-inv-not-connected-banner");

        if (data.steam.is_connected) {
            steamBtn.className = "btn-account btn-steam connected";
            const name = data.steam.account_name || "Steam";
            steamLabel.innerText = `🎮 ${name}`;
            if (invBanner) invBanner.style.display = "none";
        } else {
            steamBtn.className = "btn-account btn-steam";
            steamLabel.innerText = "🎮 Conectar Steam";
            if (invBanner) invBanner.style.display = "flex";
        }

        // Update CSFloat Button UI
        const csBtn = document.getElementById("btn-csfloat-connect");
        const csLabel = document.getElementById("csfloat-btn-label");
        const authBanner = document.getElementById("auth-warning-banner");
        if (data.csfloat.is_connected) {
            csBtn.className = "btn-account btn-csfloat connected";
            csLabel.innerText = "🔑 CSFloat Conectado";
            if (authBanner) authBanner.style.display = "none";
        } else {
            csBtn.className = "btn-account btn-csfloat";
            csLabel.innerText = "🔑 Conectar CSFloat";
            if (authBanner) authBanner.style.display = "flex";
        }

    } catch (e) {
        console.error("Error fetching connections:", e);
    }
}

function openSteamModal() {
    const modal = document.getElementById("modal-steam");
    modal.style.display = "flex";
    loadSteamModalData();
}

function closeSteamModal() {
    document.getElementById("modal-steam").style.display = "none";
}

async function loadSteamModalData() {
    try {
        const resp = await fetch("/api/connections");
        if (!resp.ok) return;
        const data = await resp.json();
        const st = data.steam;

        const pill = document.getElementById("steam-connection-status-pill");
        const text = document.getElementById("steam-modal-status-text");
        const btnDisconnect = document.getElementById("btn-disconnect-steam");

        if (st.is_connected) {
            pill.className = "connection-status-pill connected";
            text.innerText = `Conectado: ${st.account_name || 'Steam User'} (SteamID: ${st.account_id || 'OK'})`;
            btnDisconnect.style.display = "inline-block";
            document.getElementById("steam-input-name").value = st.account_name || "";
            document.getElementById("steam-input-tradeurl").value = st.trade_url || "";
            document.getElementById("steam-input-steamid").value = st.account_id || "";
        } else {
            pill.className = "connection-status-pill";
            text.innerText = "Estado: No conectado";
            btnDisconnect.style.display = "none";
        }
    } catch (e) {
        console.error("Error loading Steam modal data:", e);
    }
}

async function handleSteamConnectSubmit(e) {
    e.preventDefault();
    const btn = document.getElementById("btn-save-steam");
    const steamId = document.getElementById("steam-input-steamid").value.trim();
    if (!steamId) {
        alert("Por favor ingresa tu SteamID64 o link de perfil de Steam");
        return;
    }

    btn.disabled = true;
    btn.innerText = "Vinculando e Importando Inventario...";

    try {
        const payload = {
            steam_id: steamId,
            account_name: document.getElementById("steam-input-name").value.trim(),
            trade_url: document.getElementById("steam-input-tradeurl").value.trim()
        };

        const resp = await fetch("/api/connections/steam", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!resp.ok) {
            const err = await resp.json();
            alert(err.detail || "Error al conectar Steam");
            return;
        }

        await fetchConnections();
        closeSteamModal();
        fetchSteamInventory(true);
    } catch (err) {
        alert("Error de conexión: " + err.message);
    } finally {
        btn.disabled = false;
        btn.innerText = "Guardar y Vincular Steam";
    }
}

async function handleSteamDisconnect() {
    if (!confirm("¿Estás seguro de desconectar tu cuenta de Steam?")) return;
    try {
        await fetch("/api/connections/steam", { method: "DELETE" });
        await fetchConnections();
        closeSteamModal();
        renderSteamInventory({ is_connected: false, items: [] });
    } catch (e) {
        console.error("Error disconnecting Steam:", e);
    }
}

function openCsfloatModal() {
    const modal = document.getElementById("modal-csfloat");
    modal.style.display = "flex";
    loadCsfloatModalData();
}

function closeCsfloatModal() {
    document.getElementById("modal-csfloat").style.display = "none";
}

async function loadCsfloatModalData() {
    try {
        const resp = await fetch("/api/connections");
        if (!resp.ok) return;
        const data = await resp.json();
        const cs = data.csfloat;

        const pill = document.getElementById("csfloat-connection-status-pill");
        const text = document.getElementById("csfloat-modal-status-text");
        const btnDisconnect = document.getElementById("btn-disconnect-csfloat");

        if (cs.is_connected) {
            pill.className = "connection-status-pill connected";
            text.innerText = "Conectado: API Key válida y activa";
            btnDisconnect.style.display = "inline-block";
        } else {
            pill.className = "connection-status-pill";
            text.innerText = "Estado: No conectado";
            btnDisconnect.style.display = "none";
        }
    } catch (e) {
        console.error("Error loading CSFloat modal data:", e);
    }
}

async function handleCsfloatConnectSubmit(e) {
    e.preventDefault();
    const btn = document.getElementById("btn-save-csfloat");
    const key = document.getElementById("csfloat-input-key").value.trim();
    if (!key) {
        alert("Por favor ingresa tu API Key de CSFloat");
        return;
    }

    btn.disabled = true;
    btn.innerText = "Validando...";

    try {
        const resp = await fetch("/api/connections/csfloat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ api_key: key })
        });

        if (!resp.ok) {
            const err = await resp.json();
            alert(err.detail || "Error al validar la API Key de CSFloat");
            return;
        }

        await fetchConnections();
        await fetchSystemStatus();
        closeCsfloatModal();
        triggerScan();
    } catch (err) {
        alert("Error al conectar CSFloat: " + err.message);
    } finally {
        btn.disabled = false;
        btn.innerText = "Validar y Conectar CSFloat";
    }
}

async function handleCsfloatDisconnect() {
    if (!confirm("¿Desconectar tu API Key de CSFloat?")) return;
    try {
        await fetch("/api/connections/csfloat", { method: "DELETE" });
        await fetchConnections();
        await fetchSystemStatus();
        closeCsfloatModal();
    } catch (e) {
        console.error("Error disconnecting CSFloat:", e);
    }
}

// ==============================================
// STEAM INVENTORY & INSTANT BUY ORDER LIQUIDATION
// ==============================================
async function fetchSteamInventory(isManual = false) {
    const tbody = document.getElementById("inventory-tbody");
    if (!tbody) return;

    if (isManual) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="7">
                    <div class="loading-state">
                        <div class="spinner"></div>
                        <p>Actualizando inventario de Steam y ordenes de compra en vivo...</p>
                    </div>
                </td>
            </tr>
        `;
    }

    try {
        const resp = await fetch("/api/steam/inventory");
        if (!resp.ok) return;
        const data = await resp.json();
        steamInventoryData = data;
        renderSteamInventory(data);
    } catch (e) {
        console.error("Error fetching Steam inventory:", e);
    }
}

function renderSteamInventory(data) {
    const tbody = document.getElementById("inventory-tbody");
    if (!tbody) return;

    const banner = document.getElementById("steam-inv-not-connected-banner");

    if (!data.is_connected) {
        if (banner) banner.style.display = "flex";
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="7">
                    <div class="empty-state">
                        <div class="empty-icon">🎮</div>
                        <h3>Cuenta de Steam no conectada</h3>
                        <p>Conecta tu SteamID64 arriba para cargar tu inventario y calcular liquidación instantánea a los Buy Limits.</p>
                    </div>
                </td>
            </tr>
        `;
        document.getElementById("inv-stat-liquidation").innerText = "$0.00";
        document.getElementById("inv-stat-total").innerText = "0";
        document.getElementById("inv-stat-marketable").innerText = "0";
        document.getElementById("inv-stat-active-bids").innerText = "0";
        document.getElementById("tab-inventory-badge").innerText = "0";
        return;
    }

    if (banner) banner.style.display = "none";

    if (data.error && (!data.items || data.items.length === 0)) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="7">
                    <div class="empty-state">
                        <div class="empty-icon">⚠️</div>
                        <h3>${escapeHtml(data.error)}</h3>
                        <p>Asegúrate de que tu inventario esté en modo Público en Steam.</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    const items = data.items || [];
    const activeBidsCount = items.filter(i => i.has_active_buy_limit).length;

    // Update KPI stats
    document.getElementById("inv-stat-liquidation").innerText = `$${(data.total_liquidation_usd || 0).toFixed(2)}`;
    document.getElementById("inv-stat-total").innerText = data.total_items || items.length;
    document.getElementById("inv-stat-marketable").innerText = data.marketable_items || items.filter(i => i.marketable).length;
    document.getElementById("inv-stat-active-bids").innerText = activeBidsCount;
    document.getElementById("tab-inventory-badge").innerText = items.length;

    if (items.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="7">
                    <div class="empty-state">
                        <div class="empty-icon">📦</div>
                        <h3>No se encontraron ítems de CS2 en este inventario</h3>
                        <p>Comprueba que tu inventario no esté vacío o en modo privado.</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    let html = "";
    items.forEach(item => {
        const bidPrice = item.highest_buy_order_usd !== null ? `$${item.highest_buy_order_usd.toFixed(2)}` : "—";
        const netPayout = item.net_payout_usd !== null ? `+$${item.net_payout_usd.toFixed(2)}` : "—";
        const totalBids = item.total_buy_orders ? item.total_buy_orders.toLocaleString() : "0";

        let stateBadge = item.marketable ? `<span class="badge-status status-ACTIVE">Comercializable</span>` : `<span class="badge-tag badge-wear">Trade-Lock</span>`;

        html += `
            <tr class="opp-row">
                <td>
                    <div class="skin-cell" style="display: flex; align-items: center; gap: 12px;">
                        ${item.icon_url ? `<img src="${item.icon_url}" alt="" style="width: 44px; height: 32px; object-fit: contain;">` : ''}
                        <div>
                            <span class="skin-name">${escapeHtml(item.market_hash_name)}</span>
                            ${item.inspect_link ? `<a href="${item.inspect_link}" class="link-external" style="font-size: 0.75rem;">Inspeccionar</a>` : ''}
                        </div>
                    </div>
                </td>
                <td><span style="font-size: 0.85rem; color: var(--text-secondary);">${escapeHtml(item.type || 'CS2 Item')}</span></td>
                <td>${stateBadge}</td>
                <td class="price-val" style="color: var(--accent-cyan); font-weight: 700;">${bidPrice}</td>
                <td class="price-val stat-emerald" style="font-weight: 700;">${netPayout}</td>
                <td class="price-val">${totalBids}</td>
                <td>
                    <div class="trade-action-btns">
                        ${item.has_active_buy_limit ? `
                            <a href="${item.steam_market_url}" target="_blank" rel="noopener noreferrer" class="btn-action-trade" style="text-decoration: none; padding: 6px 12px; font-size: 0.8rem;" title="Abre Steam Market para vender al instante a la orden de compra">
                                ⚡ Liquidar a Buy Order ↗
                            </a>
                        ` : `
                            <a href="${item.steam_market_url}" target="_blank" rel="noopener noreferrer" class="btn-secondary" style="text-decoration: none; font-size: 0.8rem;">
                                Ver en Steam ↗
                            </a>
                        `}
                    </div>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}

// ==============================================
// SYSTEM STATUS
// ==============================================
async function fetchSystemStatus() {
    try {
        const resp = await fetch("/api/status");
        if (!resp.ok) return;
        const data = await resp.json();

        // Last scan timer
        const syncText = document.getElementById("last-sync-time");
        if (data.seconds_since_last_scan !== null) {
            syncText.innerText = `${data.seconds_since_last_scan}s`;
        } else {
            syncText.innerText = "Nunca";
        }

        // Scan button spinner
        const scanBtn = document.getElementById("btn-manual-scan");
        const scanBtnText = document.getElementById("btn-scan-text");
        if (data.is_scanning) {
            scanBtn.disabled = true;
            scanBtnText.innerText = "Escaneando...";
        } else {
            scanBtn.disabled = false;
            scanBtnText.innerText = "Escanear Ahora";
        }

        // Update stats
        document.getElementById("stat-total-count").innerText = data.total_opportunities;
        document.getElementById("stat-active-count").innerText = data.active_opportunities;
        document.getElementById("tab-opps-badge").innerText = data.active_opportunities;

    } catch (e) {
        console.error("Error fetching system status:", e);
    }
}

// ==============================================
// OPPORTUNITIES
// ==============================================
async function loadOpportunities(isBackground = false) {
    const tbody = document.getElementById("opps-tbody");
    if (!isBackground && currentOpportunities.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="13">
                    <div class="loading-state">
                        <div class="spinner"></div>
                        <p>Buscando oportunidades activas...</p>
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
                    <td colspan="13">
                        <div class="loading-state">
                            <p style="color: var(--accent-rose);">Error conectando con la API.</p>
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
                <td colspan="13">
                    <div class="loading-state">
                        <p>No se encontraron oportunidades con los filtros seleccionados.</p>
                        <span style="font-size: 0.8rem; color: var(--text-muted);">Prueba reduciendo el Min ROI o haz clic en Escanear Ahora.</span>
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
        const isFav = favoriteNamesSet.has(skin.market_hash_name);

        let badgesHtml = "";
        if (skin.is_stattrak) badgesHtml += `<span class="badge-tag badge-stattrak">StatTrak™</span>`;
        if (skin.is_souvenir) badgesHtml += `<span class="badge-tag badge-souvenir">Souvenir</span>`;
        if (skin.exterior) badgesHtml += `<span class="badge-tag badge-wear">${escapeHtml(skin.exterior)}</span>`;

        const profitClass = opp.gross_profit_usd >= 0 ? "profit-val" : "text-danger";
        const netProfitClass = opp.net_profit_usd >= 0 ? "stat-purple" : "text-danger";

        rowsHtml += `
            <tr class="opp-row" onclick="openDetailModal(${opp.id})">
                <td class="th-fav">
                    <button class="btn-fav-star ${isFav ? 'is-favorite' : ''}" onclick="event.stopPropagation(); toggleFavorite('${escapeHtml(skin.market_hash_name)}')">
                        ${isFav ? '⭐' : '☆'}
                    </button>
                </td>
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
                        Detalles ➔
                    </button>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = rowsHtml;
}

// ==============================================
// FAVORITES (WATCHLIST)
// ==============================================
async function fetchFavorites() {
    try {
        const resp = await fetch("/api/favorites");
        if (!resp.ok) return;
        const data = await resp.json();
        favoriteItems = data;
        favoriteNamesSet = new Set(data.map(f => f.market_hash_name));

        document.getElementById("tab-favs-badge").innerText = data.length;
        renderFavoritesTable(data);

        // Update star states on opportunities table if visible
        if (currentOpportunities.length > 0) {
            renderOpportunitiesTable(currentOpportunities);
        }
    } catch (e) {
        console.error("Error fetching favorites:", e);
    }
}

function renderFavoritesTable(favs) {
    const tbody = document.getElementById("favs-tbody");
    if (!tbody) return;

    if (favs.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="9">
                    <div class="empty-state">
                        <div class="empty-icon">⭐</div>
                        <h3>No tienes armas favoritas agregadas</h3>
                        <p>Marca cualquier skin con la estrella ⭐ en las oportunidades o búscala arriba para monitorearla.</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    let html = "";
    favs.forEach(f => {
        const priceCS = f.latest_csfloat_price_usd !== null ? `$${f.latest_csfloat_price_usd.toFixed(2)}` : "—";
        const priceSteam = f.latest_steam_bid_usd !== null ? `$${f.latest_steam_bid_usd.toFixed(2)}` : "—";
        const grossRoi = f.latest_gross_roi_percent !== null ? `${f.latest_gross_roi_percent.toFixed(1)}%` : "—";
        const netRoi = f.latest_net_roi_percent !== null ? `${f.latest_net_roi_percent.toFixed(1)}%` : "—";
        const liq = f.liquidity_score || "—";
        const status = f.status || "UNTRACKED";

        html += `
            <tr class="opp-row">
                <td class="th-fav">
                    <button class="btn-fav-star is-favorite" onclick="toggleFavorite('${escapeHtml(f.market_hash_name)}')">⭐</button>
                </td>
                <td>
                    <div class="skin-cell">
                        <span class="skin-name">${escapeHtml(f.market_hash_name)}</span>
                        ${f.exterior ? `<span class="skin-sub"><span class="badge-tag badge-wear">${escapeHtml(f.exterior)}</span></span>` : ''}
                    </div>
                </td>
                <td class="price-val">${priceCS}</td>
                <td class="price-val">${priceSteam}</td>
                <td class="roi-val">${grossRoi}</td>
                <td class="net-roi-val">${netRoi}</td>
                <td><span class="badge-liq liq-${liq}">${liq}</span></td>
                <td><span class="badge-status status-${status}">${status}</span></td>
                <td>
                    <div class="trade-action-btns">
                        <button class="btn-secondary" onclick="triggerScan('${escapeHtml(f.market_hash_name)}')">
                            ⚡ Sondear
                        </button>
                        <button class="btn-trade-opt btn-trade-delete" onclick="removeFavoriteById(${f.id})">
                            ✕
                        </button>
                    </div>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}

async function toggleFavorite(marketHashName) {
    try {
        if (favoriteNamesSet.has(marketHashName)) {
            await fetch(`/api/favorites/by-name/${encodeURIComponent(marketHashName)}`, { method: "DELETE" });
        } else {
            await fetch("/api/favorites", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ market_hash_name: marketHashName })
            });
        }
        await fetchFavorites();
    } catch (e) {
        console.error("Error toggling favorite:", e);
    }
}

async function removeFavoriteById(id) {
    try {
        await fetch(`/api/favorites/${id}`, { method: "DELETE" });
        await fetchFavorites();
    } catch (e) {
        console.error("Error removing favorite:", e);
    }
}

async function handleAddFavoriteFromInput() {
    const input = document.getElementById("input-add-fav");
    const name = input.value.trim();
    if (!name) return;

    await toggleFavorite(name);
    input.value = "";
}

function handleModalFavToggle() {
    if (!currentSelectedOppDetail) return;
    const name = currentSelectedOppDetail.skin.market_hash_name;
    toggleFavorite(name).then(() => {
        const btn = document.getElementById("modal-btn-toggle-fav");
        const isFav = favoriteNamesSet.has(name);
        btn.className = `btn-fav-toggle ${isFav ? 'is-favorite' : ''}`;
    });
}

// ==============================================
// TRADES / PnL TRACKER & HISTORY
// ==============================================
async function fetchTrades() {
    try {
        const resp = await fetch("/api/trades");
        if (!resp.ok) return;
        const data = await resp.json();
        tradeRecords = data.trades || [];

        // Update trade summary cards
        document.getElementById("trade-stat-invested").innerText = `$${data.total_invested_usd.toFixed(2)}`;
        document.getElementById("trade-stat-realized").innerText = `${data.total_realized_profit_usd >= 0 ? '+' : ''}$${data.total_realized_profit_usd.toFixed(2)}`;
        document.getElementById("trade-stat-expected").innerText = `+$${data.total_expected_profit_usd.toFixed(2)}`;
        document.getElementById("trade-stat-roi").innerText = `${data.average_roi_percent.toFixed(1)}%`;
        document.getElementById("trade-stat-counts").innerText = `${data.total_trades} / ${data.active_trades}`;
        document.getElementById("tab-trades-badge").innerText = data.active_trades;

        renderTradesTable(tradeRecords);
    } catch (e) {
        console.error("Error fetching trades:", e);
    }
}

function renderTradesTable(trades) {
    const tbody = document.getElementById("trades-tbody");
    if (!tbody) return;

    if (trades.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="10">
                    <div class="empty-state">
                        <div class="empty-icon">📊</div>
                        <h3>No hay operaciones registradas</h3>
                        <p>Registra compras desde los detalles de una oportunidad o añade una operación manual.</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }

    let html = "";
    trades.forEach(t => {
        const dateStr = new Date(t.created_at).toLocaleDateString();
        const profitClass = t.net_profit_usd >= 0 ? "stat-emerald" : "text-danger";
        const actualSell = t.actual_sell_price_usd !== null ? `$${t.actual_sell_price_usd.toFixed(2)}` : "—";
        
        let statusClass = "badge-status-lock";
        let statusLabel = "🔒 Trade-Lock";
        if (t.status === "IN_INVENTORY") {
            statusClass = "badge-status-inventory";
            statusLabel = "📦 Inventario";
        } else if (t.status === "LISTED") {
            statusClass = "badge-status-listed";
            statusLabel = "🏷️ Listado";
        } else if (t.status === "COMPLETED") {
            statusClass = "badge-status-completed";
            statusLabel = "✅ Vendido";
        } else if (t.status === "CANCELLED") {
            statusClass = "badge-status-cancelled";
            statusLabel = "✕ Cancelado";
        }

        const lockUntil = t.trade_lock_until ? new Date(t.trade_lock_until).toLocaleDateString() : "—";

        html += `
            <tr class="opp-row">
                <td style="font-size: 0.85rem; color: var(--text-secondary);">${dateStr}</td>
                <td>
                    <div class="skin-cell">
                        <span class="skin-name">${escapeHtml(t.market_hash_name)}</span>
                        ${t.notes ? `<span class="skin-sub">${escapeHtml(t.notes)}</span>` : ''}
                    </div>
                </td>
                <td class="price-val">$${t.buy_price_usd.toFixed(2)}</td>
                <td class="price-val">$${t.target_sell_price_usd.toFixed(2)}</td>
                <td class="price-val">${actualSell}</td>
                <td class="${profitClass}">+$${t.net_profit_usd.toFixed(2)}</td>
                <td class="net-roi-val">${t.net_roi_percent.toFixed(1)}%</td>
                <td><span class="badge-trade-status ${statusClass}">${statusLabel}</span></td>
                <td style="font-size: 0.8rem; font-family: var(--font-mono);">${lockUntil}</td>
                <td>
                    <div class="trade-action-btns">
                        ${t.status !== "COMPLETED" ? `
                            <button class="btn-trade-opt" title="Marcar como vendido" onclick="markTradeCompleted(${t.id}, ${t.target_sell_price_usd})">
                                ✓ Vendido
                            </button>
                        ` : ''}
                        <button class="btn-trade-opt btn-trade-delete" title="Eliminar registro" onclick="deleteTradeRecord(${t.id})">
                            ✕
                        </button>
                    </div>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
}

async function markTradeCompleted(tradeId, targetSellPrice) {
    const priceStr = prompt("Precio final de venta en Steam ($ USD):", targetSellPrice.toFixed(2));
    if (!priceStr) return;

    const actualPrice = parseFloat(priceStr);
    if (isNaN(actualPrice) || actualPrice <= 0) return;

    try {
        await fetch(`/api/trades/${tradeId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                status: "COMPLETED",
                actual_sell_price_usd: actualPrice
            })
        });
        await fetchTrades();
    } catch (e) {
        console.error("Error updating trade:", e);
    }
}

async function deleteTradeRecord(tradeId) {
    if (!confirm("¿Eliminar este registro de operación?")) return;
    try {
        await fetch(`/api/trades/${tradeId}`, { method: "DELETE" });
        await fetchTrades();
    } catch (e) {
        console.error("Error deleting trade:", e);
    }
}

function openManualTradeModal() {
    document.getElementById("modal-manual-trade").style.display = "flex";
}

function closeManualTradeModal() {
    document.getElementById("modal-manual-trade").style.display = "none";
}

async function handleManualTradeSubmit(e) {
    e.preventDefault();
    const skinName = document.getElementById("trade-input-skin").value.trim();
    const buyPrice = parseFloat(document.getElementById("trade-input-buyprice").value);
    const sellPrice = parseFloat(document.getElementById("trade-input-sellprice").value);
    const status = document.getElementById("trade-input-status").value;
    const notes = document.getElementById("trade-input-notes").value.trim();

    if (!skinName || isNaN(buyPrice) || isNaN(sellPrice)) {
        alert("Por favor completa los campos requeridos.");
        return;
    }

    try {
        const resp = await fetch("/api/trades", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                market_hash_name: skinName,
                buy_price_usd: buyPrice,
                target_sell_price_usd: sellPrice,
                status: status,
                notes: notes
            })
        });

        if (!resp.ok) throw new Error("Error creating trade");

        closeManualTradeModal();
        await fetchTrades();
        alert("¡Operación registrada con éxito en tu portafolio!");
    } catch (err) {
        alert("Error al registrar trade: " + err.message);
    }
}

function handleRecordTradeFromModal() {
    if (!currentSelectedOppDetail) return;
    const d = currentSelectedOppDetail;

    const confirmed = confirm(`¿Registrar compra de '${d.skin.market_hash_name}'?\nPrecio Compra CSFloat: $${d.csfloat_price_usd.toFixed(2)}\nPrecio Venta Steam: $${d.steam_highest_bid_usd.toFixed(2)}\nGanancia Neta Estimada: +$${d.net_profit_usd.toFixed(2)}`);
    if (!confirmed) return;

    fetch("/api/trades", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            market_hash_name: d.skin.market_hash_name,
            buy_price_usd: d.csfloat_price_usd,
            target_sell_price_usd: d.steam_highest_bid_usd,
            status: "IN_TRADE_LOCK",
            notes: `Auto-registrado desde escáner (ROI ${d.net_roi_percent.toFixed(1)}%)`
        })
    }).then(resp => {
        if (resp.ok) {
            alert("Operación registrada en tu historial.");
            fetchTrades();
        }
    }).catch(err => {
        alert("Error: " + err.message);
    });
}

// ==============================================
// DETAIL MODAL & ORDER BOOK
// ==============================================
async function openDetailModal(opportunityId) {
    const modal = document.getElementById("detail-modal");
    modal.style.display = "flex";

    // Reset fields
    document.getElementById("modal-skin-name").innerText = "Cargando detalles...";
    document.getElementById("modal-badges").innerHTML = "";
    document.getElementById("modal-orderbook-tbody").innerHTML = `<tr><td colspan="3" class="text-center text-muted">Cargando tiers del order book...</td></tr>`;
    document.getElementById("sim-results-box").style.display = "none";

    try {
        const resp = await fetch(`/api/opportunities/${opportunityId}`);
        if (!resp.ok) throw new Error("Failed to load opportunity detail");
        const data = await resp.json();
        currentSelectedOppDetail = data;

        // Title & Badges
        document.getElementById("modal-skin-name").innerText = data.skin.market_hash_name;
        
        // Favorite toggle state
        const isFav = favoriteNamesSet.has(data.skin.market_hash_name);
        const favBtn = document.getElementById("modal-btn-toggle-fav");
        favBtn.className = `btn-fav-toggle ${isFav ? 'is-favorite' : ''}`;

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
            inspectWrap.innerHTML = `<a href="${data.csfloat_listing.inspect_link}" class="link-external">Inspeccionar en Juego</a>`;
        } else {
            inspectWrap.innerHTML = `<span class="text-muted">Ninguno</span>`;
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
                        <td>${tier.quantity} órdenes</td>
                        <td class="stat-purple">$${tier.net_payout_usd.toFixed(2)}</td>
                    </tr>
                `;
            });
            obTbody.innerHTML = obHtml;
        } else {
            obTbody.innerHTML = `<tr><td colspan="3" class="text-center text-muted">Sin datos de order book en vivo</td></tr>`;
        }

        // Auto-run simulation for default qty 5
        runSimulation();

    } catch (e) {
        console.error("Error opening detail modal:", e);
    }
}

async function runSimulation() {
    if (!currentSelectedOppDetail) return;

    const qtyInput = document.getElementById("sim-quantity-input");
    const qty = parseInt(qtyInput.value, 10) || 1;

    try {
        const resp = await fetch(`/api/opportunities/${currentSelectedOppDetail.id}/simulate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ quantity: qty })
        });

        if (!resp.ok) throw new Error("Simulation failed");
        const sim = await resp.json();

        const resBox = document.getElementById("sim-results-box");
        resBox.style.display = "flex";

        document.getElementById("sim-fulfilled-qty").innerText = `${sim.fulfilled_quantity} / ${sim.target_quantity} unidades`;
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
    currentSelectedOppDetail = null;
}

// ==============================================
// SCAN & UTILITIES
// ==============================================
async function triggerScan(skinName = null) {
    const scanBtn = document.getElementById("btn-manual-scan");
    const scanBtnText = document.getElementById("btn-scan-text");
    scanBtn.disabled = true;
    scanBtnText.innerText = "Escaneando...";

    try {
        let url = "/api/scan";
        if (skinName) {
            url += `?market_hash_name=${encodeURIComponent(skinName)}`;
        }
        const resp = await fetch(url, { method: "POST" });
        await resp.json();
        await fetchSystemStatus();
        await loadOpportunities();
        await fetchFavorites();
        if (steamInventoryData && steamInventoryData.is_connected) {
            fetchSteamInventory();
        }
    } catch (e) {
        console.error("Scan error:", e);
    } finally {
        scanBtn.disabled = false;
        scanBtnText.innerText = "Escanear Ahora";
    }
}

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
