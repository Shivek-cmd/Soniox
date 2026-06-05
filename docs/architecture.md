# Voice Agent Architecture

This project runs a phone-based and browser-based restaurant voice agent for Parkash Sweets.
Twilio handles phone calls. Caddy exposes the public HTTPS endpoint. The Twilio bridge converts Twilio's media stream into raw audio. The core voice server runs the AI pipeline and owns the Clover POS connection.

`soniox_examples` is tracked directly inside the main `Soniox` repo (not a submodule).

---

## Production Deployment

Four Docker services from `docker-compose.yml` at the repo root:

```text
Internet
  |
  v
voice.bizbull.ai  (Caddy — ports 80/443)
  |
  |-- /ws                → voice-server:8765    (browser WebSocket)
  |-- /incoming-call     → twilio-bridge:5050   (Twilio phone call start)
  |-- /transfer-twiml    → twilio-bridge:5050   (call transfer)
  |-- /media-stream      → twilio-bridge:5050   (Twilio audio stream)
  |-- /clover-webhook    → twilio-bridge:5050   (Clover inventory events)
  |-- /*                 → frontend:80          (React UI)
```

### `caddy`

File: `Caddyfile`

Path-based routing. One public entrypoint covers all four services.

- `/ws` — proxies browser WebSocket connections to the voice server
- `/incoming-call`, `/transfer-twiml`, `/media-stream`, `/clover-webhook` — all phone/POS webhook traffic to the Twilio bridge
- Everything else — React frontend

Caddy handles HTTPS and auto-renews Let's Encrypt TLS certs. Data stored in `caddy_data` Docker volume.

### `twilio-bridge`

File: `soniox_examples/apps/soniox-voice-bot-demo/twilio/main.py`

FastAPI app on port 5050.

Responsibilities:
- Receives Twilio webhooks at `/incoming-call`, `/transfer-twiml`, `/media-stream`
- Opens an internal WebSocket to `voice-server:8765` per call
- Forwards caller audio to voice server; converts bot audio (PCM 24kHz → mulaw 8kHz) back to Twilio
- Receives Clover inventory webhooks at `/clover-webhook`, validates HMAC, pings `voice-server:8765/internal/clover-reload`
- Handles call transfer and barge-in (clears Twilio audio queue on interruption)

Key env vars:
```env
SONIOX_VOICE_BOT_WS_URL=ws://voice-server:8765
VOICE_SERVER_INTERNAL_URL=http://voice-server:8765
CLOVER_WEBHOOK_SECRET=...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
NGROK_URL=https://voice.bizbull.ai
```

### `voice-server`

File: `soniox_examples/apps/soniox-voice-bot-demo/server/main.py`

Raw Python WebSocket server on port 8765. Not FastAPI.

Responsibilities:
- Accepts WebSocket connections from the Twilio bridge (phone) and browser (frontend)
- Initialises Clover POS client at startup — blocks until menu is loaded
- Runs the AI pipeline per session: VAD → STT → LLM → TTS
- Exposes `GET /internal/clover-reload` for the Twilio bridge webhook relay

Key env vars:
```env
SONIOX_API_KEY=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
CLOVER_BASE_URL=https://api.clover.com
CLOVER_MERCHANT_ID=...
CLOVER_ACCESS_TOKEN=...
CLOVER_WEBHOOK_SECRET=...
```

### `frontend`

File: `soniox_examples/apps/soniox-voice-bot-demo/frontend/`

React + Vite app, served via nginx on port 80. Used for browser testing without a phone.

`VITE_SONIOX_VOICE_BOT_WS_URL` is a **build-time arg** baked into the JS bundle — must be set to `wss://voice.bizbull.ai/ws` before building.

---

## Phone Call Flow

```text
Customer dials +15878175156
  |
  | POST https://voice.bizbull.ai/incoming-call
  v
Caddy → twilio-bridge /incoming-call
  |
  | returns TwiML: Connect → Stream wss://voice.bizbull.ai/media-stream
  v
Twilio opens media WebSocket
  |
  v
Caddy → twilio-bridge /media-stream
  |
  | ws://voice-server:8765?audio_in_format=mulaw&...&skip_opening_greeting=true
  v
voice-server (new Session)
  |
  | VAD → Soniox STT → OpenAI LLM → Soniox TTS
  v
twilio-bridge (PCM 24kHz → mulaw 8kHz → Twilio mark/media events)
  |
  v
Customer hears the agent
```

---

## Clover Webhook Flow

```text
Restaurant updates an item price in Clover dashboard
  |
  | POST https://voice.bizbull.ai/clover-webhook (X-Clover-Auth header)
  v
Caddy → twilio-bridge /clover-webhook
  |
  | validates HMAC, checks event type (I/IC/IG/IM = inventory events)
  | GET http://voice-server:8765/internal/clover-reload
  v
voice-server process_request handler
  |
  | client.schedule_menu_reload()  (debounced 2s)
  v
Clover API: GET /v3/merchants/{id}/items
  |
  v
MenuCache.replace_all(raw_items)
  → all new sessions use updated prices
```

---

## Core Voice Pipeline

Every call or browser session creates one `Session` in the voice server.

```python
processors = [
    VADProcessor(...),
    STTProcessor(...),
    LLMProcessor(...),
    DynamicTTSProcessor(...),
]
session = Session(processors, websocket)
await session.run()
```

### 1. `VADProcessor`

File: `server/processors/vad.py`

Silero VAD. Detects speech start/end. Enables barge-in (caller can interrupt the bot).

### 2. `STTProcessor`

File: `server/processors/stt.py`

Streams audio to Soniox real-time STT. Uses restaurant vocabulary context (`STT_CONTEXT`) and language hints. For phone calls the hints are `["pa", "hi", "en"]` (Punjabi, Hindi, English).

### 3. `LLMProcessor`

File: `server/processors/llm.py`

Sends transcriptions to OpenAI and streams response text to TTS. Key behaviours:
- Phone calls: opens with a cached WAV greeting asking for language, then detects language from first reply and switches TTS accordingly
- Browser: plays the opening greeting directly in the chosen language
- Calls tools (`place_order`, `get_menu`, `check_item_availability`, `select_language`, `transfer_call`) when needed
- Logs `User → LLM`, `Calling tools`, `Got tool call response` at INFO level

### 4. `DynamicTTSProcessor`

Defined in: `server/main.py` (extends `TTSProcessor` from `server/processors/tts.py`)

- Reads language/voice from `RestaurantState` on each new TTS stream (supports mid-call language switch)
- **Lazy connection**: does not open the Soniox TTS WebSocket at session start — connects on first TTS use
- **Time-based reconnect**: if the last TTS stream finished >45 seconds ago, reconnects before starting a new stream (Soniox closes idle connections at ~60s)
- **Retry on connect**: up to 3 attempts with 2s/4s backoff if the Soniox handshake times out
- **Dead stream recovery**: if Soniox returns 408/400 for a stream, marks that stream ID dead — `_send_task` discards queued chunks for it, `_active_stream_id` is cleared, and the next TTS chunk starts a fresh stream automatically
- Fires `OrderConfirmedMessage` and `TransferCallMessage` after the farewell audio finishes

---

## Clover POS Integration

File: `server/clover.py`

`CloverClient` is a singleton initialised at startup. It is the source of truth for all menu data and order creation.

### Startup sequence

```text
main() calls CloverClient.init()
  → GET /v3/merchants/{id}/order_types  (maps "Takeout"/"Delivery"/"Dine-In" to Clover IDs)
  → GET /v3/merchants/{id}/items        (loads full menu into MenuCache)
  → starts background poll task (every 5 min, delta sync)
```

If the menu load fails, the server falls back to `menu.json` until Clover is reachable.

### MenuCache

Three indexes built at startup and on every reload:
- `by_id` — Clover item ID → `CloverItem`
- `by_name` — normalized name / spoken alias → Clover item ID (fuzzy matched at ≥80 score)
- `by_category` — category name → list of `CloverItem` (fuzzy matched at ≥70 score)

Extras (spoken aliases, pronunciation hints) are loaded from `menu.json` and merged into `CloverItem` objects. Clover has no concept of these fields.

### Order creation

```text
place_order tool called
  → CloverClient.create_order(order_type, items, customer_name, phone, notes)
    → POST /v3/merchants/{id}/orders           (creates shell with manualTransaction:true)
    → POST /v3/merchants/{id}/orders/{id}/line_items  (one POST per unit — Clover has no qty field)
    → GET  /v3/merchants/{id}/orders/{id}      (fetch final order for total)
  → returns CloverCreatedOrder with order_id
```

`manualTransaction: true` marks the order as a remote/phone order so it appears in the Clover dashboard Orders list.

### Clover API logging

Every HTTP call through `_request()` logs:
```
clover.api.request   method=POST  path=/orders  attempt=1
clover.api.response  method=POST  path=/orders  status=200  ms=245
```

### Token management

For production, set `CLOVER_REFRESH_TOKEN`. The client auto-refreshes the access token 5 minutes before its 1-hour expiry. Sandbox tokens never expire — leave `CLOVER_REFRESH_TOKEN` empty.

---

## Restaurant Tools

File: `server/tools.py`

| Tool | Purpose |
|---|---|
| `get_menu(category)` | Returns menu items from Clover cache; falls back to menu.json |
| `check_item_availability(name)` | Checks Clover cache first; falls back to static data |
| `place_order(...)` | Creates order in Clover POS; falls back to n8n webhook |
| `select_language(language)` | Switches TTS language/voice mid-call |
| `transfer_call(reason)` | Transfers call to owner phone number |

`get_system_message()` dynamically builds the `## PRICES` section from live Clover cache at session start — the LLM always has the current prices.

---

## Logging

All logs use `structlog` at INFO level. Third-party stdlib loggers (`httpx`, `websockets`, `httpcore`) are silenced.

Key log events:
```
Warming up VAD model...
clover.api.request / clover.api.response    — every Clover HTTP call with ms timing
clover.order_types.ready                    — startup: order type IDs mapped
menu_cache.replaced                         — menu loaded or reloaded
clover.ready                                — Clover fully initialised
Starting WebSocket server
Starting session                            — new call/browser session
User → LLM                                 — transcription sent to OpenAI
Calling tools                               — LLM made a tool call
Got tool call response                      — tool result returned to LLM
clover.order.created                        — order confirmed in Clover POS
Session completed.
```

---

## Audio Formats

| Stage | Format |
|---|---|
| Twilio → bridge | mulaw, 8kHz, mono, base64 JSON |
| Bridge → voice-server | mulaw, 8kHz, mono, raw bytes |
| Voice-server STT input | configured from WebSocket query params |
| Soniox TTS output | PCM, 24kHz, mono |
| Voice-server → bridge | PCM, 24kHz audio bytes |
| Bridge → Twilio | mulaw, 8kHz, mono, base64 JSON |

---

## Interruption Handling

1. Voice server sends transcription events back to the Twilio bridge
2. Bridge tracks queued bot audio using Twilio `mark` messages
3. When caller speech is detected while bot audio is pending, bridge sends `{"event": "clear"}` to Twilio

---

## Environment Variables

All variables are in root `.env` and substituted by `docker-compose.yml`.

### Voice server
```env
SONIOX_API_KEY=...
SONIOX_STT_MODEL=stt-rt-v4
SONIOX_TTS_MODEL=tts-rt-v1
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.85
LLM_MAX_TOKENS=200
N8N_WEBHOOK_URL=...
WEBSOCKET_HOST=0.0.0.0
WEBSOCKET_PORT=8765
CLOVER_BASE_URL=https://api.clover.com
CLOVER_MERCHANT_ID=...
CLOVER_ACCESS_TOKEN=...
CLOVER_REFRESH_TOKEN=
CLOVER_WEBHOOK_SECRET=...
CLOVER_MENU_POLL_INTERVAL=300
```

### Twilio bridge
```env
SONIOX_VOICE_BOT_WS_URL=ws://voice-server:8765
VOICE_SERVER_INTERNAL_URL=http://voice-server:8765
VOICE_BOT_LANGUAGE=pa
VOICE_BOT_VOICE=Maya
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_NUMBER=+15878175156
YOUR_NUMBER=+919413752688
OWNER_PHONE_NUMBER=...
NGROK_URL=https://voice.bizbull.ai
OPENING_GREETING_AUDIO_PATH=assets/opening_greeting.wav
CLOVER_WEBHOOK_SECRET=...
```

### Frontend (build arg, baked into JS bundle)
```env
VITE_SONIOX_VOICE_BOT_WS_URL=wss://voice.bizbull.ai/ws
```

---

## Deployment Workflow

Push from Windows:
```powershell
cd "D:\Chrishan Solution\Soniox"
git add .
git commit -m "your message"
git push
```

Deploy on server:
```bash
cd ~/Soniox
git pull
docker compose up -d --build
```

Python-only changes (faster):
```bash
git pull
docker compose up -d --force-recreate voice-server twilio-bridge
```

---

## Summary

```text
Caddy           = public HTTPS entrypoint, path-based routing
twilio-bridge   = FastAPI: Twilio phone bridge + Clover webhook relay
voice-server    = WebSocket AI engine + Clover POS client
frontend        = React UI for browser testing
Soniox STT      = speech to text (Punjabi / Hindi / English)
OpenAI LLM      = conversation brain
Soniox TTS      = text to speech
Clover POS      = live menu cache + order creation
Docker Compose  = runs all four services
```
