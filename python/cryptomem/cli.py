from __future__ import annotations

import argparse

from cryptomem import __version__


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``cryptomem`` command."""
    parser = argparse.ArgumentParser(prog="cryptomem", description="cryptomem CLI")
    parser.add_argument("--version", action="version", version=f"cryptomem {__version__}")
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="run the Ollama-compatible sidecar")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8088)
    serve.add_argument("--ollama-url", default="http://localhost:11434")

    args = parser.parse_args(argv)

    if args.command == "serve":
        try:
            import uvicorn

            from cryptomem.server.app import create_app
        except ImportError:
            print("The sidecar needs the 'serve' extra: pip install 'cryptomem[serve]'")
            return 1
        app = create_app(ollama_url=args.ollama_url)
        uvicorn.run(app, host=args.host, port=args.port)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
