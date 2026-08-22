"""CLI entry: python -m grok_a2a"""

from __future__ import annotations

import os

import uvicorn
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "9999"))
    # Import after dotenv so GrokAgent sees env.
    from grok_a2a.server import create_app

    app = create_app()
    print(
        f"grok-a2a listening on http://{host}:{port} "
        f"(Agent Card: http://{host}:{port}/.well-known/agent-card.json)"
    )
    print("Unofficial community adapter — not affiliated with xAI.")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
