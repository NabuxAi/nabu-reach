# Nabu Reach — WhatsApp Campaign Studio (MVP)

**Free Core Forever.** Local-first, dependency-free campaign drafting and consent-ledger management for WhatsApp business messaging. This is a working **draft-only proof of concept**, not a live-sending tool.

![Status: draft-only](https://img.shields.io/badge/messaging-draft--only-blue)

## What works today

- Responsive dark-blue/cyan campaign dashboard with accounts, contacts, and drafts.
- Multiple account records: `mock` is available; `meta_cloud`, `gowa`, and `evolution` are **setup placeholders**, not implemented connections.
- CSV import with explicit opt-in evidence (`consent_source` and `consent_at`), validation, and row-level errors.
- Opt-outs cannot be undone by subsequent CSV imports.
- Message composition and `{{name}}` / `{{phone}}` previews for opted-in contacts only.
- Draft persistence with SQLite and basic audit events. A hard cap of 50 preview recipients applies.
- No live send endpoint, background queue, or provider credentials; the UI cannot send WhatsApp messages.
- No external Python packages; unit/HTTP smoke tests run with the standard library.

## Quick start

Requirements: Python 3.11+.

```bash
python -m reach.server
# Open http://127.0.0.1:8787
python -m unittest discover -s tests -v
```

Optional local data path:

```bash
DB_PATH=/tmp/nabu-reach.sqlite3 python -m reach.server
```

Docker (binds to host loopback only):

```bash
docker compose up --build
# Open http://127.0.0.1:8787
```

The MVP **has no user authentication**. Never publish its port directly to the Internet, place it on a shared computer, or load real customer data until authentication, encryption, retention and privacy requirements have been implemented and reviewed.

## Example CSV

```csv
phone,name,consent,consent_source,consent_at
+15550100101,Example Person,yes,demo_signup_form,2026-01-01T12:00:00Z
```

Demo phone numbers are fictitious; do not message them. `consent` supports `yes`/`no`, `true`/`false`, `1`/`0`, or `opt_in`/`opt_out`. Phone numbers must be E.164 with a leading `+`. Opt-in requires a timestamp with a timezone and the source of that consent. Duplicate phone numbers are updated except that existing opt-outs remain opted out. All content remains local in SQLite.

## API (localhost only)

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/healthz` | Draft-only health check |
| GET | `/api/summary` | Workspace counts |
| GET/POST | `/api/accounts` | Account placeholders |
| GET | `/api/contacts` | Latest 200 ledger entries |
| POST | `/api/contacts/import` | Raw `text/csv` import |
| POST | `/api/contacts/opt-out` | Explicit opt-out by E.164 phone |
| POST | `/api/campaigns/preview` | Consent-checked preview |
| GET/POST | `/api/campaigns` | Save / list drafts |

Example:

```bash
curl -s http://127.0.0.1:8787/healthz
curl -s -X POST http://127.0.0.1:8787/api/accounts \
  -H 'Content-Type: application/json' -d '{"label":"Demo","provider":"mock"}'
curl -s -X POST http://127.0.0.1:8787/api/contacts/import \
  -H 'Content-Type: text/csv' --data-binary @examples/contacts.csv
curl -s -X POST http://127.0.0.1:8787/api/campaigns/preview \
  -H 'Content-Type: application/json' -d '{"message":"Hi {{name}}, thanks for opting in."}'
```

## Architecture and roadmap

```text
web UI ──> localhost HTTP API ──> SQLite (accounts, consent ledger, drafts, audit)
                         └──> mock/official provider adapters (future; disabled)
```

**Existing related project:** [NabuxAi/whatsapp-mcp](https://github.com/NabuxAi/whatsapp-mcp) already offers multi-number management and official Meta WhatsApp Cloud API support. Nabu Reach should integrate via a secure server-to-server interface, **not** recreate that gateway.

The official Meta Cloud API should be the preferred live integration after Meta authorization, security review, approved templates and account-level quotas. GOWA and Evolution may be evaluated as optional self-hosted adapters **only for permitted, opted-in messaging**; unofficial WhatsApp Web integrations can violate platform terms and result in account restrictions. This MVP does **not** implement account rotation, ban-risk optimization, unsolicited bulk messaging, contact scraping, or limit bypasses.

Before a real deployment, implement: owner authentication & RBAC, CSRF defenses appropriate for login cookies, encrypted secrets, tenant isolation, provider authorization, approved-template validation, webhook verification, suppression list synchronization, opt-out keyword handling, bounded queues, per-provider legitimate rate limits, time-window controls, idempotency, observability, backups, privacy and retention controls, and independent security review.

## Costs and licensing

- **Software core:** MIT license, no mandatory card, subscription, or paid upgrade.
- **Running locally:** no software or hosted service fee.
- **Self-hosting:** infrastructure, domain, SSL and operational maintenance may cost money.
- **Meta WhatsApp Business Platform:** message/template pricing and permissions depend on current Meta rules, geography and account status. No message cost occurs in this draft-only MVP.
- **Unofficial adapters:** not included; their compatibility, licensing and operational risks require separate assessment.

## Security

Read [docs/SECURITY.md](docs/SECURITY.md). Do not upload private customer phone lists to public repositories.

## Try the public interactive demo

**[Launch Nabu Reach demo](https://reach.nabuxai.com)** — a browser-only simulation with fictional sample contacts. It never connects to WhatsApp, never sends messages, and does not persist imported data to a server.

![Nabu Reach dashboard — real screenshot](docs/assets/desktop-overview.png)

The hosted demo and local-first MVP have different trust boundaries:

| | Public interactive demo | Local-first MVP |
|---|---|---|
| Storage | Browser memory, reset on reload | Local SQLite |
| API/backend | None | Python HTTP on localhost |
| WhatsApp sending | Disabled | Disabled |
| Authentication | Not needed for synthetic data | Not implemented; localhost only |
| Real contact data | **Never import** | Only on a trusted local machine |

To build the static demo: `python3 demo/build.py`. Serve `dist/demo` using a static server. A hardened read-only Nginx container is available at `demo/Dockerfile`, and an example reverse-proxy Compose definition is at `deploy/compose.demo.yaml`. The demo blocks network connections with a strict Content Security Policy. Its CSV parser is intentionally simplified for synthetic demo records; use the local MVP for stricter import validation.

## Community

Found a consent, privacy or reliability issue? Open an issue with a minimal reproducible example and no personal data. Contributions are welcome with tests. No mandatory subscription, card or paid API is required for the core.
