"""Grok-backed agent that calls the xAI Chat Completions API."""

from __future__ import annotations

import os
from typing import Any

import httpx


class GrokAgent:
    """Thin client for xAI Grok chat completions."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_base: str | None = None,
        model: str | None = None,
        dry_run: bool | None = None,
        system_prompt: str | None = None,
        timeout_s: float = 120.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("XAI_API_KEY", "").strip()
        self.api_base = (api_base or os.getenv("XAI_API_BASE", "https://api.x.ai/v1")).rstrip("/")
        self.model = model or os.getenv("GROK_MODEL", "grok-4-1-fast-reasoning")
        if dry_run is None:
            dry_run = os.getenv("GROK_A2A_DRY_RUN", "0").strip() in {"1", "true", "TRUE", "yes"}
        self.dry_run = dry_run
        self.system_prompt = system_prompt or (
            "You are Grok, reached via an unofficial community A2A (Agent2Agent) adapter. "
            "Be concise and useful. Do not claim to be an official xAI A2A product."
        )
        self.timeout_s = timeout_s

    async def invoke(self, user_request: str) -> str:
        text = (user_request or "").strip()
        if not text:
            return "No text input was provided."

        if self.dry_run:
            return f"[dry-run] Grok A2A would answer: {text}"

        if not self.api_key:
            raise RuntimeError(
                "XAI_API_KEY is not set. Export it or copy .env.example → .env. "
                "For local smoke without an API call, set GROK_A2A_DRY_RUN=1."
            )

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0.4,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.api_base}/chat/completions"

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            resp = await client.post(url, headers=headers, json=payload)
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                detail = resp.text[:500]
                raise RuntimeError(
                    f"xAI API error {resp.status_code}: {detail}"
                ) from exc
            data = resp.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected xAI response shape: {data!r}") from exc

        if isinstance(content, list):
            # Some providers return content parts; join text bits.
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif isinstance(item, str):
                    parts.append(item)
            content = "".join(parts)

        return str(content).strip() or "(empty model response)"
