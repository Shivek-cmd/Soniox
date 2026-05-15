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

## Node.js SDK (Our Choice)

```bash
npm install @soniox/node
```

### STT — Real-time Streaming (actual working code from Soniox GitHub)
```javascript
import { SonioxNodeClient } from '@soniox/node';

const client = new SonioxNodeClient({
  api_key: process.env.SONIOX_API_KEY,
});

const session = client.realtime.stt({
  model: 'stt-rt-v4',
  audio_format: 'pcm_s16le',   // PCM 16-bit signed little-endian
  sample_rate: 16000,           // 16kHz
  num_channels: 1,              // mono
  enable_endpoint_detection: true,   // detects when user stops speaking → trigger LLM
  language_hints: ['pa', 'en'],      // Punjabi + English
});

// Events
session.on('result', (result) => {
  const text = result.tokens.map(t => t.text).join('');
  console.log('transcript:', text);
});

session.on('endpoint', () => {
  // User has FINISHED speaking → send transcript to LLM now
  console.log('User done speaking → call LLM');
});

session.on('error', (err) => console.error(err));

// Connect and stream audio
await session.connect();
session.sendAudio(audioChunk);  // call this in a loop as audio arrives

// Control commands
session.pause();    // pause listening (while agent is speaking)
session.resume();   // resume listening (after agent finishes)
await session.finish();  // end session
```

### TTS — Real-time Streaming
```javascript
// REST-based TTS (simple)
const bytes = await client.tts.generateToFile('output.wav', {
  text: 'ਸਤ ਸ੍ਰੀ ਅਕਾਲ! ਮੈਂ ਤੁਹਾਡੀ ਮਦਦ ਕਰ ਸਕਦਾ ਹਾਂ।',
  voice: 'Adrian',         // voice ID — check Soniox console for Punjabi voices
  model: 'tts-rt-v1',
  language: 'pa',          // Punjabi
  audio_format: 'wav',
});

// WebSocket TTS (streaming — for lower latency)
// Use wss://tts-rt.soniox.com/tts-websocket directly
```

### Key Session Events
| Event | When it fires | What to do |
|-------|--------------|------------|
| `result` | Partial/full transcript arrives | Display interim, buffer final |
| `endpoint` | User finished speaking | → Send transcript to LLM |
| `disconnected` | Connection dropped | Reconnect or end call |
| `error` | Something broke | Log + handle gracefully |

### Key Session Methods
| Method | What it does |
|--------|-------------|
| `session.connect()` | Open WebSocket to Soniox |
| `session.sendAudio(buffer)` | Send audio chunk (call in loop) |
| `session.pause()` | Stop processing audio (agent speaking) |
| `session.resume()` | Resume listening (agent done speaking) |
| `session.finalize()` | Force end-of-utterance detection |
| `session.finish()` | End session cleanly |
| `session.close()` | Close immediately |

## Python SDK (alternative)

```bash
pip install soniox
```

Basic pattern same as Node — uses `AsyncSonioxClient`, same events and methods.

## Language Codes for Our Use Case

| Language | Code |
|----------|------|
| Punjabi | `pa` |
| English | `en` |
| Hindi | `hi` |

## Key Features We'll Use

- **Multilingual support** — customer can speak Punjabi or English, Soniox handles both
- **Language hints** — tell Soniox which languages to expect (`["pa", "en"]`)
- **Speaker diarization** — detect different speakers (useful for noisy environments)
- **End-of-utterance detection** — know when customer is done speaking
- **Sub-200ms latency** — fast enough for natural phone conversation

## Token Conversion (for cost tracking)
- 1 hour audio = ~30,000 tokens
- 1 character = ~0.3 tokens

## Docs & Resources
- Main docs: https://soniox.com/docs
- Console: https://console.soniox.com
- GitHub examples: https://github.com/soniox/soniox_examples
- Discord: https://discord.gg/rWfnk9uM5j
