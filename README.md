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
| Auth | Operator’s own `XAI_API_KEY` (env / `.env`) |
| Dry-run | `GROK_A2A_DRY_RUN=1` for local smoke without calling xAI |

**Not in v0.1:** streaming, inbound client auth, task cancel, official xAI branding.

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

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `XAI_API_KEY` | _(required unless dry-run)_ | xAI API key |
| `XAI_API_BASE` | `https://api.x.ai/v1` | API base |
| `GROK_MODEL` | `grok-4-1-fast-reasoning` | Model id |
| `HOST` / `PORT` | `127.0.0.1` / `9999` | Bind address |
| `PUBLIC_URL` | `http://127.0.0.1:9999` | URL advertised on the Agent Card |
| `GROK_A2A_DRY_RUN` | `0` | `1` = fake replies, no xAI call |

Never commit `.env` or API keys.

## License

Apache-2.0. See [LICENSE](./LICENSE).

Grok® / xAI® are trademarks of their respective owners. This project only uses the public xAI API under your own credentials.
