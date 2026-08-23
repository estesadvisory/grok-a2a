# Agent instructions (grok-a2a)

This repository is the **local source of truth** for grok-a2a work in the Grok CLI.
Web UI Grok Projects do **not** sync here. Continuity is: **disk + this file** (+ Memory MCP when used).

- **Local path:** `~/repos/grok-a2a`
- **GitHub:** https://github.com/estesadvisory/grok-a2a

## What this repo is

Unofficial [A2A (Agent2Agent)](https://a2a-protocol.org/latest/) wrapper for [xAI Grok](https://docs.x.ai/). Community adapter maintained by Estes Advisory — **not** an official xAI product, **not** affiliated with or endorsed by xAI.

Expose Grok as an A2A agent (Agent Card + JSON-RPC tasks → xAI Chat Completions).

## Portfolio process (shared)

Cross-repo standards live in **[estesadvisory/portfolio-ops](https://github.com/estesadvisory/portfolio-ops)** (`docs/PHILOSOPHY.md`, `docs/OPS.md`, `docs/DELIVERY.md`, `docs/ISSUE_FIRST.md`).

1. **Delivery:** multi-step work → issue → **branch → PR → review → merge** (not direct `main`). See `docs/DELIVERY.md`.
2. **Issue-first:** announce `Tracking: owner/repo#N` (skill `issue-first`).
3. **Issue bodies** are source of truth; update bodies when closing.
4. **Priority in titles:** `[P0]`…`[P3]`; park as `[P3 / parked]` with unpark criteria.
5. **Small PRs**; `Refs #N` / `Fixes #N` on implementing commits.
6. **After PR:** `/review --pr N` → fix bugs on PR → agent merge (unless `hold` / `wait` / `don't merge`). File issues only for deferred findings.
7. **Never** embed PATs/tokens in `git remote` URLs — clean HTTPS + `gh auth` keyring (or SSH).
8. **No silent product breakage** across repos; file issues first for risky changes.
9. **Session harvest** after meaningful work: short MCP summary — portfolio-ops `docs/SESSION_HARVEST.md`.

## Repo-specific non-negotiables

- Stay **unofficial**. Do not imply xAI endorsement, official branding, or catalog listing.
- Operator supplies their own `XAI_API_KEY` in gitignored `.env`. Never commit keys or paste them into issues/chat.
- Bind **localhost** (`127.0.0.1`) until inbound auth lands ([#3](https://github.com/estesadvisory/grok-a2a/issues/3)). Anyone who can reach the port can spend the operator’s xAI key.
- Dry-run (`GROK_A2A_DRY_RUN=1`) is the CI/smoke path without credits. Live Chat Completions smoke stays parked until a funded key exists ([#2](https://github.com/estesadvisory/grok-a2a/issues/2)).
- This is **A2A (the bus)**, not Artifactum (the vault). Do not fold durable storage into this adapter — see [artifactum#162](https://github.com/estesadvisory/artifactum/issues/162).
- v0.1 does not stream, cancel, or authenticate inbound clients. Those are tracked issues, not silent README lies.

## Useful links

- [README.md](README.md)
- Hub onboard: https://github.com/estesadvisory/portfolio-ops/issues/111
