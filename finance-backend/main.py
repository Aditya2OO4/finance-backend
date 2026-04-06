"""
main.py — top-level entry point
Run with: python main.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.server import create_app

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))

    print(f"\n{'='*50}")
    print(f"  Finance Backend API")
    print(f"  Running on http://{host}:{port}")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*50}\n")

    server = create_app(host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()
