"""
CS2 Arbitrage Terminal — Application Runner with Full Terminal Logging
Execute this script with:
    python run.py

All terminal outputs, requests, scans, and error logs are automatically
written into a timestamped .txt file in the logs/ directory until Ctrl+C.
"""
import sys
import uvicorn

if __name__ == "__main__":
    try:
        uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
    except KeyboardInterrupt:
        print("\n🛑 Servidor detenido por el usuario (Ctrl + C).")
        sys.exit(0)
