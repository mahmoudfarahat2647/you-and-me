"""Executable entrypoint for the local backend server."""
import argparse
import sys
import uvicorn
from src.adapters.api.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Video Studio Local Backend")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--db-path", default=None, help="Path to SQLite database file")
    args = parser.parse_args()

    app = create_app(db_path=args.db_path)

    print(f"Starting backend on http://{args.host}:{args.port}", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
