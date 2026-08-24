# grok-a2a

**Unofficial** [A2A (Agent2Agent)](https://a2a-protocol.org/latest/) wrapper for [xAI Grok](https://docs.x.ai/).

This is a **community adapter** maintained by [Estes Advisory](https://github.com/estesadvisory).  
It is **not** an official xAI product, and is **not affiliated with or endorsed by xAI**.

Expose Grok as an A2A agent so other agents can discover an Agent Card and hand off text tasks over JSON-RPC.

## What you get

| Piece | Detail |
|-------|--------|
| Agent Card | `GET /.well-known/agent-card.json` |
| Task handler | A2A JSON-RPC → xAI Chat Completions API |
| Cancel | `CancelTask` marks the task cancelled and aborts an in-flight xAI HTTP request when one is running |
| Auth | Operator’s own `XAI_API_KEY` (env / `.env`). Inbound A2A uses optional `GROK_A2A_TOKEN`. |
| Dry-run | `GROK_A2A_DRY_RUN=1` for local smoke without calling xAI |

**Not in v0.1:** streaming, official xAI branding.

Inbound auth is **required before any non-localhost bind** (or a non-loopback `PUBLIC_URL`). Loopback (`127.0.0.1`) may omit the token. Set `GROK_A2A_TOKEN` and send `Authorization: Bearer …` on JSON-RPC once you expose the port.

## Quick start

Requires Python 3.10+.

```bash
git clone https://github.com/estesadvisory/grok-a2a.git
cd grok-a2a
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .

cp .env.example .env
# Edit .env and set XAI_API_KEY from https://console.x.ai/

python -m grok_a2a
```

Agent Card:

```bash
curl -s http://127.0.0.1:9999/.well-known/agent-card.json | python -m json.tool
```

Dry-run (no API key):

```bash
GROK_A2A_DRY_RUN=1 python -m grok_a2a
# other terminal:
python scripts/smoke_client.py --text "ping"
```

Non-loopback bind (requires inbound token):

```bash
export GROK_A2A_TOKEN=your-shared-token
HOST=0.0.0.0 PUBLIC_URL=http://0.0.0.0:9999 python -m grok_a2a
# other terminal (same token value):
python scripts/smoke_client.py --text "ping" --token "$GROK_A2A_TOKEN"
```

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `XAI_API_KEY` | _(required unless dry-run)_ | xAI API key |
| `XAI_API_BASE` | `https://api.x.ai/v1` | API base |
| `GROK_MODEL` | `grok-4-1-fast-reasoning` | Model id |
| `HOST` / `PORT` | `127.0.0.1` / `9999` | Bind address. Non-loopback HOST requires `GROK_A2A_TOKEN`. |
| `PUBLIC_URL` | `http://127.0.0.1:9999` | URL advertised on the Agent Card. Non-loopback URL requires `GROK_A2A_TOKEN`. |
| `GROK_A2A_TOKEN` | _(empty)_ | Shared inbound Bearer token. Required on JSON-RPC when set. Agent Card stays public. |
| `GROK_A2A_RATE_LIMIT` | `0` | Optional JSON-RPC requests per client IP per 60s (`0` = off). |
| `GROK_A2A_DRY_RUN` | `0` | `1` = fake replies, no xAI call |

Never commit `.env` or API keys.

## License

Apache-2.0. See [LICENSE](./LICENSE).

Grok® / xAI® are trademarks of their respective owners. This project only uses the public xAI API under your own credentials.
