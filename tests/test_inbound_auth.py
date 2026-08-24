"""Inbound auth, bind policy, and optional rate limit (no live xAI calls)."""

from __future__ import annotations

import logging
import unittest
import warnings

warnings.filterwarnings(
    "ignore",
    message=r"Using `httpx` with `starlette.testclient` is deprecated",
)

from starlette.testclient import TestClient

from grok_a2a.agent import GrokAgent
from grok_a2a.auth import (
    assert_inbound_auth_allowed,
    bearer_from_authorization,
    is_loopback_host,
    is_loopback_url,
    tokens_match,
)
from grok_a2a.server import create_app

TOKEN = "test-inbound-token"
logging.getLogger("a2a").setLevel(logging.CRITICAL)


def _app(**kwargs):
    kwargs.setdefault("host", "127.0.0.1")
    kwargs.setdefault("public_url", "http://127.0.0.1:9999")
    kwargs.setdefault("agent", GrokAgent(dry_run=True))
    kwargs.setdefault("inbound_token", "")
    kwargs.setdefault("rate_limit", 0)
    return create_app(**kwargs)


def _client(app) -> TestClient:
    return TestClient(app)


class LoopbackTests(unittest.TestCase):
    def test_loopback_hosts(self) -> None:
        for host in ("127.0.0.1", "127.0.0.2", "localhost", "::1", "[::1]"):
            self.assertTrue(is_loopback_host(host), host)
        for host in (
            "0.0.0.0",
            "::",
            "192.168.1.9",
            "example.com",
            "127.evil.com",
            "127.0.0.1.nip.io",
        ):
            self.assertFalse(is_loopback_host(host), host)

    def test_loopback_urls(self) -> None:
        self.assertTrue(is_loopback_url("http://127.0.0.1:9999"))
        self.assertTrue(is_loopback_url("http://localhost:9999/"))
        self.assertFalse(is_loopback_url("https://example.com"))
        self.assertFalse(is_loopback_url("http://0.0.0.0:9999"))
        self.assertFalse(is_loopback_url("http://127.0.0.1.example.com"))
        self.assertFalse(is_loopback_url("http://127.evil.com"))


class BindPolicyTests(unittest.TestCase):
    def test_loopback_without_token_ok(self) -> None:
        assert_inbound_auth_allowed(
            host="127.0.0.1",
            public_url="http://127.0.0.1:9999",
            token="",
        )

    def test_non_loopback_host_without_token_refused(self) -> None:
        with self.assertRaises(RuntimeError) as ctx:
            assert_inbound_auth_allowed(
                host="0.0.0.0",
                public_url="http://127.0.0.1:9999",
                token="",
            )
        self.assertIn("GROK_A2A_TOKEN", str(ctx.exception))

    def test_public_url_without_token_refused(self) -> None:
        with self.assertRaises(RuntimeError) as ctx:
            assert_inbound_auth_allowed(
                host="127.0.0.1",
                public_url="https://agents.example.com",
                token="",
            )
        self.assertIn("PUBLIC_URL", str(ctx.exception))

    def test_127_prefix_hostname_is_not_loopback(self) -> None:
        with self.assertRaises(RuntimeError) as ctx:
            assert_inbound_auth_allowed(
                host="127.0.0.1",
                public_url="http://127.evil.com",
                token="",
            )
        self.assertIn("PUBLIC_URL", str(ctx.exception))

    def test_exposed_with_token_ok(self) -> None:
        assert_inbound_auth_allowed(
            host="0.0.0.0",
            public_url="https://agents.example.com",
            token=TOKEN,
        )

    def test_create_app_refuses_public_url_without_token(self) -> None:
        with self.assertRaises(RuntimeError):
            _app(public_url="https://agents.example.com", inbound_token="")


class TokenHelperTests(unittest.TestCase):
    def test_bearer_parse(self) -> None:
        self.assertEqual(bearer_from_authorization("Bearer abc"), "abc")
        self.assertEqual(bearer_from_authorization("bearer abc"), "abc")
        self.assertIsNone(bearer_from_authorization(None))
        self.assertIsNone(bearer_from_authorization("Basic abc"))
        self.assertIsNone(bearer_from_authorization("Bearer"))

    def test_tokens_match(self) -> None:
        self.assertTrue(tokens_match("abc", "abc"))
        self.assertFalse(tokens_match("abc", "abd"))
        self.assertFalse(tokens_match("ab", "abc"))


class MiddlewareTests(unittest.TestCase):
    def test_no_token_jsonrpc_open_on_loopback(self) -> None:
        with _client(_app(inbound_token="")) as client:
            resp = client.post("/", json={"jsonrpc": "2.0", "id": 1, "method": "x"})
            self.assertNotEqual(resp.status_code, 401)

    def test_token_required_on_jsonrpc(self) -> None:
        with _client(_app(inbound_token=TOKEN)) as client:
            missing = client.post("/", json={"jsonrpc": "2.0", "id": 1, "method": "x"})
            self.assertEqual(missing.status_code, 401)
            self.assertEqual(missing.headers.get("www-authenticate"), 'Bearer realm="grok-a2a"')

            wrong = client.post(
                "/",
                json={"jsonrpc": "2.0", "id": 1, "method": "x"},
                headers={"Authorization": "Bearer wrong-token-value"},
            )
            self.assertEqual(wrong.status_code, 401)

            ok = client.post(
                "/",
                json={"jsonrpc": "2.0", "id": 1, "method": "x"},
                headers={"Authorization": f"Bearer {TOKEN}"},
            )
            self.assertNotEqual(ok.status_code, 401)

    def test_agent_card_stays_public(self) -> None:
        with _client(_app(inbound_token=TOKEN)) as client:
            resp = client.get("/.well-known/agent-card.json")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertIn("securitySchemes", data)
            self.assertIn("bearer", data["securitySchemes"])

    def test_agent_card_omits_security_when_no_token(self) -> None:
        with _client(_app(inbound_token="")) as client:
            resp = client.get("/.well-known/agent-card.json")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertFalse(data.get("securitySchemes"))

    def test_rate_limit(self) -> None:
        with _client(_app(inbound_token="", rate_limit=2)) as client:
            r1 = client.post("/", json={"jsonrpc": "2.0", "id": 1, "method": "x"})
            r2 = client.post("/", json={"jsonrpc": "2.0", "id": 2, "method": "x"})
            r3 = client.post("/", json={"jsonrpc": "2.0", "id": 3, "method": "x"})
            self.assertNotEqual(r1.status_code, 429)
            self.assertNotEqual(r2.status_code, 429)
            self.assertEqual(r3.status_code, 429)
            self.assertIn("Retry-After", r3.headers)
            card = client.get("/.well-known/agent-card.json")
            self.assertEqual(card.status_code, 200)

    def test_non_loopback_with_token_builds(self) -> None:
        app = _app(host="0.0.0.0", public_url="http://0.0.0.0:9999", inbound_token=TOKEN)
        with _client(app) as client:
            self.assertEqual(client.get("/.well-known/agent-card.json").status_code, 200)


if __name__ == "__main__":
    unittest.main()
