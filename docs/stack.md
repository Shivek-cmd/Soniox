# Tech Stack Decision

## What We're Building
A restaurant voice agent that:
- Answers incoming phone calls
- Understands Punjabi and English
- Takes food orders from customers
- Confirms the order back
- Sends order to restaurant (WhatsApp / email)

---

## Final Stack

| Layer | Tool | Why |
|-------|------|-----|
| Base project | **soniox-voice-bot-demo** | Soniox's official demo — complete voice agent, we only change tools.py |
| Phone calls | **Twilio** | Real phone number, streams audio via WebSocket to our bridge |
| STT | **Soniox** | Punjabi language support, sub-200ms latency, streaming |
| TTS | **Soniox** | Same API, Punjabi voices, natural sounding |
| VAD | **Silero VAD** | Detects when customer starts/stops speaking, enables barge-in |
| LLM | **OpenAI gpt-4o-mini** | Already wired in the demo, cheap, fast. Switch to Claude later if needed |
| Voice bot server | **Python + websockets** | Port 8765 — runs the 4 processors pipeline |
| Twilio bridge | **Python + FastAPI** | Port 5050 — connects Twilio phone calls to voice bot server |
| Frontend | **React (Vite)** | Port 5173 — browser UI for local testing without Twilio |
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
soniox_examples/apps/soniox-voice-bot-demo/   ← base project (cloned)
├── server/                    ← voice bot brain (Python, port 8765)
│   ├── main.py                ← WebSocket server entry point
│   ├── session.py             ← manages message queue per call
│   ├── languages.py           ← 60+ languages including "pa" (Punjabi)
│   ├── tools.py               ← ✅ THE ONLY FILE WE EDIT
│   ├── processors/
│   │   ├── vad.py             ← Silero VAD (don't touch)
│   │   ├── stt.py             ← Soniox STT (don't touch)
│   │   ├── llm.py             ← OpenAI LLM (don't touch)
│   │   └── tts.py             ← Soniox TTS (don't touch)
│   └── .env                   ← SONIOX_API_KEY, OPENAI_API_KEY
├── twilio/                    ← phone call bridge (Python, port 5050)
│   ├── main.py                ← FastAPI server (don't touch)
│   └── .env                   ← SONIOX_VOICE_BOT_WS_URL, VOICE_BOT_LANGUAGE=pa
└── frontend/                  ← browser test UI (React, port 5173)
    └── (don't touch)
```

---

## Python Dependencies (actual, from pyproject.toml)

### server/
```
openai>=1.101.0      # LLM
python-dotenv        # env vars
structlog            # logging
websockets>=15.0.1   # WebSocket to Soniox STT/TTS
silero-vad           # Voice Activity Detection
torch                # required by silero-vad
torchaudio           # required by silero-vad
onnxruntime          # required by silero-vad
numpy                # audio processing
pydantic>=2.11.7     # request validation
```

### twilio/
```
fastapi>=0.116.1     # webhook server
uvicorn>=0.35.0      # run FastAPI
websockets>=15.0.1   # connect to voice bot server
twilio>=9.7.2        # Twilio helper
audioop-lts>=0.2.2   # audio format conversion (mulaw ↔ PCM), Python 3.13 compatible
```

**Install with uv** (not pip) — run `uv sync` inside each folder separately.

---

## Build Order

1. Run demo as-is in browser → confirm everything works
2. Pick Punjabi in language selector → confirm Punjabi STT/TTS works
3. Write restaurant `tools.py` (menu + place_order)
4. Test order flow in browser
5. Set up Twilio phone number
6. Run twilio bridge + ngrok → test with real phone call
7. Wire `place_order` to WhatsApp/email notification
8. Deploy to server (Docker ready)

---

## API Keys Needed

| Key | Service | Get from |
|-----|---------|----------|
| `SONIOX_API_KEY` | STT + TTS | console.soniox.com |
| `OPENAI_API_KEY` | LLM | platform.openai.com |
| `TWILIO_*` | Phone calls | twilio.com (Step 5 only) |
