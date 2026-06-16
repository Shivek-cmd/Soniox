# System Architecture

This project runs a phone-based and browser-based restaurant ordering system for Parkash Sweets.
Twilio handles phone calls. Caddy exposes the public HTTPS endpoint. The Twilio bridge converts Twilio's media stream into raw audio. The core voice server runs the AI pipeline and owns the POS connection. The store-api serves the e-commerce Browse Store tab.

**Dual POS:** Both the AI ordering (Sierra) and Browse Store tabs support **Clover** (default) and **Square** POS, switchable via a header dropdown. All WebSocket and REST API endpoints accept `?pos=clover|square`.

`soniox_examples` is tracked directly inside the main `Soniox` repo (not a submodule).

---

## Production Deployment

Five Docker services from `docker-compose.yml` at the repo root:

```text
Internet
  |
  v
voice.bizbull.ai  (Caddy — ports 80/443)
  |
  |-- /ws                → voice-server:8765    (browser WebSocket — AI ordering)
  |-- /store-api/*       → store-api:8766       (store REST API — menu + orders)
  |-- /incoming-call     → twilio-bridge:5050   (Twilio phone call start)
  |-- /transfer-twiml    → twilio-bridge:5050   (call transfer)
  |-- /media-stream      → twilio-bridge:5050   (Twilio audio stream)
  |-- /clover-webhook    → twilio-bridge:5050   (Clover inventory events)
  |-- /*                 → frontend:80          (React UI — both tabs)
```

---

### `caddy`

File: `Caddyfile`

Path-based routing. One public entrypoint covers all five services.

- `/ws` — browser WebSocket to voice server
- `/store-api/*` — strips prefix, proxies to store-api REST API
- `/incoming-call`, `/transfer-twiml`, `/media-stream`, `/clover-webhook` — phone/POS webhook traffic to Twilio bridge
- Everything else — React frontend (serves both the AI tab and Store tab)

Caddy handles HTTPS and auto-renews Let's Encrypt TLS certs. Data stored in `caddy_data` Docker volume.

---

### `voice-server`

File: `soniox_examples/apps/soniox-voice-bot-demo/server/main.py`

Raw Python WebSocket server on port 8765. Not FastAPI.

Responsibilities:
- Accepts WebSocket connections from the Twilio bridge (phone) and browser (frontend)
- Accepts `?pos=clover|square` WebSocket query param — selects POS for each session
- Initialises Clover POS client at startup (required); initialises Square POS client if `SQUARE_ACCESS_TOKEN` is set
- Runs the AI pipeline per session: VAD → STT → LLM → TTS
- Exposes `GET /internal/clover-reload` for the Twilio bridge webhook relay

**POS abstraction:** `square_client.py` mirrors the `CloverClient` interface. `tools.py` functions all accept `pos_client=None`. `state.pos_client` is set per WebSocket session from `?pos=` param.

Key env vars:
```env
SONIOX_API_KEY=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
CLOVER_BASE_URL=https://api.clover.com
CLOVER_MERCHANT_ID=...
CLOVER_ACCESS_TOKEN=...
CLOVER_WEBHOOK_SECRET=...
CLOVER_MENU_POLL_INTERVAL=300
# Square (optional — enables Square POS when set)
SQUARE_BASE_URL=https://connect.squareupsandbox.com
SQUARE_ACCESS_TOKEN=...
SQUARE_LOCATION_ID=...
```

---

### `twilio-bridge`

File: `soniox_examples/apps/soniox-voice-bot-demo/twilio/main.py`

FastAPI app on port 5050.

Responsibilities:
- Receives Twilio webhooks at `/incoming-call`, `/transfer-twiml`, `/media-stream`
- Opens an internal WebSocket to `voice-server:8765` per call
- Forwards caller audio to voice server; converts bot audio (PCM 24kHz → mulaw 8kHz) back to Twilio
- Receives Clover inventory webhooks at `/clover-webhook`, validates HMAC, pings `voice-server:8765/internal/clover-reload`
- Handles call transfer and barge-in

Key env vars:
```env
SONIOX_VOICE_BOT_WS_URL=ws://voice-server:8765
VOICE_SERVER_INTERNAL_URL=http://voice-server:8765
CLOVER_WEBHOOK_SECRET=...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
NGROK_URL=https://voice.bizbull.ai
```

---

### `store-api`

File: `soniox_examples/apps/soniox-voice-bot-demo/store-api/main.py`

FastAPI app on port 8766. Powers the "Browse Store" tab in the React frontend. **All endpoints accept `?pos=clover|square` (default: clover).**

Responsibilities:
- `GET /menu?pos=` — fetches menu from Clover or Square catalog; returns `{ categories, items }` with modifier groups
- `GET /discounts?pos=` — returns active named discounts from Clover or Square catalog
- `POST /checkout?pos=` — **Clover:** creates a Clover Hosted Checkout session; **Square:** creates a Square Payment Link; both return `{ checkout_url, ... }`. Frontend redirects to `checkout_url`; POS handles card entry and redirects back to `FRONTEND_URL?payment=success`.
- `POST /orders?pos=` — creates an order in Clover or Square (no payment; used by voice-server AI tab path)
- `GET /orders/{id}?pos=` — polls order state from Clover or Square
- `GET /health` — liveness probe; returns `{ ok, clover, square, merchant_id, location_id }`

Caddy strips `/store-api` prefix before forwarding, so the service receives requests at `/menu`, `/orders`, etc.

Key env vars:
```env
CLOVER_BASE_URL=https://api.clover.com
CLOVER_MERCHANT_ID=...
CLOVER_ACCESS_TOKEN=...
CLOVER_ECOM_KEY=...                     # Hosted Checkout ecommerce token
SQUARE_BASE_URL=https://connect.squareupsandbox.com
SQUARE_ACCESS_TOKEN=...
SQUARE_LOCATION_ID=...
FRONTEND_URL=https://voice.bizbull.ai   # used for checkout redirect URLs
```

**Payment — Clover:** Implemented via Clover Hosted Checkout redirect flow.
- Endpoint: `POST {CLOVER_BASE_URL}/invoicingcheckoutservice/v1/checkouts`
- Auth: `Authorization: Bearer {CLOVER_ECOM_KEY}` + `X-Clover-Merchant-Id` header (merchant is NOT in the request body)
- On success Clover redirects to `FRONTEND_URL?payment=success`; frontend detects this on load and switches to the Store tab to show the success overlay
- Test card: `4111 1111 1111 1111`, any future expiry, any CVV
- To go live: replace `CLOVER_BASE_URL` with `https://api.clover.com` and create a new `CLOVER_ECOM_KEY` from the production Clover dashboard

**`CLOVER_ECOM_KEY`** is a separate credential from `CLOVER_ACCESS_TOKEN`. Get it from the Clover merchant dashboard → Account & Setup → Ecommerce API Tokens → Create new token → select **"Hosted checkout"** → copy the Private token. Must be created from the **same environment** (sandbox or production) as `CLOVER_BASE_URL`. Setting manually in `.env` is more reliable than PAKMS auto-fetch (PAKMS returns 404 on most sandbox accounts).

---

### `frontend`

File: `soniox_examples/apps/soniox-voice-bot-demo/frontend/`

React + Vite app, served via nginx on port 80.

**POS dropdown** in the header (persisted in localStorage) controls both tabs simultaneously — switching from Clover to Square reloads the menu in both the Store and the MenuPanel in the AI tab.

Two tabs:
- **Order with Sierra** — AI voice ordering (Sierra avatar, menu panel, live order/receipt). MenuPanel fetches `/store-api/menu?pos=...` dynamically. Bottom bar has language selector + Start/End call button.
- **Browse Store** — e-commerce store: category filter, search, item grid, cart sidebar, item modal (modifier selection), checkout modal with promo code input → redirects to Clover Hosted Checkout or Square Payment Link for payment → success overlay on return.

**Mobile:** Fully responsive. Desktop tab switcher in header. Mobile: fixed bottom nav bar (64px); cart shown as floating amber FAB + slide-up bottom sheet; modals are full-screen. `useIsMobile(640)` hook drives layout switching.

`VITE_SONIOX_VOICE_BOT_WS_URL` is a **build-time arg** baked into the JS bundle — must be set to `wss://voice.bizbull.ai/ws` before building. `VITE_STORE_API_URL` defaults to `/store-api` (correct for production via Caddy proxy) and does not need to be set.

If the store-api is unreachable on startup, the Store tab silently falls back to the static `menu.json` data so the UI still loads.

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

## Store Order Flow

```text
Customer opens voice.bizbull.ai → clicks "Browse Store" tab
  |
  | GET /store-api/menu  (+ GET /store-api/discounts for promo code list)
  v
Caddy strips prefix → store-api:8766
  |
  | GET https://api.clover.com/v3/merchants/{id}/items?expand=categories,modifierGroups
  v
Returns item list → React renders category grid (photos from Unsplash fallback,
                                                  sold-out items greyed out)

Customer browses → adds items to cart (pure frontend state, useReducer)
  |
Customer clicks "Place Order" → fills name/phone/type/note
  |   (optionally enters promo code → matched against /discounts list)
  |
  | POST /store-api/checkout  { items, order_type, customer_name, discount_code? }
  v
store-api:
  → validates discount via GET /v3/merchants/{id}/discounts (if code provided)
  → POST /invoicingcheckoutservice/v1/checkouts  (Clover Hosted Checkout)
     redirectUrls: { success: FRONTEND_URL?payment=success,
                     cancel:  FRONTEND_URL?payment=cancelled }
  → returns { checkout_url, session_id, discount_amount, discount_name }
  |
Frontend:
  → saves { session_id, total, discount_amount, discount_name } to sessionStorage
  → window.location.href = checkout_url   (navigates to Clover payment page)
  |
Customer enters card on Clover-hosted page → payment processed
  |
Clover redirects back → voice.bizbull.ai?payment=success (or ?payment=cancelled)
  |
Frontend:
  → reads sessionStorage, restores order summary
  → clears cart (CLEAR action)
  → shows SuccessOverlay with total paid + savings banner if promo was used
Order appears in Clover POS dashboard / kitchen display immediately
```

---

## Clover Webhook Flow (inventory sync for AI tab)

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
voice-server MenuCache.replace_all(raw_items)
  → all new AI sessions use updated prices
```

Note: The store-api fetches fresh data from Clover on every `/menu` request — no caching layer, so it always reflects the latest prices without needing webhook-triggered reloads.

---

## Core Voice Pipeline (AI Tab)

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
File: `server/processors/vad.py` — Silero VAD. Detects speech start/end. Enables barge-in.

### 2. `STTProcessor`
File: `server/processors/stt.py` — Streams audio to Soniox real-time STT. Language hints: `["pa", "hi", "en"]`.

### 3. `LLMProcessor`
File: `server/processors/llm.py` — Sends transcriptions to OpenAI, streams response to TTS. Calls tools (`place_order`, `get_menu`, `check_item_availability`, `select_language`, `transfer_call`).

### 4. `DynamicTTSProcessor`
Defined in: `server/main.py`
- Lazy TTS WebSocket connect (on first use)
- Time-based reconnect if idle >45s
- Up to 3 retry attempts on Soniox handshake timeout
- Dead stream ID recovery if Soniox returns 408/400

---

## Environment Variables

All variables are in root `.env` and substituted by `docker-compose.yml`.

### voice-server
```env
SONIOX_API_KEY=...
SONIOX_STT_MODEL=stt-rt-v5
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
# Square (optional)
SQUARE_BASE_URL=https://connect.squareupsandbox.com
SQUARE_ACCESS_TOKEN=...
SQUARE_LOCATION_ID=...
```

### twilio-bridge
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

### store-api
```env
CLOVER_BASE_URL=https://api.clover.com        # or https://apisandbox.dev.clover.com for sandbox
CLOVER_MERCHANT_ID=...
CLOVER_ACCESS_TOKEN=...
CLOVER_ECOM_KEY=...                           # Ecommerce API token (Hosted Checkout type) from Clover dashboard
SQUARE_BASE_URL=https://connect.squareupsandbox.com
SQUARE_ACCESS_TOKEN=...
SQUARE_LOCATION_ID=...
FRONTEND_URL=https://voice.bizbull.ai         # Checkout redirect base URL (both Clover + Square)
```

### frontend (build-time args only — baked into JS bundle)
```env
VITE_SONIOX_VOICE_BOT_WS_URL=wss://voice.bizbull.ai/ws
# VITE_STORE_API_URL not needed in prod — defaults to /store-api via Caddy
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

Deploy on server (full rebuild):
```bash
cd ~/Soniox
git pull
docker compose up -d --build
```

Store-api only (fastest — when only store-api Python changed):
```bash
git pull
docker compose up -d --force-recreate store-api
```

Python-only AI changes (skips frontend rebuild):
```bash
git pull
docker compose up -d --force-recreate voice-server twilio-bridge
```

Switch store-api from sandbox to production Clover (when ready):
```bash
nano ~/Soniox/.env
# Change: CLOVER_BASE_URL=https://apisandbox.dev.clover.com
# To:     CLOVER_BASE_URL=https://api.clover.com
docker compose up -d --force-recreate store-api
```

---

## Summary

```text
Caddy           = public HTTPS entrypoint, path-based routing to all 5 services
twilio-bridge   = FastAPI: Twilio phone bridge + Clover inventory webhook relay
voice-server    = WebSocket AI engine: VAD + STT + LLM + TTS + Clover/Square POS client (?pos=)
store-api       = FastAPI: dual-POS e-commerce REST API — menu, discounts, checkout (?pos=)
frontend        = React UI — POS dropdown + two tabs: AI ordering (Sierra) + Browse Store
Soniox STT/TTS  = speech-to-text and text-to-speech (Punjabi / Hindi / English)
OpenAI LLM      = conversation brain (gpt-4o-mini)
Clover POS      = live menu + order creation (default POS)
Square POS      = optional POS — Payment Links checkout; sandbox catalog has 20 bakery items
Docker Compose  = runs all five services
```
