# Tech Stack Decision

## What We're Building
A restaurant voice agent and e-commerce store for Parkash Sweets that:
- Answers incoming phone calls (Twilio) and browser sessions (React frontend — "Order with Sierra" tab)
- Understands Punjabi, Hindi, and English in the same call
- Takes food orders from customers using live menu data from Clover POS
- Creates real orders in the Clover POS dashboard
- Confirms the order back to the customer via TTS
- Serves a full e-commerce "Browse Store" tab: category grid, search, cart, modifier selection, checkout → Clover order

---

## Final Stack

| Layer | Tool | Why |
|-------|------|-----|
| Base project | **soniox-voice-bot-demo** | Soniox's official demo — complete voice agent pipeline |
| Phone calls | **Twilio** | Real phone number, streams audio via WebSocket to our bridge |
| STT | **Soniox** | Punjabi language support, sub-200ms latency, streaming |
| TTS | **Soniox** | Same API, Punjabi voices, natural sounding |
| VAD | **Silero VAD** | Detects when customer starts/stops speaking, enables barge-in |
| LLM | **OpenAI gpt-4o-mini** | Cheap, fast, good tool-calling support |
| POS | **Clover** (default) + **Square** (optional) | Live menu sync + order creation; switchable via `?pos=` dropdown |
| Voice bot server | **Python + websockets** | Port 8765 — runs the 4-processor pipeline + Clover/Square POS client |
| Twilio bridge | **Python + FastAPI** | Port 5050 — Twilio phone bridge + Clover webhook relay |
| Store API | **Python + FastAPI** | Port 8766 — dual-POS e-commerce REST API (Clover + Square via `?pos=`) |
| Frontend | **React (Vite)** | Served via nginx — two tabs: AI ordering + Browse Store |
| Reverse proxy | **Caddy** | Ports 80/443 — HTTPS, path-based routing to all 5 services |
| Dev tunneling | **ngrok** | Exposes local server to Twilio during development |

---

## What We Are NOT Using
- ~~VAPI~~ — paid abstraction tool, hides how things work
- ~~Retell~~ — same
- ~~LiveKit~~ — for WebRTC/browser calls, not phone calls
- ~~Pipecat~~ — another framework, Soniox's own demo is better for us
- ~~Node.js~~ — Soniox's voice agent demo is Python, we follow that

---

## Folder Structure

```
soniox_examples/apps/soniox-voice-bot-demo/   ← base project
├── server/                    ← voice bot brain (Python, port 8765)
│   ├── main.py                ← ✅ EDITED: DynamicTTSProcessor, Clover init, logging config
│   ├── session.py             ← manages message queue per call
│   ├── languages.py           ← 60+ languages including "pa" (Punjabi)
│   ├── tools.py               ← ✅ EDITED: restaurant tools, Clover integration
│   ├── clover.py              ← ✅ NEW: CloverClient, MenuCache, order creation
│   ├── clover_types.py        ← ✅ NEW: CloverItem, CloverCreatedOrder, CloverOrderType
│   ├── square_client.py       ← ✅ NEW: SquareClient + SquareMenuCache (same interface as Clover)
│   ├── menu.json              ← spoken aliases and pronunciation hints (merged into Clover data)
│   ├── processors/
│   │   ├── vad.py             ← Silero VAD (don't touch)
│   │   ├── stt.py             ← Soniox STT (don't touch)
│   │   ├── llm.py             ← ✅ EDITED: 3 key log lines promoted from debug→info
│   │   └── tts.py             ← ✅ EDITED: dead stream ID recovery, _dead_stream_ids set
│   └── .env                   ← loaded by main.py directly (local dev only)
├── twilio/                    ← phone call bridge (Python, port 5050)
│   ├── main.py                ← ✅ EDITED: /clover-webhook endpoint added
│   └── .env                   ← local dev only (Docker uses env from docker-compose.yml)
├── store-api/                 ← ✅ NEW: e-commerce REST API (Python + FastAPI, port 8766)
│   ├── main.py                ← GET /menu, POST /orders, GET /orders/{id}, GET /health
│   ├── requirements.txt       ← fastapi, uvicorn, httpx, pydantic, structlog
│   └── Dockerfile             ← python:3.13-slim, port 8766
└── frontend/                  ← browser UI (React + Vite, served by nginx, port 80)
    ├── src/
    │   ├── App.tsx             ← ✅ EDITED: tab switcher ("Order with Sierra" / "Browse Store")
    │   ├── components/
    │   │   ├── conversation.tsx ← ✅ EDITED: removed chat panel, 3-column layout
    │   │   └── Store.tsx       ← ✅ NEW: full e-commerce store UI (~600 lines)
    │   └── vite-env.d.ts      ← ✅ EDITED: added VITE_STORE_API_URL type
    └── vite.config.ts         ← ✅ EDITED: proxy /store-api → localhost:8766 (local dev)
```

---

## Python Dependencies (actual, from pyproject.toml)

### server/
```
openai>=1.101.0      # LLM
python-dotenv        # env vars
structlog            # structured logging (INFO level — debug calls suppressed)
websockets>=15.0.1   # WebSocket to Soniox STT/TTS
silero-vad           # Voice Activity Detection
torch                # required by silero-vad
torchaudio           # required by silero-vad
onnxruntime          # required by silero-vad
numpy                # audio processing
pydantic>=2.11.7     # request validation
httpx                # async HTTP client for Clover API calls
rapidfuzz            # fuzzy menu item name matching (≥80 score for items, ≥70 for categories)
```

### twilio/
```
fastapi>=0.116.1     # webhook server
uvicorn>=0.35.0      # run FastAPI
websockets>=15.0.1   # connect to voice bot server
twilio>=9.7.2        # Twilio helper
audioop-lts>=0.2.2   # audio format conversion (mulaw ↔ PCM), Python 3.13 compatible
httpx                # internal HTTP calls to voice-server (/internal/clover-reload)
```

### store-api/
```
fastapi>=0.116.1     # REST API
uvicorn[standard]>=0.34.0  # run FastAPI
httpx>=0.28.1        # async HTTP client for Clover API calls
pydantic>=2.11.7     # request/response models
structlog>=25.3.0    # structured logging
```

**Install with uv** (not pip) — run `uv sync` inside `server/` and `twilio/`. For `store-api/`, use `pip install -r requirements.txt` (uses requirements.txt, not pyproject.toml).

---

## Build Order

1. Run demo as-is in browser → confirm everything works
2. Pick Punjabi in language selector → confirm Punjabi STT/TTS works
3. Write restaurant `tools.py` (menu + place_order using static menu.json)
4. Test order flow in browser
5. Set up Twilio phone number
6. Run twilio bridge + ngrok → test with real phone call
7. Wire `place_order` to WhatsApp/email notification (n8n fallback)
8. **Clover POS integration** — connect live menu, create real orders in dashboard
   - `clover.py`: CloverClient + MenuCache (fuzzy lookup, spoken aliases)
   - `clover_types.py`: typed data models
   - `tools.py`: get_menu/check_availability/place_order use Clover as source of truth
   - `main.py`: DynamicTTSProcessor (lazy connect, idle reconnect, dead stream recovery)
   - `twilio/main.py`: /clover-webhook endpoint for inventory change events
9. **Browse Store e-commerce tab** — Parkash Store with Clover backend
   - `store-api/main.py`: FastAPI on 8766, GET /menu + POST /orders via Clover REST
   - `frontend/src/components/Store.tsx`: full store UI (category filter, search, cart, modal, checkout)
   - `frontend/src/App.tsx`: tab switcher between AI ordering and Browse Store
   - `conversation.tsx`: removed transcript panel, now 3-column layout
   - Docker: 5th service (store-api), Caddy routes `/store-api/*` to it
10. Deploy to server (Docker — 5 services: voice-server, twilio-bridge, store-api, frontend, caddy)
    - **Pending:** switch store-api `CLOVER_BASE_URL` from sandbox to production when Clover production access is purchased
    - **Pending:** add Clover Hosted Checkout (redirect-based payment) after production access

---

## API Keys Needed

| Key | Service | Get from |
|-----|---------|----------|
| `SONIOX_API_KEY` | STT + TTS | console.soniox.com |
| `OPENAI_API_KEY` | LLM | platform.openai.com |
| `TWILIO_*` | Phone calls | twilio.com |
| `CLOVER_ACCESS_TOKEN` | POS orders + menu | developer.clover.com |
| `CLOVER_MERCHANT_ID` | POS merchant | Clover dashboard → Account Settings |
| `CLOVER_WEBHOOK_SECRET` | Webhook HMAC validation | any strong random string you choose |
