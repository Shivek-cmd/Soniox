# Voice Agent Architecture

## Real Architecture (from actual Soniox demo code)

Two separate services run together:

```
Customer Phone
      ↓
   Twilio
      ↓ WebSocket (mulaw 8kHz audio)
Twilio Bridge  ←── fastapi server (twilio/main.py)
      ↓ WebSocket (mulaw 8kHz audio, forwarded as-is)
Voice Bot Server  ←── websockets server (server/main.py) port 8765
      ├── VADProcessor    → detects speech start/end
      ├── STTProcessor    → Soniox STT → transcript
      ├── LLMProcessor    → OpenAI → response text
      └── TTSProcessor    → Soniox TTS → audio bytes
      ↓ WebSocket (PCM 24kHz audio back)
Twilio Bridge
      ↓ converts PCM 24kHz → mulaw 8kHz
   Twilio
      ↓
Customer hears agent
```

For **local browser testing** (no Twilio needed):
```
Browser (frontend/  React app)
      ↓ WebSocket (PCM 16kHz audio from mic)
Voice Bot Server (server/main.py) port 8765
      ↓ (same pipeline)
Browser plays audio back
```

---

## The 4 Processors (server/processors/)

Every audio chunk flows through all 4 in order via a message queue:

### 1. VADProcessor (`vad.py`)
- Uses **Silero VAD** (torch model) to detect when customer starts/stops speaking
- Fires `UserSpeechStartMessage` → LLM cancels its current response (barge-in)
- Fires `UserSpeechEndMessage` → passed downstream

### 2. STTProcessor (`stt.py`)
- Connects to `wss://stt-rt.soniox.com/transcribe-websocket`
- Streams audio chunks, receives transcript tokens back
- Fires `TranscriptionMessage` → accumulates transcript text
- Fires `TranscriptionEndpointMessage` → customer finished sentence → **triggers LLM**

### 3. LLMProcessor (`llm.py`)
- On `TranscriptionEndpointMessage` → calls OpenAI with full conversation history
- Streams response tokens → fires `LLMChunkMessage` per token
- Handles tool calls (e.g. `place_order`, `get_menu`)
- On `UserSpeechStartMessage` → cancels in-progress LLM call (barge-in)

### 4. TTSProcessor (`tts.py`)
- On each `LLMChunkMessage` → streams text to Soniox TTS
- Receives audio chunks back → fires `TTSAudioMessage`
- Audio sent back to client over WebSocket

---

## Message Types (how processors talk to each other)

```
UserAudioMessage          → raw audio bytes from customer
UserSpeechStartMessage    → VAD detected speech start → cancel LLM + TTS
UserSpeechEndMessage      → VAD detected speech end
TranscriptionMessage      → partial/full transcript from STT
TranscriptionEndpointMessage → customer finished sentence → start LLM
LLMChunkMessage           → one token from LLM → start TTS immediately
LLMFullMessage            → complete LLM response (for history)
TTSAudioMessage           → audio chunk → send to customer
SessionStartMessage       → new connection → LLM sends greeting
ErrorMessage              → something broke → close connection
MetricsMessage            → timing data (latency tracking)
```

---

## Barge-In (Interruption Handling)

Customer speaks while agent is talking:
1. VAD fires `UserSpeechStartMessage`
2. LLMProcessor cancels its active task
3. TTSProcessor stops sending audio
4. Twilio bridge sends `{"event": "clear"}` → Twilio cuts audio mid-sentence
5. STT starts collecting new transcript

---

## Audio Formats

| Stage | Format |
|-------|--------|
| Browser mic → server | PCM s16le, 16kHz, mono |
| Twilio → bridge | mulaw, 8kHz, mono (base64 in JSON) |
| Bridge → server | mulaw, 8kHz, mono (raw bytes) |
| Soniox STT expects | pcm_s16le OR mulaw (auto-detected) |
| Soniox TTS outputs | PCM, 24kHz, mono |
| Server → browser | PCM 24kHz, mono |
| Bridge → Twilio | mulaw, 8kHz, mono (converted back) |

Audio conversion in bridge (`audioop`):
```python
# PCM 24kHz → mulaw 8kHz
pcm_8k = audioop.ratecv(pcm_24k, 2, 1, 24000, 8000, None)[0]
ulaw = audioop.lin2ulaw(pcm_8k, 2)
```

---

## Latency Budget

```
Customer finishes speaking         → 0ms
VAD detects end of speech          → ~100ms
STT TranscriptionEndpoint fires    → ~200ms
LLM first token arrives            → ~500-800ms
TTS first audio chunk              → ~200-400ms
Customer hears first word          → ~900ms - 1400ms total
```

Sub-1.5 seconds feels natural. Over 2 seconds feels robotic.

---

## Conversation Memory

Stored inside `LLMProcessor._messages`:
```python
[
    {"role": "system", "content": "You are a restaurant agent for..."},
    {"role": "user", "content": "I want to order butter chicken"},
    {"role": "assistant", "content": "What size would you like?"},
    {"role": "user", "content": "Large please"},
    ...
]
```
Full history sent to LLM every turn. No external DB needed for the conversation itself.
