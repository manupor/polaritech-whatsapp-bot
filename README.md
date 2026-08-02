# Polaritech WhatsApp Bot

Production-ready WhatsApp chatbot backend for **Polaritech Window Film**.
Built with FastAPI and the Meta WhatsApp Cloud API.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your credentials
uvicorn src.main:app --reload --port 8000
```

## Project Structure

```
src/
  main.py                  # FastAPI app entrypoint
  api/
    webhook.py             # WhatsApp webhook verification & message ingress
    ops.py                 # Internal ops API (leads, escalations, conversations)
    dashboard.py           # Server-rendered ops dashboard (Jinja2)
  templates/               # Jinja2 HTML templates for dashboard
  core/
    config.py              # Pydantic Settings loaded from .env
    constants.py           # Business rules, intents, and reply templates
  db/
    database.py            # SQLAlchemy engine, session, init_db()
    models.py              # ORM models (Contact, MessageLog, Lead, Escalation…)
    repositories.py        # CRUD operations per table
  kb/
    data/                  # FAQ JSON + Markdown knowledge base files
    loader.py              # Load knowledge base files from disk
    models.py              # Data models for KB articles
  services/
    faq_service.py         # Match user questions to KB answers
    intent_service.py      # Classify user intent from message text
    response_service.py    # Orchestrate reply generation
    escalation_service.py  # Decide when to hand off to a human
    whatsapp_service.py    # Outbound message sender (httpx)
    persistence_service.py # Persist messages, leads, escalations to DB
  state/
    conversation_store.py  # In-memory conversation history + flow state
    idempotency_store.py   # Duplicate webhook delivery protection
  schemas/
    whatsapp.py            # Pydantic models for WhatsApp webhook payloads
    chatbot.py             # Internal request/response schemas
    ops.py                 # Pydantic models for ops API responses
  tests/                   # Pytest tests
```

## Knowledge Base

The bot loads its knowledge from two sources on startup:

- **`kb/data/polaritech_faq.json`** — structured FAQ, products, policies, rules (primary)
- **`kb/data/polaritech_base_conocimiento.md`** — Markdown knowledge base (fallback)

## Environment Variables

| Variable | Description |
|---|---|
| `WHATSAPP_ACCESS_TOKEN` | Permanent or temporary access token from Meta |
| `WHATSAPP_PHONE_NUMBER_ID` | Phone number ID from WhatsApp Business account |
| `WHATSAPP_VERIFY_TOKEN` | Secret string you choose for webhook verification |
| `META_API_VERSION` | Graph API version (default: `v21.0`) |
| `DATABASE_URL` | SQLAlchemy URL (default: `sqlite:///polaritech.db`) |
| `WHATSAPP_WELCOME_IMAGE_URL` | Public URL of the welcome image (optional) |
| `WHATSAPP_WELCOME_IMAGE_ID` | Pre-uploaded Meta media ID for welcome image (optional) |
| `WELCOME_WINDOW_HOURS` | Hours before a conversation is considered "new" (default: `24`) |
| `OPENAI_API_KEY` | OpenAI key (future use) |
| `APP_ENV` | `development` or `production` |
| `LOG_LEVEL` | Logging level (`debug`, `info`, `warning`) |
| `ESCALATION_PHONE_NUMBER` | Phone number for human escalation alerts |

## Meta WhatsApp Cloud API Setup

### 1. Create a Meta App

1. Go to [developers.facebook.com](https://developers.facebook.com/) → **My Apps** → **Create App**
2. Select **Business** type → Next
3. Fill in app name → Create
4. In the app dashboard, add the **WhatsApp** product

### 2. Get your credentials

In the WhatsApp section of the Meta App Dashboard:

- **Phone Number ID** → copy to `WHATSAPP_PHONE_NUMBER_ID`
- **Temporary Access Token** → copy to `WHATSAPP_ACCESS_TOKEN`
  - For production, generate a permanent System User token via Business Settings

### 3. Set your verify token

Choose any secret string (e.g. `polaritech_webhook_2024`) and set it in `.env`:

```
WHATSAPP_VERIFY_TOKEN=polaritech_webhook_2024
```

### 4. Configure the webhook URL

Your server must be reachable over HTTPS. For local development, use ngrok:

```bash
# Terminal 1 — start the bot
uvicorn src.main:app --port 8000

# Terminal 2 — expose via ngrok
ngrok http 8000
```

Copy the ngrok HTTPS URL (e.g. `https://ab12cd34.ngrok-free.app`) and configure it in Meta:

1. In the App Dashboard → **WhatsApp** → **Configuration**
2. **Callback URL**: `https://ab12cd34.ngrok-free.app/webhook`
3. **Verify Token**: the same string from your `.env`
4. Click **Verify and Save**
5. Subscribe to the **messages** webhook field

### 5. Test it

Send a WhatsApp message to the test phone number shown in the Meta dashboard.
The bot should reply via the same channel.

## How to Test Locally with Meta Webhook

```bash
# 1. Start the server
uvicorn src.main:app --reload --port 8000

# 2. In another terminal, verify the webhook works
curl "http://localhost:8000/webhook?hub.mode=subscribe&hub.verify_token=polaritech_webhook_2024&hub.challenge=test123"
# Expected: test123

# 3. Simulate an inbound WhatsApp text message
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "object": "whatsapp_business_account",
    "entry": [{
      "id": "BIZ_ID",
      "changes": [{
        "field": "messages",
        "value": {
          "messaging_product": "whatsapp",
          "metadata": {
            "display_phone_number": "15551234567",
            "phone_number_id": "PHONE_ID"
          },
          "contacts": [{
            "profile": {"name": "Test User"},
            "wa_id": "50688001234"
          }],
          "messages": [{
            "from": "50688001234",
            "id": "wamid.test001",
            "timestamp": "1700000000",
            "type": "text",
            "text": {"body": "Hola"}
          }]
        }
      }]
    }]
  }'
# Expected: {"status":"ok"}
```

## Welcome Flow

New conversations automatically receive a welcome message before the normal bot response:

1. **Greeting text** — introduces Valentina (the virtual assistant)
2. **Welcome image** — product/quote information visual (optional)

### What counts as "new"

A conversation is treated as new if **any** of these is true:

- Contact does not exist in the database
- No conversation snapshot exists
- Last interaction is older than `WELCOME_WINDOW_HOURS` (default: 24h)

### Configuration

Set one of the image sources in `.env`:

```
WHATSAPP_WELCOME_IMAGE_URL=https://your-cdn.com/polaritech-cotizacion.jpg
# OR
WHATSAPP_WELCOME_IMAGE_ID=1234567890  # pre-uploaded via Meta API
```

If neither is configured, only the welcome text is sent (with a log warning).

Place the source image file in `assets/welcome/polaritech-cotizacion.jpg` for reference.

## Database (Persistence Layer)

The bot uses SQLite by default (`polaritech.db` in the project root). Set `DATABASE_URL` to a PostgreSQL connection string for production — no code changes needed.

### How it works

- On **startup**, `init_db()` creates all tables that don't exist yet (safe to call repeatedly).
- On every **inbound message**, the contact is upserted and the message is logged.
- On every **outbound reply**, the message is logged, the conversation snapshot is updated, and leads/escalation records are created when appropriate.

### Where the DB file lives

```
polaritech-whatsapp-bot/
  polaritech.db          ← SQLite file (auto-created on first startup)
```

### Inspect records locally

```bash
# Open the SQLite CLI
sqlite3 polaritech.db

# View contacts
SELECT * FROM contacts ORDER BY last_seen_at DESC LIMIT 10;

# View open escalations
SELECT * FROM escalation_records WHERE status = 'open';

# View leads
SELECT * FROM lead_records ORDER BY created_at DESC;

# View conversation snapshot for a specific phone
SELECT * FROM conversation_snapshots WHERE phone_number = '+50688001234';
```

### PostgreSQL (required for Vercel / serverless)

SQLite **cannot** be used on Vercel: the filesystem is ephemeral, so the database
is wiped on every cold start. The bot then loses conversation context and greets
returning users again mid-conversation.

The `psycopg` (v3) driver is already in `requirements.txt`, and
`src/db/database.py` normalizes provider URLs automatically, so both
`postgres://` and `postgresql://` connection strings work as-is.

1. Create a free Postgres database:
   - **Neon** — https://neon.tech (recommended, serverless-friendly)
   - **Supabase** — https://supabase.com
2. Copy the connection string, e.g.
   ```
   postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
3. Set `DATABASE_URL` to that value in Vercel → Settings → Environment Variables
   (Production and Preview), then redeploy.
4. Tables are created automatically on the first cold start by `init_db()`.

Connections use `NullPool` in non-SQLite mode because each serverless invocation
runs in its own process, so cross-request pooling only exhausts Postgres
connection limits.

Local development can stay on SQLite:
```bash
# .env
DATABASE_URL=sqlite:///polaritech.db
```

## Internal Ops API

A minimal JSON API for the Polaritech team to view and manage leads and escalations.
No auth yet — isolate behind a reverse proxy or VPN in production.

### Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/ops/health` | Ops service health check |
| GET | `/ops/escalations` | List escalations (filters: `status`, `priority`, `limit`, `offset`) |
| GET | `/ops/escalations/{id}` | Get single escalation |
| PATCH | `/ops/escalations/{id}/status` | Update status (`open`, `in_progress`, `closed`) |
| GET | `/ops/leads` | List leads (filters: `status`, `lead_type`, `limit`, `offset`) |
| GET | `/ops/leads/{id}` | Get single lead |
| PATCH | `/ops/leads/{id}/status` | Update status (`new`, `contacted`, `quoted`, `closed`) |
| GET | `/ops/conversations/{phone_number}` | Get conversation snapshot |

### Example curl calls

```bash
# List all open escalations
curl http://localhost:8000/ops/escalations?status=open

# Get escalation #1
curl http://localhost:8000/ops/escalations/1

# Mark escalation #1 as in_progress
curl -X PATCH http://localhost:8000/ops/escalations/1/status \
  -H "Content-Type: application/json" \
  -d '{"status": "in_progress"}'

# List all quote leads
curl http://localhost:8000/ops/leads?lead_type=quote

# Mark lead #3 as contacted
curl -X PATCH http://localhost:8000/ops/leads/3/status \
  -H "Content-Type: application/json" \
  -d '{"status": "contacted"}'

# Get conversation state for a phone number
curl http://localhost:8000/ops/conversations/+50688001234
```

## Operations Dashboard

A minimal server-rendered admin UI available at **`/dashboard`**.

### Pages

| Path | Description |
|---|---|
| `/dashboard/` | Home — counts for open escalations, in-progress, new/contacted/quoted leads |
| `/dashboard/escalations` | Escalation list with status and priority filters |
| `/dashboard/escalations/{id}` | Escalation detail + quick status update buttons |
| `/dashboard/leads` | Lead list with status and type filters |
| `/dashboard/leads/{id}` | Lead detail + quick status update buttons |
| `/dashboard/conversations` | Conversation lookup by phone number |

### Dashboard Actions

From the conversation lookup page, operators can:

- **Tomar conversación** — Human takes over; bot stops auto-replying
- **Reanudar bot** — Resume bot auto-responses
- **Marcar como lead** — Create a lead from the current conversation data
- **Marcar escalamiento** — Create an escalation record

### Notes

- No auth yet — isolate behind a reverse proxy or VPN in production
- Mobile-friendly responsive layout
- Uses Jinja2 templates rendered by FastAPI
- Reads directly from the same DB used by the ops API

## Environments: Staging & Production

### Staging

Uses Meta's **test phone number** from the WhatsApp Cloud API dashboard.

```bash
cp .env.staging .env
# Edit .env with your test credentials from Meta Developer Portal
uvicorn src.main:app --reload --port 8000
```

1. Go to [Meta Developer Portal](https://developers.facebook.com/) > Your App > WhatsApp > API Setup
2. Copy the **temporary access token** and **test phone number ID**
3. Set `WHATSAPP_VERIFY_TOKEN` to any secret string
4. Configure the webhook URL: `https://your-ngrok-or-server.com/webhook`
5. Subscribe to `messages` webhook field
6. Send a test message from one of the allowed test numbers

### Production

Uses the client's **real WhatsApp Business number** via Cloud API coexistence.

```bash
cp .env.production .env
# Edit .env with real business credentials
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

#### Cloud API + WhatsApp Business App Coexistence

Production is designed for **coexistence mode**, where:

1. The client keeps their existing WhatsApp Business App and phone number
2. The same number is onboarded to Cloud API without losing WhatsApp Business App access
3. Both the bot (via Cloud API webhook) and the human (via WhatsApp Business App) can interact with customers
4. When `human_takeover=true` in the dashboard, the bot stops auto-replying and the human responds from the WhatsApp Business App

#### Production Onboarding Steps

1. **Register the existing business number** in Meta Business Manager under WhatsApp Accounts
2. **Complete phone number verification** via the Meta Developer Portal
3. **Enable coexistence**: In the WhatsApp Manager, choose "Use existing WhatsApp Business number with Cloud API"
4. **Generate a permanent System User token** (never use the temporary developer token)
5. **Set the webhook URL** to your production server: `https://your-domain.com/webhook`
6. **Subscribe to `messages`** webhook field
7. **Set environment variables** in `.env` from `.env.production` template
8. **Verify** the webhook handshake via the Meta Developer Portal

> **Important**: Do NOT perform a destructive migration of the phone number.
> The coexistence setup preserves the client's WhatsApp Business App access.
> Messages arrive to both the app and the webhook simultaneously.

### Conversation Control

| State | Bot responds? | Human responds? |
|---|---|---|
| `human_takeover=false, bot_active=true` | Yes | Optional |
| `human_takeover=true, bot_active=false` | No | Yes (via WhatsApp Business App) |

Operators toggle this from the dashboard conversation lookup page.

## Running Tests

```bash
python -m pytest src/tests/ -v
```

## Extending

- **OpenAI integration**: Add an `openai_service.py` under `services/` and call it from `response_service.py` when the FAQ service has no match.
- **Persistent state**: Swap `conversation_store.py` for a Redis or database-backed implementation. The `IdempotencyBackend` interface in `idempotency_store.py` is designed for the same swap.
- **New intents**: Add entries to `constants.py` and handle them in `intent_service.py`.
