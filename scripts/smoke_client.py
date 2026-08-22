#!/usr/bin/env python3
"""Minimal A2A client smoke: resolve Agent Card, send one message."""

from __future__ import annotations

import argparse
import asyncio
import sys

import httpx
from a2a.client import A2ACardResolver, create_client
from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest
from google.protobuf.json_format import MessageToDict


async def run(agent_url: str, text: str) -> int:
    async with httpx.AsyncClient(timeout=60.0) as httpx_client:
        card = await A2ACardResolver(httpx_client, agent_url).get_agent_card()
        print(f"Agent: {card.name} v{card.version}")
        print(f"Skills: {[s.name for s in card.skills]}")

    client = await create_client(agent_url)
    try:
        msg = new_text_message(text)
        msg.role = Role.ROLE_USER
        req = SendMessageRequest(message=msg)

        async for event in client.send_message(req):
            data = MessageToDict(event)
            task = data.get("task") or {}
            state = (task.get("status") or {}).get("state")
            arts = task.get("artifacts") or []
            if arts:
                parts = arts[0].get("parts") or []
                reply = parts[0].get("text") if parts else None
                if reply:
                    print(f"State: {state}")
                    print(f"Reply: {reply}")
                    return 0
            print(f"Event: {data}")
    finally:
        await client.close()

    print("No artifact reply", file=sys.stderr)
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test grok-a2a")
    parser.add_argument("--agent", default="http://127.0.0.1:9999")
    parser.add_argument("--text", default="Say hello in one short sentence.")
    args = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(run(args.agent, args.text)))
    except Exception as exc:  # noqa: BLE001
        print(f"smoke_client failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
