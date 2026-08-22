"""Starlette A2A server: Agent Card + JSON-RPC task handler."""

from __future__ import annotations

import os

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from starlette.applications import Starlette

from grok_a2a.agent import GrokAgent
from grok_a2a.executor import GrokAgentExecutor


def build_agent_card(*, public_url: str) -> AgentCard:
    skill = AgentSkill(
        id="grok_chat",
        name="Grok Chat",
        description=(
            "Send a natural-language message and receive a Grok reply "
            "(via unofficial community A2A adapter using the xAI API)."
        ),
        input_modes=["text/plain"],
        output_modes=["text/plain"],
        tags=["grok", "xai", "a2a", "unofficial"],
        examples=["Summarize A2A in one paragraph", "What is xAI Grok good at?"],
    )
    return AgentCard(
        name="Grok (unofficial A2A)",
        description=(
            "Community A2A wrapper for xAI Grok. Unofficial — not affiliated with "
            "or endorsed by xAI. Requires the operator's own XAI_API_KEY."
        ),
        version="0.1.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(streaming=False, extended_agent_card=False),
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                url=public_url.rstrip("/"),
                protocol_version="1.0",
            )
        ],
        skills=[skill],
    )


def create_app(
    *,
    public_url: str | None = None,
    agent: GrokAgent | None = None,
) -> Starlette:
    public_url = public_url or os.getenv("PUBLIC_URL", "http://127.0.0.1:9999")
    card = build_agent_card(public_url=public_url)
    handler = DefaultRequestHandler(
        agent_executor=GrokAgentExecutor(agent=agent or GrokAgent()),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    routes = []
    routes.extend(create_agent_card_routes(card))
    routes.extend(create_jsonrpc_routes(handler, "/"))
    return Starlette(routes=routes)
