# Tech Stack Decision

## What We're Building
A restaurant voice agent for Parkash Sweets that:
- Answers incoming phone calls (Twilio) and browser sessions (React frontend)
- Understands Punjabi, Hindi, and English in the same call
- Takes food orders from customers using live menu data from Clover POS
- Creates real orders in the Clover POS dashboard
- Confirms the order back to the customer via TTS

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
| POS | **Clover** | Live menu sync + real order creation in restaurant's POS system |
| Voice bot server | **Python + websockets** | Port 8765 — runs the 4-processor pipeline + Clover client |
| Twilio bridge | **Python + FastAPI** | Port 5050 — Twilio phone bridge + Clover webhook relay |
| Frontend | **React (Vite)** | Served via nginx — browser UI for testing without a phone |
| Reverse proxy | **Caddy** | Ports 80/443 — HTTPS, path-based routing to all services |
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
└── frontend/                  ← browser test UI (React + Vite, served by nginx)
    └── (don't touch — VITE_SONIOX_VOICE_BOT_WS_URL baked in at build time)
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

**Install with uv** (not pip) — run `uv sync` inside each folder separately.

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
9. Deploy to server (Docker — 4 services: voice-server, twilio-bridge, frontend, caddy)

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
