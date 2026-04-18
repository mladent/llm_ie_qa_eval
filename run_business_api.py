from __future__ import annotations

import argparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the business-evaluation API server (optional FastAPI runtime)."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host for API server.")
    parser.add_argument("--port", type=int, default=8000, help="Bind port for API server.")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        import uvicorn  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        raise ImportError(
            "uvicorn is not installed. Install optional deps to run API server."
        ) from exc

    uvicorn.run(
        "business.api:create_fastapi_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,
    )


if __name__ == "__main__":
    main()
