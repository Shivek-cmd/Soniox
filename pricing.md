# Soniox Pricing Reference

## Simple Way to Think About It

Soniox charges like a taxi meter — only while audio is running.
Two things it does:

| What | What it does | Cost |
|------|-------------|------|
| STT (Speech-to-Text) | User talks → converts to text | ~$0.12 / hour |
| TTS (Text-to-Speech) | Agent talks → generates voice | ~$0.70 / hour |

---

## Real Example — One 5-Minute Call

| | Cost |
|--|--|
| User talked ~2.5 min (STT) | ~$0.005 |
| Agent talked ~2.5 min (TTS) | ~$0.030 |
| **Total per call** | **~$0.04** |

---

## Monthly Estimates

| Calls/month | Soniox cost | LLM cost (est.) | Total |
|-------------|-------------|-----------------|-------|
| 100 calls | ~$0.40 | ~$2-5 | ~$5 |
| 1,000 calls | ~$4.00 | ~$20-50 | ~$25-55 |
| 10,000 calls | ~$40.00 | ~$200-500 | ~$240-540 |

*(Assumes 5 min avg call, user + agent each talk ~2.5 min)*

---

## Technical Pricing (Exact Numbers from Soniox)

**STT — Real-time Streaming:**
- Input audio: $2.00 per 1M tokens (~$0.12/hr)
- Input text: $4.00 per 1M tokens
- Output text: $4.00 per 1M tokens

**TTS — Real-time Streaming:**
- Input text: $4.00 per 1M tokens
- Output audio: $21.50 per 1M tokens (~$0.70/hr)

**Token conversion:**
- 1 hour of audio ≈ 30,000 tokens
- 1 character ≈ 0.3 tokens

---

## Key Points

- **No subscription, no monthly fee** — pure pay-as-you-go
- **No free tier** — you pay from first use (but costs are tiny for testing)
- **Sub-200ms latency** — suitable for real-time voice agents
- **60+ languages** — both STT and TTS
- Soniox handles both STT and TTS — no need for separate ElevenLabs or Deepgram

---

## Pricing Page
https://soniox.com/pricing
