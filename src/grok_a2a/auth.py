"""Inbound shared-token auth and bind policy for the A2A door.

Anyone who can reach this process can spend the operator's XAI_API_KEY.
Loopback binds may omit a token. Any non-loopback HOST or PUBLIC_URL
requires GROK_A2A_TOKEN, and that token is then required on inbound
JSON-RPC (Agent Card stays public so clients can discover the scheme).
"""

from __future__ import annotations

import hmac
import os
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "0:0:0:0:0:0:0:1"})


def _unauthorized() -> JSONResponse:
    return JSONResponse(
        {"error": "unauthorized"},
        status_code=401,
        headers={"WWW-Authenticate": 'Bearer realm="grok-a2a"'},
    )


def inbound_token_from_env() -> str:
    return os.getenv("GROK_A2A_TOKEN", "").strip()


def rate_limit_from_env() -> int:
    raw = os.getenv("GROK_A2A_RATE_LIMIT", "0").strip() or "0"
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(
            "GROK_A2A_RATE_LIMIT must be a non-negative integer "
            "(requests per minute; 0 disables)."
        ) from exc
    if value < 0:
        raise RuntimeError("GROK_A2A_RATE_LIMIT must be >= 0.")
    return value


def normalize_host(host: str) -> str:
    h = host.strip().lower()
    if h.startswith("[") and h.endswith("]"):
        h = h[1:-1]
    if "%" in h:
        h = h.split("%", 1)[0]
    return h


def is_loopback_host(host: str) -> bool:
    h = normalize_host(host)
    if not h:
        return False
    if h in LOOPBACK_HOSTS:
        return True
    return h.startswith("127.")


def is_loopback_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return is_loopback_host(host)


def exposure_reasons(*, host: str | None, public_url: str) -> list[str]:
    reasons: list[str] = []
    if host is not None and not is_loopback_host(host):
        reasons.append(f"HOST={host}")
    if not is_loopback_url(public_url):
        reasons.append(f"PUBLIC_URL={public_url}")
    return reasons


def assert_inbound_auth_allowed(
    *,
    host: str | None,
    public_url: str,
    token: str,
) -> None:
    """Refuse to start if the door is reachable beyond loopback without a token."""
    reasons = exposure_reasons(host=host, public_url=public_url)
    if reasons and not token:
        joined = ", ".join(reasons)
        raise RuntimeError(
            "Refusing to start without GROK_A2A_TOKEN "
            f"({joined}). Anyone who can reach this adapter can spend "
            "the operator's XAI_API_KEY. Bind 127.0.0.1 with a loopback "
            "PUBLIC_URL, or set a shared inbound Bearer token."
        )


def bearer_from_authorization(header: str | None) -> str | None:
    if not header:
        return None
    scheme, _, rest = header.partition(" ")
    if scheme.lower() != "bearer" or not rest.strip():
        return None
    return rest.strip()


def tokens_match(provided: str, expected: str) -> bool:
    left = provided.encode("utf-8")
    right = expected.encode("utf-8")
    if len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def is_public_path(path: str) -> bool:
    return path.rstrip("/") == AGENT_CARD_WELL_KNOWN_PATH.rstrip("/") or path == AGENT_CARD_WELL_KNOWN_PATH


class InboundAuthMiddleware(BaseHTTPMiddleware):
    """Require Authorization: Bearer when a shared inbound token is configured."""

    def __init__(self, app, token: str = "") -> None:
        super().__init__(app)
        self.token = token.strip()

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.token or is_public_path(request.url.path):
            return await call_next(request)
        provided = bearer_from_authorization(request.headers.get("authorization"))
        if provided is None or not tokens_match(provided, self.token):
            return _unauthorized()
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple per-client-IP sliding window on the JSON-RPC door (not the Agent Card)."""

    def __init__(self, app, *, limit: int, window_s: float = 60.0) -> None:
        super().__init__(app)
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _client_key(self, request: Request) -> str:
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    async def dispatch(self, request: Request, call_next) -> Response:
        if self.limit <= 0 or is_public_path(request.url.path):
            return await call_next(request)
        key = self._client_key(request)
        now = time.monotonic()
        bucket = self._hits[key]
        cutoff = now - self.window_s
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= self.limit:
            retry = max(1, int(self.window_s - (now - bucket[0])))
            return JSONResponse(
                {"error": "rate_limited"},
                status_code=429,
                headers={"Retry-After": str(retry)},
            )
        bucket.append(now)
        return await call_next(request)
