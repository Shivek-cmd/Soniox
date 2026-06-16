# Soniox API Reference

## Endpoints

| Type | URL |
|------|-----|
| STT Real-time (WebSocket) | `wss://stt-rt.soniox.com` |
| TTS Real-time (WebSocket) | `wss://tts-rt.soniox.com/tts-websocket` |
| REST API base | `https://api.soniox.com/v1` |

## Authentication
```bash
export SONIOX_API_KEY=your_key_here
```
Get key from: https://console.soniox.com

---

## Python SDK — What We Use

```bash
pip install soniox
```

The voice bot server (`server/`) uses the Python SDK via the `STTProcessor` and `TTSProcessor` processor classes (in `processors/stt.py` and `processors/tts.py`). You don't call the SDK directly — the processors wrap it.

### STT config (in `server/main.py`)
```python
STTProcessor(
    api_key=SONIOX_API_KEY,
    model="stt-rt-v5",             # upgraded from v4 (June 2026)
    audio_format="mulaw",          # or "pcm_s16le" for browser
    audio_sample_rate=8000,        # 8000 for Twilio, 16000 for browser
    num_channels=1,
    max_endpoint_delay_ms=500,     # 4× faster than default 2000ms
    language_hints=["pa", "hi", "en"],
    context={
        "general": [
            {"key": "restaurant", "value": "Parkash Sweets"},
            {"key": "location",   "value": "Canada"},
            {"key": "setting",    "value": "Phone ordering"},
            {"key": "domain",     "value": "restaurant"},
            {"key": "topic",      "value": "Customer placing a takeaway order"},
            {"key": "language",   "value": "Punjabi, Hindi, English"},
        ],
        "terms": ["Parkash Sweets", "Gulab Jamun", ...]  # auto-built from Clover/Square menu
    }
)
```

### TTS config (in `server/main.py`)
```python
DynamicTTSProcessor(
    api_key=SONIOX_API_KEY,
    api_host="wss://tts-rt.soniox.com/tts-websocket",
    model="tts-rt-v1",
    language="pa",        # updated dynamically by select_language tool
    voice="Maya",         # updated dynamically by select_language tool
    audio_format="pcm_s16le",
    sample_rate=24000,
)
```

### Opening greeting pre-generation (`twilio/generate_opening_greeting.py`)
Direct WebSocket TTS call (no SDK wrapper):
```python
async with websockets.connect("wss://tts-rt.soniox.com/tts-websocket") as ws:
    await ws.send(json.dumps({
        "api_key": SONIOX_API_KEY,
        "model": "tts-rt-v1",
        "language": "en",
        "voice": "Maya",
        "audio_format": "pcm_s16le",
        "sample_rate": 24000,
        "stream_id": stream_id,
    }))
    await ws.send(json.dumps({"text": "Thank you for calling...", "text_end": False, "stream_id": stream_id}))
    await ws.send(json.dumps({"text": "", "text_end": True, "stream_id": stream_id}))
    # collect audio chunks → write WAV
```

---

## Language Codes We Use

| Language | Code | STT hints |
|----------|------|-----------|
| Punjabi | `pa` | `["pa", "hi", "en"]` |
| Hindi | `hi` | `["hi", "en"]` |
| English | `en` | `["en"]` |

### How language switching works at runtime
1. Customer speaks → `select_language("punjabi")` tool called by LLM
2. `state.tts_language = "pa"` and `state.tts_voice = "Maya"` updated
3. `DynamicTTSProcessor` reads state at start of next TTS stream → automatic switch
4. STT language hints are set once at connection time based on the initial language selection

---

## Voice Names

Voice `Maya` is used for all three languages in our implementation.
Check https://console.soniox.com for the full list of available voices per language.

---

## Audio Formats

| Format | Code | Used where |
|--------|------|-----------|
| PCM 16-bit signed little-endian | `pcm_s16le` | Browser → server (STT in), server → browser (TTS out) |
| µ-law 8kHz | `mulaw` | Twilio → bridge → server (STT in) |
| PCM 24kHz | `pcm_s16le` | Server TTS output (default) |

Twilio conversion (in `twilio/main.py`):
```python
# PCM 24kHz → mulaw 8kHz for Twilio playback
pcm_8k = audioop.ratecv(pcm_24k, 2, 1, 24000, 8000, None)[0]
ulaw   = audioop.lin2ulaw(pcm_8k, 2)
```

---

## STT Models

| Model | Notes |
|-------|-------|
| `stt-rt-v5` | Current — what we use (launched June 16 2026, v4 retires June 30) |

## TTS Models

| Model | Notes |
|-------|-------|
| `tts-rt-v1` | Current — what we use |

---

## Latency Optimizations

| Optimization | How | Impact |
|---|---|---|
| Faster STT endpoint detection | `max_endpoint_delay_ms=500` (default 2000ms) | ~1500ms saved per utterance |
| Manual VAD finalization | VAD silence → `{"type": "finalize"}` sent immediately | Skips Soniox's internal timer |
| TTS keepalive | `{"keep_alive": true}` every 20s when idle | Avoids cold reconnect mid-call |
| TTS cancel on barge-in | `{"stream_id": "...", "cancel": true}` | Stops wasted synthesis instantly |
| Filler phrases | Sent on first `delta.tool_calls` chunk from LLM | Kills dead air during menu lookup |
| `endpoint_sensitivity` | v5 param — higher = finalizes sooner | Optional tuning knob |

---

## Key Features We Rely On

- **stt-rt-v5** — latest model (June 2026); better accented speech, mid-sentence code-switching, alphanumeric precision
- **Multilingual per-token** — language ID per token; handles Punjabi/Hindi/English mixed in one sentence
- **Language hints** — `language_hints=["pa", "hi", "en"]` biases recognition toward expected scripts
- **Enriched STT context** — 6 `general` keys (restaurant, location, setting, domain, topic, language) + all 80+ menu terms
- **Manual VAD finalization** — Silero VAD triggers `{"type": "finalize"}` immediately on silence, skipping Soniox's 2s default wait
- **Streaming TTS** — audio chunks start playing before full LLM response is generated
- **Error type branching** — both `stt.py` and `tts.py` branch on `error_type` (stable) not `error_message`

---

## Token / Cost Reference

- 1 hour audio (STT) ≈ 30,000 tokens ≈ $0.12
- 1 hour audio (TTS) ≈ $0.70
- Per 5-min call (Soniox + GPT-4o-mini + Twilio) ≈ $0.10 total

---

## Docs & Resources

- Main docs: https://soniox.com/docs
- Console: https://console.soniox.com
- GitHub examples: https://github.com/soniox/soniox_examples
- Discord: https://discord.gg/rWfnk9uM5j
