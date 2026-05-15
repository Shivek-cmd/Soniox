# Soniox Official Voice Agent Demo — Reference

Source: https://github.com/soniox/soniox_examples/tree/main/apps/soniox-voice-bot-demo

This is Soniox's own voice agent implementation. We use this as our base reference.
Our restaurant agent is an adaptation of this — same architecture, different tools + system prompt.

---

## Architecture

```
[Browser / Phone (Twilio)]
          ↓ WebSocket (raw audio bytes)
[Voice Bot Server — Python WebSocket server]
    ├── VADProcessor     → detects when user starts/stops speaking
    ├── STTProcessor     → Soniox STT → transcript
    ├── LLMProcessor     → OpenAI GPT → response text
    └── TTSProcessor     → Soniox TTS → audio bytes
          ↓ WebSocket (audio bytes back)
[Browser / Phone]
```

For phone calls, a separate **Twilio Bridge** sits between Twilio and the voice bot:
```
[Customer Phone] → Twilio → [Twilio Bridge (FastAPI)] → [Voice Bot Server]
```

---

## Two Separate Services

### 1. Voice Bot Server (`server/`)
- Python WebSocket server (port 8765 by default)
- Handles the full STT → LLM → TTS pipeline
- Connects to: Soniox API, OpenAI API

### 2. Twilio Bridge (`twilio/`)
- FastAPI server (port 5050 by default)
- Receives incoming Twilio calls
- Bridges Twilio's audio stream ↔ Voice Bot Server
- Handles audio format conversion (mulaw 8kHz ↔ PCM 24kHz)

---

## Key Files

### `server/main.py` — WebSocket server entry point
```python
# Pipeline per connection:
processors = [
    VADProcessor(sample_rate=16000),
    STTProcessor(api_key=SONIOX_API_KEY, language_hints=["en"]),
    LLMProcessor(api_key=OPENAI_API_KEY, model="gpt-4o-mini", system_message=..., tools=...),
    TTSProcessor(api_key=SONIOX_API_KEY, language="en", voice="female_1"),
]
session = Session(processors, websocket)
await session.run()
```

### `server/tools.py` — Where to customize for your business

This is the ONLY file you need to change for a different business. It has:

1. **`get_system_message()`** — the agent's personality and instructions
2. **Tool functions** — what the agent can DO (call APIs, databases)

For our restaurant, we replace:
| Demo (AutoWorks) | Ours (Restaurant) |
|-----------------|-------------------|
| `search_knowledge_base` | `get_menu` |
| `check_availability` | `check_item_availability` |
| `create_appointment` | `place_order` |

### `twilio/main.py` — Twilio bridge (the phone call handler)

Key parts:
```python
# When call comes in → return TwiML to stream audio to our server
@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=f"wss://{host}/media-stream")
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")

# Bridge: Twilio audio ↔ Voice Bot Server
@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    # Connects to voice bot server, forwards audio both ways
    # Handles interruption via Twilio "mark" events
    # Converts: PCM 24kHz → mulaw 8kHz (for Twilio playback)
```

---

## Audio Format Flow

```
Twilio → Bridge:    mulaw, 8kHz, mono  (base64 encoded in JSON)
Bridge → VoiceBot:  mulaw, 8kHz, mono  (raw bytes)
VoiceBot processes: PCM 16kHz, mono    (Soniox STT expects this)
VoiceBot TTS out:   PCM 24kHz, mono    (Soniox TTS produces this)
VoiceBot → Bridge:  PCM 24kHz, mono
Bridge → Twilio:    mulaw, 8kHz, mono  (converted back)
```

**Conversion used** (Python `audioop`):
```python
# PCM 24kHz → mulaw 8kHz (for sending to Twilio)
pcm_8k = audioop.ratecv(pcm_24k, 2, 1, 24000, 8000, None)[0]
ulaw = audioop.lin2ulaw(pcm_8k, 2)
```

---

## Interruption Handling (Barge-in)

The Twilio bridge uses Twilio's "mark" system:
1. Every time agent audio is sent → a "mark" message is added to `mark_queue`
2. If customer speaks while agent is talking → `transcription` event fires
3. Bridge sends `{"event": "clear"}` to Twilio → cuts off agent audio mid-sentence
4. Clears `mark_queue`

This is what makes it feel like a real conversation.

---

## Environment Variables

### Voice Bot Server (`server/.env`)
```
SONIOX_API_KEY=...
OPENAI_API_KEY=...          # or replace with Anthropic
OPENAI_MODEL=gpt-4o-mini
WEBSOCKET_HOST=localhost
WEBSOCKET_PORT=8765
```

### Twilio Bridge (`twilio/.env`)
```
PORT=5050
SONIOX_VOICE_BOT_WS_URL=ws://localhost:8765   # voice bot server URL
VOICE_BOT_LANGUAGE=pa                          # pa = Punjabi
VOICE_BOT_VOICE=female_1
```

---

## What We Change for Restaurant

1. **`tools.py`** — Replace AutoWorks tools with restaurant tools:
   - `get_menu()` — return the restaurant's menu
   - `place_order(items, customer_name, phone)` → save to DB + send WhatsApp
   - `check_item_availability(item)` — is it in stock today?

2. **`get_system_message()`** — Replace AutoWorks persona with restaurant persona:
   - Restaurant name, cuisine type
   - Instructions to take orders
   - Punjabi/English language instructions

3. **LLM** — Switch from OpenAI to Claude (Anthropic) if preferred

4. **Language** — Set `language_hints=["pa", "en"]` for Punjabi + English

Everything else stays exactly the same.

---

## Stack Correction (Important)

Soniox's own demo uses **Python** for the voice agent server.
Node.js SDK is for the **browser/frontend** side (React app).

Updated stack:
| Layer | Tool |
|-------|------|
| Voice bot server | Python (websockets, asyncio) |
| Twilio bridge | Python (FastAPI) |
| Frontend (optional) | React + @soniox/react |
| STT + TTS | Soniox Python SDK |
| LLM | Claude or GPT-4o |
| Phone calls | Twilio |
