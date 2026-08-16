import logging
import os
import sys
from datetime import datetime

# Root workspace logs directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# Generate timestamped session log file and pointer to latest
SESSION_TIMESTAMP = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
SESSION_LOG_FILE = os.path.join(LOGS_DIR, f"terminal_log_{SESSION_TIMESTAMP}.txt")
LATEST_LOG_FILE = os.path.join(LOGS_DIR, "latest_log.txt")

_logging_initialized = False

def get_current_log_file() -> str:
    return SESSION_LOG_FILE

def setup_terminal_logging(log_level: str = "INFO"):
    """
    Configures Python logging to simultaneously stream to the terminal (stdout)
    and continuously append all logs to a timestamped .txt file inside logs/
    until the application is terminated (Ctrl + C).
    """
    global _logging_initialized
    if _logging_initialized:
        return

    level = getattr(logging, log_level.upper(), logging.INFO)
    log_format = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)

    # 1. Console Stream Handler (Terminal Output)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    # 2. Session .txt File Handler (Appends for the entire duration of the run)
    session_file_handler = logging.FileHandler(SESSION_LOG_FILE, mode="a", encoding="utf-8")
    session_file_handler.setLevel(level)
    session_file_handler.setFormatter(formatter)

    # 3. Latest .txt File Handler (Convenient pointer to the most recent run)
    latest_file_handler = logging.FileHandler(LATEST_LOG_FILE, mode="w", encoding="utf-8")
    latest_file_handler.setLevel(level)
    latest_file_handler.setFormatter(formatter)

    # Root Logger Configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(session_file_handler)
    root_logger.addHandler(latest_file_handler)

    # Also redirect standard uvicorn and httpx loggers to the .txt file
    for lib_name in ("uvicorn", "uvicorn.access", "uvicorn.error", "httpx", "sqlalchemy.engine"):
        lib_logger = logging.getLogger(lib_name)
        lib_logger.setLevel(level)
        if session_file_handler not in lib_logger.handlers:
            lib_logger.addHandler(session_file_handler)
        if latest_file_handler not in lib_logger.handlers:
            lib_logger.addHandler(latest_file_handler)

    _logging_initialized = True

    root_logger.info("=" * 70)
    root_logger.info(f"🚀 INICIO DE SESIÓN DE TERMINAL — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    root_logger.info(f"📁 Guardando todos los logs en: {SESSION_LOG_FILE}")
    root_logger.info("=" * 70)

def close_terminal_logging():
    """Flushes and adds clean footer to log file upon termination."""
    root_logger = logging.getLogger()
    root_logger.info("=" * 70)
    root_logger.info(f"🛑 FIN DE SESIÓN (Ctrl+C / Shutdown) — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    root_logger.info(f"📄 Archivo de log guardado exitosamente: {SESSION_LOG_FILE}")
    root_logger.info("=" * 70)
    for handler in root_logger.handlers:
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
