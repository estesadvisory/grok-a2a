"""CLI entry: python -m grok_a2a"""

from __future__ import annotations

import os
import sys

import uvicorn
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "9999"))
    public_url = os.getenv("PUBLIC_URL", f"http://127.0.0.1:{port}")
    # Import after dotenv so GrokAgent / auth see env.
    from grok_a2a.auth import inbound_token_from_env, rate_limit_from_env
    from grok_a2a.server import create_app

    token = inbound_token_from_env()
    try:
        app = create_app(public_url=public_url, inbound_token=token, host=host)
    except RuntimeError as exc:
        print(f"grok-a2a: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    print(
        f"grok-a2a listening on http://{host}:{port} "
        f"(Agent Card: http://{host}:{port}/.well-known/agent-card.json)"
    )
    if token:
        print("Inbound auth: Bearer token required on JSON-RPC (GROK_A2A_TOKEN).")
    else:
        print("Inbound auth: off (loopback only). Set GROK_A2A_TOKEN before any public bind.")
    limit = rate_limit_from_env()
    if limit:
        print(f"Inbound rate limit: {limit} requests / 60s per client IP.")
    print("Unofficial community adapter — not affiliated with xAI.")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
