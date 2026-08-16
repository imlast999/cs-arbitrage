import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db
from app.api.routes import router as api_router
from app.services.scanner_service import scanner_service
from app.services.http_client import http_client

from app.logger_config import setup_terminal_logging, close_terminal_logging

# Configure logging with both terminal output and continuous .txt file writing
setup_terminal_logging(settings.LOG_LEVEL)
logger = logging.getLogger("scanner.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing CS2 Arbitrage Scanner database...")
    init_db()
    logger.info("Starting background market scanner loop...")
    await scanner_service.start_background_loop()
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
