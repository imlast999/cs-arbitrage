"""
CS2 Arbitrage Scanner — Application Runner
Execute this script with:
    python run.py
    or
    python run.py --port 8000 --host 127.0.0.1
"""
import sys
import socket
import argparse
import uvicorn
from app.config import settings

def is_port_available(host: str, port: int) -> bool:
    """Check if a host:port combination is available for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False

def find_available_port(host: str, start_port: int = 8000, max_attempts: int = 20) -> int:
    """Finds the first available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(host, port):
            return port
    return start_port

def main():
    parser = argparse.ArgumentParser(description="Run the CS2 Arbitrage Scanner web server.")
    parser.add_argument("--host", default="127.0.0.1", help="Host IP to bind to (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")
    args = parser.parse_args()

    host = args.host
    port = args.port

    # Verify port availability
    if not is_port_available(host, port):
        print(f"⚠️  El puerto {port} está ocupado o bloqueado en {host}.")
        fallback_port = find_available_port(host, start_port=port + 1)
        print(f"🔄 Usando puerto alternativo disponible: {fallback_port}")
        port = fallback_port

    print("\n" + "=" * 60)
    print(" 🚀 CS2 ARBITRAGE SCANNER ")
    print(f" 🌐 Servidor iniciado en: http://{host}:{port}")
    print(f" 📖 Documentación API en: http://{host}:{port}/docs")
    print(f" 🛑 Presiona Ctrl + C para detener el servidor")
    print("=" * 60 + "\n")

    try:
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=not args.no_reload
        )
    except KeyboardInterrupt:
        print("\n🛑 Servidor detenido por el usuario (Ctrl + C).")
        sys.exit(0)
    except OSError as err:
        if err.errno == 10013:
            print("\n❌ Error [WinError 10013]: Permisos de socket denegados en Windows.")
            print("👉 Causa habitual: El puerto está siendo usado por otro proceso o está en el rango reservado de Windows.")
            print(f"👉 Prueba ejecutando con otro puerto: python run.py --port 8080")
        else:
            print(f"\n❌ Error al iniciar servidor: {err}")
        sys.exit(1)

if __name__ == "__main__":
    main()
