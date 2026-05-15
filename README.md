# Restaurant Voice Agent — Soniox

A voice agent that answers restaurant phone calls and takes orders in **Punjabi and English**.
Customer calls → Agent picks up → Takes the order → Confirms it → Order sent to restaurant.

## Why Soniox
Soniox supports **Punjabi language** (60+ languages) — that's the core reason we chose it.

## Base Project
We build on top of Soniox's official voice bot demo:
`soniox_examples/apps/soniox-voice-bot-demo/`

We only modify one file: **`server/tools.py`** — everything else is reused as-is.

## What We Change
| File | What we do |
|------|-----------|
| `server/tools.py` | Replace AutoWorks tools with restaurant tools (menu, place order) |
| `server/.env` | Add our API keys |
| `twilio/.env` | Set language to `pa` (Punjabi) |

## Project Structure
```
soniox_examples/apps/soniox-voice-bot-demo/
├── server/          ← voice agent brain
│   ├── tools.py     ← THE ONLY FILE WE CUSTOMIZE
│   ├── processors/  ← don't touch (VAD, STT, LLM, TTS)
│   └── .env         ← our API keys go here
├── twilio/          ← phone call handler (don't touch)
└── frontend/        ← browser UI for local testing (don't touch)
```

## Our tools.py Changes
Replacing 3 AutoWorks tools with 3 restaurant tools:

| AutoWorks (original) | Our Restaurant |
|----------------------|----------------|
| `search_knowledge_base` | `get_menu` — returns restaurant menu |
| `check_availability` | `check_item_availability` — is item in stock |
| `create_appointment` | `place_order` — saves order + sends WhatsApp/email |

## Quick Reference
- [Pricing](pricing.md)
- [Architecture](docs/architecture.md)
- [Soniox API Reference](docs/soniox-api.md)
- [How Phone Calls Work](docs/phone-calls.md)
- [Tech Stack Decision](docs/stack.md)
- [Voice Agent Demo Reference](docs/soniox-voice-agent-demo.md)

## Run Locally for Testing (no Twilio needed)

### 1. Start the server
```bash
cd soniox_examples/apps/soniox-voice-bot-demo/server

uv venv
.venv\Scripts\activate
uv sync

# Copy env and fill in your keys
copy .env.example .env

uv run main.py
```

### 2. Start the frontend
```bash
cd soniox_examples/apps/soniox-voice-bot-demo/frontend

npm install
npm run dev
```

### 3. Open browser
Go to `http://localhost:5173` → select **Punjabi** → speak.

## Run with Real Phone Calls (Twilio)
```bash
cd soniox_examples/apps/soniox-voice-bot-demo/twilio

uv venv
.venv\Scripts\activate
uv sync

copy .env.example .env
# Set SONIOX_VOICE_BOT_WS_URL=ws://localhost:8765
# Set VOICE_BOT_LANGUAGE=pa

uv run main.py
# Then expose with ngrok: ngrok http 5050
```

## API Keys Needed
| Key | Where to get |
|-----|-------------|
| `SONIOX_API_KEY` | console.soniox.com |
| `OPENAI_API_KEY` | platform.openai.com |
| `TWILIO_*` | twilio.com (only for phone calls) |

## Build Status
- [ ] Step 1: Run the demo as-is locally (browser test)
- [ ] Step 2: Confirm Punjabi works
- [ ] Step 3: Write restaurant `tools.py`
- [ ] Step 4: Test full order flow in browser
- [ ] Step 5: Connect Twilio for real phone calls
- [ ] Step 6: Production deployment


https://api.vapi.ai/twilio/sms