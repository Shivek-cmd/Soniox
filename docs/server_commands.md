# Contabo Server — Deploy & Run Commands

**Server IP:** 194.163.171.241
**Domain:** voice.bizbull.ai
**Server OS:** Ubuntu 22.04

---

## SSH Into Server

```powershell
ssh root@194.163.171.241
```

Enter password when prompted (won't show while typing, that's normal).

---

## First-Time Setup (already done — don't repeat)

### 1. Install Docker
```bash
curl -fsSL https://get.docker.com | sh
```

### 2. Clone the repo
```bash
git clone https://github.com/Shivek-cmd/Soniox.git
cd Soniox
```

### 3. Initialize submodules (soniox_examples)
```bash
git submodule update --init --recursive
```

### 4. Create .env file with API keys
```bash
nano .env
```
Paste:
```
SONIOX_API_KEY=your_soniox_key
SONIOX_STT_MODEL=stt-rt-v4
SONIOX_TTS_MODEL=tts-rt-v1
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.85
LLM_MAX_TOKENS=120
```
Ctrl+O → Enter → Ctrl+X to save.

### 5. Build and start (first build takes 10-15 min)
```bash
docker compose up -d --build
```

---

## Daily Commands

### Start everything
```bash
cd ~/Soniox
docker compose up -d
```

### Stop everything
```bash
docker compose down
```

### Restart everything
```bash
docker compose restart
```

### Check status (all 3 containers should be Up)
```bash
docker compose ps
```

### Watch live logs
```bash
docker compose logs -f
```

### Watch logs for one service only
```bash
docker compose logs -f voice-server
docker compose logs -f twilio-bridge
docker compose logs -f caddy
```

---

## Updating Code

When you push changes from Windows to GitHub:

```bash
cd ~/Soniox
git pull
docker compose up -d --build
```

---

## Twilio Setup

Twilio webhook URL (set once, never changes):
```
https://voice.bizbull.ai/incoming-call
```

**Twilio Console steps:**
1. console.twilio.com → Phone Numbers → +15878175156
2. Voice Configuration → A call comes in → URL: `https://voice.bizbull.ai/incoming-call`
3. Method: HTTP POST → Save

---

## Make a Test Call (from Windows)

```powershell
cd "D:\Chrishan Solution\Soniox\soniox_examples\apps\soniox-voice-bot-demo\twilio"
python make_call.py
```

Your phone (+919413752688) will ring. Pick up and talk to the agent.

---

## Architecture Running on Server

```
Twilio → HTTPS → voice.bizbull.ai (Caddy, port 443)
                         ↓
                  twilio-bridge:5050  (Docker internal)
                         ↓ ws://voice-server:8765
                  voice-server:8765   (Docker internal)
```

3 Docker containers:
- `caddy` — handles HTTPS, auto SSL cert via Let's Encrypt
- `twilio-bridge` — FastAPI bridge between Twilio and voice server
- `voice-server` — VAD + STT + LLM + TTS pipeline (the brain)

---

## Troubleshooting

**Containers not starting:**
```bash
docker compose logs voice-server
docker compose logs twilio-bridge
```

**SSL cert issues (Caddy):**
```bash
docker compose logs caddy
```
Make sure DNS A record for `voice.bizbull.ai` points to `194.163.171.241`.

**Rebuild from scratch:**
```bash
docker compose down
docker compose up -d --build
```
