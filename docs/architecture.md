# Voice Agent Architecture

This project runs a phone-based restaurant voice agent. Twilio handles the phone call, Caddy exposes the public HTTPS endpoint, the Twilio bridge converts Twilio's media stream into raw audio, and the core voice server runs the AI pipeline.

`soniox_examples` is now tracked directly inside the main `Soniox` repo. It is no longer a Git submodule.

---

## Production Deployment

The server runs three Docker services from `docker-compose.yml`:

```text
Internet
  |
  v
voice.bizbull.ai
  |
  v
caddy
  |
  v
twilio-bridge:5050
  |
  v
voice-server:8765
```

### `caddy`

Caddy is the public-facing reverse proxy.

File:

```text
Caddyfile
```

Current config:

```text
voice.bizbull.ai {
    reverse_proxy twilio-bridge:5050
}
```

Responsibilities:

- Listens on public ports `80` and `443`
- Provides HTTPS for `voice.bizbull.ai`
- Forwards all traffic to the internal `twilio-bridge` container
- Stores TLS data in the `caddy_data` Docker volume

### `twilio-bridge`

The Twilio bridge is a FastAPI app.

File:

```text
soniox_examples/apps/soniox-voice-bot-demo/twilio/main.py
```

Docker service:

```yaml
twilio-bridge:
  environment:
    - SONIOX_VOICE_BOT_WS_URL=ws://voice-server:8765
    - VOICE_BOT_LANGUAGE=pa
    - VOICE_BOT_VOICE=Maya
```

Responsibilities:

- Receives Twilio webhook requests at `/incoming-call`
- Returns TwiML that tells Twilio to open a WebSocket stream
- Receives Twilio audio at `/media-stream`
- Opens an internal WebSocket connection to `voice-server`
- Forwards caller audio to the voice server
- Converts bot audio back into Twilio's required format
- Sends the bot voice back to the phone call

### `voice-server`

The voice server is the core AI server.

File:

```text
soniox_examples/apps/soniox-voice-bot-demo/server/main.py
```

It is not FastAPI. It is a raw WebSocket server using Python `websockets`.

Docker service:

```yaml
voice-server:
  environment:
    - SONIOX_API_KEY=${SONIOX_API_KEY}
    - OPENAI_API_KEY=${OPENAI_API_KEY}
    - OPENAI_MODEL=gpt-4o-mini
    - WEBSOCKET_HOST=0.0.0.0
    - WEBSOCKET_PORT=8765
```

Responsibilities:

- Accepts WebSocket connections from the Twilio bridge
- Receives live caller audio
- Runs the voice pipeline: VAD, STT, LLM, TTS
- Streams generated bot audio back to the bridge

---

## Phone Call Flow

```text
Customer phone call
  |
  v
Twilio phone number
  |
  | POST https://voice.bizbull.ai/incoming-call
  v
Caddy
  |
  v
twilio-bridge /incoming-call
  |
  | returns TwiML with wss://voice.bizbull.ai/media-stream
  v
Twilio opens media WebSocket
  |
  v
twilio-bridge /media-stream
  |
  | ws://voice-server:8765?audio_in_format=mulaw&audio_in_sample_rate=8000&...
  v
voice-server
  |
  | VAD -> Soniox STT -> OpenAI LLM -> Soniox TTS
  v
twilio-bridge
  |
  | converts PCM 24kHz audio to mulaw 8kHz
  v
Twilio
  |
  v
Customer hears the agent
```

---

## Core Voice Pipeline

Every live call becomes one WebSocket session in `voice-server`.

The server creates this processor chain:

```python
processors = [
    VADProcessor(...),
    STTProcessor(...),
    LLMProcessor(...),
    DynamicTTSProcessor(...),
]
```

Then it runs:

```python
session = Session(processors, websocket)
await session.run()
```

### 1. `VADProcessor`

File:

```text
server/processors/vad.py
```

Purpose:

- Detects when the caller starts speaking
- Detects when the caller stops speaking
- Helps support interruption while the bot is talking

### 2. `STTProcessor`

File:

```text
server/processors/stt.py
```

Purpose:

- Streams caller audio to Soniox speech-to-text
- Uses restaurant vocabulary context from `STT_CONTEXT`
- Produces transcription messages for the LLM

Current speech context includes restaurant terms such as:

```text
Butter Chicken, Chicken Tikka Masala, Dal Makhani, Garlic Naan,
Basmati Rice, Mango Lassi, pickup, delivery
```

Current language hints:

```python
["pa", "hi", "en"]
```

That means the bot is tuned for Punjabi, Hindi, and English input.

### 3. `LLMProcessor`

File:

```text
server/processors/llm.py
```

Purpose:

- Sends a fixed English opening greeting as soon as the call starts
- Sends the customer transcript to OpenAI
- Uses `gpt-4o-mini` by default
- Applies the restaurant system prompt from `tools.py`
- Uses restaurant tools from `get_tools(state)`
- Streams response text toward TTS

The LLM owns the conversation brain after the opening greeting: language selection, menu understanding, order collection, confirmation, and tool calls.

Current opening greeting:

```text
Hi! This is Sierra calling from Bizbull Restaurant. Would you like to continue in English, Hindi, or Punjabi?
```

### 4. `DynamicTTSProcessor`

Defined in:

```text
server/main.py
```

It extends the normal Soniox `TTSProcessor`.

Purpose:

- Converts the LLM response text into voice audio
- Reads current language and voice from `RestaurantState`
- Allows the bot to switch TTS language/voice during the call when tools update state

---

## Restaurant State And Tools

Restaurant-specific behavior lives mainly in:

```text
soniox_examples/apps/soniox-voice-bot-demo/server/tools.py
```

Important pieces:

- `RestaurantState`
- `get_system_message(...)`
- `get_tools(state)`

`RestaurantState` stores call-level information such as selected language, TTS language, TTS voice, and order details.

`get_system_message(...)` creates the restaurant agent instructions.

`get_tools(state)` exposes callable tools to the LLM so it can manage restaurant-specific actions instead of only chatting freely.

---

## Audio Formats

Twilio and Soniox use different audio formats, so the bridge handles conversion.

| Stage | Format |
| --- | --- |
| Twilio to bridge | mulaw, 8kHz, mono, base64 JSON payload |
| Bridge to voice-server | mulaw, 8kHz, mono, raw bytes |
| Voice-server STT input | configured from WebSocket query params |
| Soniox TTS output | PCM, 24kHz, mono |
| Voice-server to bridge | PCM, 24kHz audio bytes |
| Bridge to Twilio | mulaw, 8kHz, mono, base64 JSON payload |

Conversion happens in `twilio/main.py`:

```python
pcm_audio_bytes_8k = audioop.ratecv(
    pcm_audio_bytes, 2, 1, 24000, 8000, None
)[0]
ulaw_audio_bytes = audioop.lin2ulaw(pcm_audio_bytes_8k, 2)
```

---

## Interruption Handling

The system supports basic barge-in, meaning the caller can interrupt the bot while it is speaking.

How it works:

1. The voice server sends transcription events back to the Twilio bridge.
2. The bridge tracks whether bot audio is still queued using Twilio `mark` messages.
3. When caller speech is detected while bot audio is pending, the bridge sends:

```json
{"event": "clear"}
```

Twilio then clears queued bot audio so the caller does not have to wait for the previous response to finish.

---

## Environment Variables

Main runtime variables are configured in `docker-compose.yml` and `.env`.

### Voice server

```env
SONIOX_API_KEY=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
SONIOX_STT_MODEL=stt-rt-v4
SONIOX_TTS_MODEL=tts-rt-v1
LLM_TEMPERATURE=0.85
LLM_MAX_TOKENS=120
WEBSOCKET_HOST=0.0.0.0
WEBSOCKET_PORT=8765
```

### Twilio bridge

```env
SONIOX_VOICE_BOT_WS_URL=ws://voice-server:8765
VOICE_BOT_LANGUAGE=pa
VOICE_BOT_VOICE=Maya
```

### Test call script

The local test call script is:

```text
soniox_examples/apps/soniox-voice-bot-demo/twilio/make_call.py
```

It reads Twilio values from environment variables:

```env
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_NUMBER=...
YOUR_NUMBER=...
NGROK_URL=...
```

Do not hard-code Twilio credentials in Python files.

---

## Local Browser Testing

The original Soniox demo also includes a browser frontend:

```text
soniox_examples/apps/soniox-voice-bot-demo/frontend
```

For browser testing, the flow is different:

```text
Browser microphone
  |
  v
voice-server WebSocket
  |
  v
VAD -> STT -> LLM -> TTS
  |
  v
Browser audio playback
```

The production phone deployment does not expose this frontend through Caddy. Production traffic goes through Twilio and the `twilio-bridge`.

---

## Deployment Workflow

The project is now one repo.

Local Windows workflow:

```powershell
cd "D:\Chrishan Solution\Soniox"
git add .
git commit -m "your message"
git push
```

Server workflow:

```bash
cd ~/Soniox
git pull
docker compose up -d --build
```

For a quicker restart after Python-only changes:

```bash
cd ~/Soniox
git pull
docker compose up -d --force-recreate voice-server twilio-bridge
```

---

## Summary

Short version:

```text
Caddy = public HTTPS entrypoint
Twilio bridge = FastAPI app that talks to Twilio
Voice server = WebSocket AI engine
Soniox STT = speech to text
OpenAI = restaurant conversation brain
Soniox TTS = text to speech
Docker Compose = runs all services together
```
