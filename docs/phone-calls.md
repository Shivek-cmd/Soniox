# How Phone Calls Work (Twilio Bridge)

## Overview

The `twilio/main.py` is a thin bridge — it doesn't do any AI processing.
It just connects Twilio's phone call audio to the Voice Bot Server.

```
Customer Phone → Twilio → [twilio/main.py] → [server/main.py]
                                ↑ bridge ↑
```

---

## What Happens Step by Step

1. Customer dials your Twilio phone number
2. Twilio sends HTTP POST to `yourserver.com/incoming-call`
3. Bridge responds with TwiML: "stream audio to wss://yourserver.com/media-stream"
4. Twilio opens WebSocket to bridge, streams audio
5. Bridge opens WebSocket to Voice Bot Server (port 8765)
6. Bridge forwards audio both ways between Twilio ↔ Voice Bot
7. Bridge converts audio formats on the way back (PCM 24kHz → mulaw 8kHz)

---

## Key Code in `twilio/main.py`

### Incoming call webhook
```python
@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=f"wss://{host}/media-stream")
    response.append(connect)
    return HTMLResponse(content=str(response), media_type="application/xml")
```

### Audio bridge
```python
@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    # Connects to voice bot: ws://localhost:8765?language=pa&voice=female_1
    # Forwards Twilio audio → voice bot
    # Converts voice bot audio → mulaw → sends back to Twilio
```

### Interruption (barge-in)
```python
# When transcription arrives → customer spoke → clear Twilio audio buffer
if message["type"] == "transcription":
    await websocket.send_json({"event": "clear", "streamSid": stream_sid})
```

---

## Audio Conversion in Bridge

```python
import audioop

# Voice bot outputs PCM 24kHz → Twilio needs mulaw 8kHz
pcm_8k = audioop.ratecv(pcm_24k, 2, 1, 24000, 8000, None)[0]
ulaw = audioop.lin2ulaw(pcm_8k, 2)
audio_payload = base64.b64encode(ulaw).decode("utf-8")
```

Note: `audioop` was removed in Python 3.13 standard library.
The demo uses `audioop-lts` package which brings it back for Python 3.13.

---

## Environment Variables (`twilio/.env`)

```
PORT=5050
SONIOX_VOICE_BOT_WS_URL=ws://localhost:8765   # voice bot server
VOICE_BOT_LANGUAGE=pa                          # pa = Punjabi
VOICE_BOT_VOICE=female_1                       # voice for TTS
```

---

## Development Setup with ngrok

Twilio needs a public HTTPS URL to reach your local server.

```bash
# Terminal 1 — run voice bot server
cd server && uv run main.py          # port 8765

# Terminal 2 — run twilio bridge
cd twilio && uv run main.py          # port 5050

# Terminal 3 — expose bridge to internet
ngrok http 5050
# → gives you: https://abc123.ngrok.io
```

Set Twilio webhook to: `https://abc123.ngrok.io/incoming-call`

---

## Twilio Setup (when ready for real calls)

1. Create account at twilio.com
2. Buy a phone number (~$1/month)
3. Go to Phone Number settings → Voice → Webhook
4. Set to: `https://your-ngrok-url/incoming-call` (POST)
5. Call the number to test

---

## Cost Per Call (Rough Estimate)

| Service | 5-min call cost |
|---------|----------------|
| Soniox STT (2.5 min listening) | ~$0.005 |
| Soniox TTS (2.5 min speaking) | ~$0.030 |
| OpenAI gpt-4o-mini | ~$0.010 |
| Twilio (phone call) | ~$0.040 |
| **Total per call** | **~$0.085** |
