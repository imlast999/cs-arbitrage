import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db, SessionLocal
from app.models.schema import UserConnection, Opportunity, Skin, CSFloatListing, SteamOrderBook
from app.api.routes import router as api_router
from app.services.scanner_service import scanner_service
from app.services.http_client import http_client
from app.services.csfloat_client import csfloat_client
from app.services.matching_service import matching_service
from app.services.catalog_service import PROVEN_PROFITABLE_SKINS
from app.logger_config import setup_terminal_logging, close_terminal_logging
import json

# Configure logging with both terminal output and continuous .txt file writing
setup_terminal_logging(settings.LOG_LEVEL)
logger = logging.getLogger("scanner.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing CS2 Arbitrage Scanner database...")
    init_db()

    # Clean up non-weapon / negative profit opportunities from previous runs
    try:
        db_cleanup = SessionLocal()
        db_cleanup.query(Opportunity).filter(Opportunity.net_profit_usd <= 0).delete()
        db_cleanup.commit()
        db_cleanup.close()
    except Exception:
        pass

    # Auto-sync CSFloat and Steam profile if API Key is configured in .env
    if csfloat_client.has_api_key():
        try:
            db = SessionLocal()
            profile = await csfloat_client.fetch_user_profile()
            if profile.get("success"):
                conn = db.query(UserConnection).filter(UserConnection.provider == "csfloat").first()
                if not conn:
                    conn = UserConnection(provider="csfloat")
                    db.add(conn)
                conn.is_connected = True
                conn.api_key = settings.CSFLOAT_API_KEY
                conn.account_name = profile.get("username") or "CSFloat User"
                conn.balance_usd = profile.get("balance_usd", 0.0)
                conn.trade_url = profile.get("trade_url")
                conn.meta_json = json.dumps(profile.get("raw", {}))

                if profile.get("steam_id64"):
                    st_conn = db.query(UserConnection).filter(UserConnection.provider == "steam").first()
                    if not st_conn:
                        st_conn = UserConnection(provider="steam")
                        db.add(st_conn)
                    st_conn.is_connected = True
                    st_conn.account_id = profile["steam_id64"]
                    if not st_conn.account_name or st_conn.account_name == "Steam User":
                        st_conn.account_name = profile.get("username")
                    if profile.get("trade_url") and not st_conn.trade_url:
                        st_conn.trade_url = profile.get("trade_url")

                db.commit()
                logger.info(f"✅ CSFloat conectado automáticamente como '{conn.account_name}' (Saldo: ${conn.balance_usd:.2f})")
            db.close()
        except Exception as e:
            logger.warning(f"No se pudo sincronizar perfil de CSFloat en inicio: {e}")

    logger.info("⚡ Modo de escaneo bajo demanda activo: se escaneará cuando el usuario pulse 'Escanear Ahora' para proteger los límites de la API.")
    yield
    # Shutdown (Ctrl+C / Termination)
    logger.info("Shutting down scanner...")
    await scanner_service.stop_background_loop()
    await http_client.close()
    close_terminal_logging()

app = FastAPI(
    title="CS2 Arbitrage Scanner",
    description="Real-time arbitrage scanner between CSFloat lowest asks and Steam Community Market highest buy orders.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router)

# Mount Static frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
