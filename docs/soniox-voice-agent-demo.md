# Parkash Sweets — Voice Agent Reference

Based on Soniox's official demo: https://github.com/soniox/soniox_examples/tree/main/apps/soniox-voice-bot-demo

This is the full implementation reference for our restaurant voice agent. Two access modes:
- **Phone** — customer calls a Twilio number, Twilio bridge connects them to the voice bot
- **Browser** — customer opens the React web app, clicks "Start call", speaks directly

---

## Architecture

```
PHONE PATH:
[Customer Phone]
    → Twilio PSTN
    → [Twilio Bridge — FastAPI :5050]
        (extracts caller phone, mulaw 8kHz ↔ voice bot, barge-in, call transfer)
    → [Voice Bot Server — WebSocket :8765]
        → VAD → STT (Soniox) → LLM (GPT-4o-mini) → TTS (Soniox)
    → [n8n webhook]  (on order placed)
    → [Owner phone via Twilio REST]  (on transfer)

BROWSER PATH:
[Browser] → React frontend (Vite :5173)
    ← PCM audio + JSON events →
[Voice Bot Server — WebSocket :8765]
    → same VAD → STT → LLM → TTS pipeline
    → order_confirmed WS event → receipt card shown in UI
```

### Pipeline (per call/session)
```
[Audio in]
    → VADProcessor        detects speech start/end
    → STTProcessor        Soniox STT → transcript
    → LLMProcessor        GPT-4o-mini → response text + tool calls
    → DynamicTTSProcessor Soniox TTS → PCM audio out
[Audio out]
```

---

## Three Services

### 1. Voice Bot Server — `server/` (port 8765)
Python WebSocket server. Handles the full STT → LLM → TTS pipeline. Accepts both raw PCM (browser) and mulaw (Twilio bridge) via query params.

**Query params accepted:**
```
?language=pa&voice=Maya
&audio_in_format=mulaw&audio_in_sample_rate=8000&audio_in_num_channels=1
&skip_opening_greeting=true
&caller_phone=+16131234567
```

### 2. Twilio Bridge — `twilio/` (port 5050)
FastAPI server. Sits between Twilio and the voice bot server. Handles phone-specific concerns: audio format conversion, barge-in, caller ID extraction, call transfer.

### 3. React Frontend — `frontend/` (port 5173)
Vite + React 19 + TypeScript + Tailwind CSS v4. Used for browser-based voice ordering. Connects directly to voice bot server via WebSocket. Shows real-time chat, full browseable menu, and live order tracking with receipt.

---

## Key Files

### `server/tools.py` — The only file customized per business

Contains:
1. `get_system_message()` — Sierra's full personality and call flow instructions
2. `RestaurantState` — mutable per-call state (TTS language/voice, transfer flag, confirmed order, caller phone)
3. 5 tools the LLM can call:
   - `transfer_call(reason)` — escalates to human staff
   - `select_language(language)` — switches TTS voice/language mid-call
   - `get_menu(category)` — returns menu items
   - `check_item_availability(item_name)` — checks menu
   - `place_order(...)` — confirms order, posts to n8n webhook
   - *(TODO: `book_table(...)` — referenced in system prompt Workflow 2, not yet implemented)*

### `server/main.py` — WebSocket server entry point

Key customizations beyond the base demo:
- `DynamicTTSProcessor` — subclasses `TTSProcessor`, reads `state.tts_language`/`state.tts_voice` at each new TTS stream start so language switching takes effect immediately. Also fires `OrderConfirmedMessage` or `TransferCallMessage` after TTS audio finishes playing.
- `QueryParams` — parses `language`, `voice`, `audio_in_format`, `caller_phone`, `skip_opening_greeting`
- STT language hints are dynamic: English → `["en"]`, Hindi → `["hi", "en"]`, Punjabi → `["pa", "hi", "en"]`
- STT context includes domain hints + all 80+ menu item names for better recognition

```python
processors = [
    VADProcessor(sample_rate=params.audio_in_sample_rate),
    STTProcessor(api_key=SONIOX_API_KEY, model="stt-rt-v4", language_hints=stt_hints, context=STT_CONTEXT),
    LLMProcessor(api_key=OPENAI_API_KEY, model="gpt-4o-mini", system_message=..., tools=get_tools(state)),
    DynamicTTSProcessor(state=state, api_key=SONIOX_API_KEY, model="tts-rt-v1", language=..., voice=...),
]
session = Session(processors, websocket)
await session.run()
```

### `twilio/main.py` — Twilio bridge

- `/incoming-call` — returns TwiML to stream audio to `/media-stream`; extracts `From` (caller phone) and passes it as `?caller_phone=` to voice bot
- `/media-stream` — WebSocket: bridges Twilio audio ↔ voice bot, handles barge-in and call transfer
- `/transfer-twiml` — TwiML for redirecting call to `OWNER_PHONE_NUMBER`
- Cached opening greeting: if `OPENING_GREETING_AUDIO_PATH` is set, plays pre-generated WAV immediately on call start (bypasses TTS latency for first message)

### `twilio/generate_opening_greeting.py`
One-off script to pre-generate the opening greeting as a WAV file using Soniox TTS. Run once, commit the file, set `OPENING_GREETING_AUDIO_PATH` in `.env`.

```bash
python generate_opening_greeting.py
# Writes: assets/opening_greeting.wav
```

### `frontend/src/components/conversation.tsx` — Main UI orchestrator
Manages the WebSocket connection, microphone, audio playback, and the 3-column layout. Also contains inline: `OrderColumn`, `SierraFloat`, `ReceiptCard`, `StatusDot`.

### `frontend/src/utils/menuData.ts` — Client-side menu + order parsing
- `MENU_CATEGORIES` — full menu for display in MenuPanel (names, descriptions, prices)
- Flat `MENU` with `terms[]` — for real-time order detection
- `parseOrderFromBotMessages()` — regex-matches "N item_name" in bot text as order builds
- `parseConversationDetails()` — extracts name, phone, order type, instructions from running transcript

### `frontend/src/utils/messages.ts` — WS message contracts
Zod schemas for all message types. `updateMessages()` accumulates streaming transcription and LLM response chunks.

---

## Audio Format Flow

```
PHONE:
  Twilio → Bridge:      mulaw 8kHz, base64-encoded JSON
  Bridge → VoiceBot:    mulaw 8kHz, raw bytes
  VoiceBot → Bridge:    PCM 24kHz, raw bytes
  Bridge → Twilio:      mulaw 8kHz  (audioop.ratecv + audioop.lin2ulaw)

BROWSER:
  Browser → VoiceBot:   PCM 16kHz (from useMicrophone.ts → AudioWorklet)
  VoiceBot → Browser:   PCM 24kHz raw bytes → addAudioChunk() → AudioWorklet playback
```

---

## WebSocket Events (Voice Bot Server → Client)

| Event | Payload | Description |
|-------|---------|-------------|
| `session_start` | — | Connection established |
| `transcription` | `{final_text, non_final_text}` | STT result (streaming) |
| `llm_response` | `{text}` | LLM response chunk |
| `user_speech_start` | — | VAD detected speech start |
| `user_speech_end` | — | VAD detected speech end |
| `order_confirmed` | `{order_id, customer_name, phone_number, order_type, items[], total_amount, wait_time, special_instructions}` | Fired after TTS finishes playing confirmation |
| `transfer` | `{reason}` | Call transfer requested — Twilio bridge acts on this |
| binary | PCM 24kHz bytes | TTS audio chunks |

---

## Barge-in (Interruption)

**Phone:** Twilio bridge tracks a `mark_queue`. On `user_speech_start` or `transcription` from voice bot → sends `{"event":"clear"}` to Twilio → cuts off agent audio mid-sentence.

**Browser:** `useAudioChunkPlayer.ts` has `interruptAudio()`. On `user_speech_start` from voice bot → stops all queued audio immediately.

---

## Frontend Layout Detail

```
┌────────────────────────────────────────────────────────────┐
│  Header: [P] Parkash Sweets · AI Voice Ordering   ● Online │
├────────────────────┬──────────────────┬────────────────────┤
│  Chat (38%)        │  Menu (34%)      │  Order (28%)       │
│  ─ Status bar      │  ─ "Full Menu"   │  ─ "Your Order"    │
│  ─ Chat bubbles:   │  ─ Category pills│  ACTIVE:           │
│    User = amber    │    (scrollable)  │  "Building Order…" │
│    Sierra = surface│  ─ Items w/desc  │  + real-time items │
│                    │    + price       │  + name/phone/type  │
│                    │                  │  CONFIRMED:         │
│                    │                  │  Receipt card       │
│                    │                  │  (paper style, GST) │
├────────────────────┴──────────────────┴────────────────────┤
│  [Punjabi ▾]                           [🎙 Start call]     │
└────────────────────────────────────────────────────────────┘
                                      ↗ Sierra floating circle
                                         (bottom-right, abs)
```

**Sierra floating circle**: 56×56px amber "S" circle. Pulse rings while speaking. Wave bars while listening. Tooltip shows "Sierra is speaking…" / "Listening…" / "Thinking…".

**Receipt card**: Shows after order_confirmed. Paper-style white card with: restaurant header, order ID + date/time, customer info, items table (qty × price), subtotal + GST 5% + total, special instructions, thank you footer.

**Components not wired into current layout** (built, available for future use):
- `AvatarPanel.tsx` — large centered Sierra avatar with animated rings and waveform
- `OrderPanel.tsx` — standalone order panel with `embedded` prop for inline use

---

## Call Transfer Flow (Phone only)

1. LLM calls `transfer_call(reason)` → sets `state.transfer_requested = True`
2. Sierra says the transfer message in the customer's language, TTS plays it
3. After TTS stream finalizes → `DynamicTTSProcessor._on_stream_finalized()` fires `TransferCallMessage`
4. Twilio bridge receives `{"type": "transfer", "reason": "..."}` over WS
5. Calls Twilio REST: `client.calls(call_sid).update(url=f"{NGROK_URL}/transfer-twiml")`
6. `/transfer-twiml` returns TwiML that dials `OWNER_PHONE_NUMBER`

---

## Order Placement Flow

1. LLM calls `place_order(customer_name, phone_number, items, total_amount, order_type, ...)`
2. `place_order()` validates all items against menu, calculates real total, generates `order_id = PS-HHMMSS`
3. Posts to `N8N_WEBHOOK_URL` (if set) with full order payload
4. Returns success + sets `state.confirmed_order`
5. After TTS finishes → fires `OrderConfirmedMessage` → sent to client as `order_confirmed` WS event
6. Frontend shows receipt card (or Twilio bridge could use it for logging)

---

## How to Run Locally

```bash
# Terminal 1 — Voice bot server (required for both phone + browser)
cd soniox_examples/apps/soniox-voice-bot-demo/server
cp .env.example .env          # fill in SONIOX_API_KEY, OPENAI_API_KEY
python main.py                # starts on ws://localhost:8765

# Terminal 2 — React frontend (browser access)
cd soniox_examples/apps/soniox-voice-bot-demo/frontend
# .env already has: VITE_SONIOX_VOICE_BOT_WS_URL=ws://localhost:8765
npm install && npm run dev    # http://localhost:5173

# Terminal 3 — Twilio bridge (phone access only)
cd soniox_examples/apps/soniox-voice-bot-demo/twilio
cp .env.example .env          # fill in Twilio creds, OWNER_PHONE_NUMBER, etc.
python main.py                # starts on http://localhost:5050
# + in another terminal: ngrok http 5050
# + set webhook in Twilio console: https://<ngrok>.ngrok.io/incoming-call
```

---

## Environment Variables

```bash
# server/.env
SONIOX_API_KEY=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
WEBSOCKET_HOST=localhost
WEBSOCKET_PORT=8765
N8N_WEBHOOK_URL=...              # optional — order webhook

# twilio/.env
PORT=5050
SONIOX_VOICE_BOT_WS_URL=ws://localhost:8765
VOICE_BOT_LANGUAGE=pa            # pa / hi / en (default language for Twilio calls)
VOICE_BOT_VOICE=Maya
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
OWNER_PHONE_NUMBER=+1...         # where to transfer calls
NGROK_URL=https://xxxx.ngrok.io  # your ngrok URL
OPENING_GREETING_AUDIO_PATH=     # optional — path to pre-generated WAV

# frontend/.env
VITE_SONIOX_VOICE_BOT_WS_URL=ws://localhost:8765
```

---

## What We Changed vs Soniox Base Demo

| Base Demo (AutoWorks) | Our Version (Parkash Sweets) |
|----------------------|------------------------------|
| Generic tools (search_kb, check_availability, create_appointment) | Restaurant tools: get_menu, check_item_availability, place_order, select_language, transfer_call |
| Single language (English) | Trilingual: Punjabi + Hindi + English, mid-call switching |
| No caller ID | Caller phone from Twilio `From` header → system prompt |
| No order confirmation events | `OrderConfirmedMessage` fires after TTS, received by frontend |
| No call transfer | Full transfer to owner via Twilio REST API |
| No cached greeting | Pre-generated WAV greeting (zero TTS latency on first message) |
| Generic frontend | Parkash Sweets branded: 3-col layout, menu panel, receipt card, Sierra avatar |
| No real-time order parsing | `parseOrderFromBotMessages()` + local fallback receipt |
