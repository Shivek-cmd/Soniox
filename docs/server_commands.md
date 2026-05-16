# Contabo Server - Deploy & Run Commands

**Server IP:** 194.163.171.241
**Domain:** voice.bizbull.ai
**Server OS:** Ubuntu 22.04

---

## SSH Into Server

```powershell
ssh root@194.163.171.241
```

Enter password when prompted. It will not show while typing.

---

## First-Time Setup

These steps are only needed once on a fresh server.

### 1. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
```

### 2. Clone the repo

```bash
git clone https://github.com/Shivek-cmd/Soniox.git
cd Soniox
```

`soniox_examples` is now part of this repo directly. You do not need to run any submodule commands.

### 3. Create `.env` file with API keys

```bash
nano .env
```

Paste:

```env
SONIOX_API_KEY=your_soniox_key
SONIOX_STT_MODEL=stt-rt-v4
SONIOX_TTS_MODEL=tts-rt-v1
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.85
LLM_MAX_TOKENS=120
```

Press `Ctrl+O`, `Enter`, then `Ctrl+X` to save.

### 4. Build and start

First build can take 10-15 minutes.

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

### Check status

All 3 containers should be `Up`.

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

### Commit changes on Windows

All code is now in one repo. Commit from the main `Soniox` folder only.

```powershell
cd "D:\Chrishan Solution\Soniox"
git add .
git commit -m "your message here"
git push
```

### Deploy on server

```bash
cd ~/Soniox
git pull
docker compose up -d --build
```

If only Python code changed and you want a quicker restart:

```bash
cd ~/Soniox
git pull
docker compose up -d --force-recreate voice-server twilio-bridge
```

---

## Twilio Setup

Twilio webhook URL:

```text
https://voice.bizbull.ai/incoming-call
```

Twilio Console steps:

1. Go to `console.twilio.com` -> Phone Numbers -> `+15878175156`
2. Voice Configuration -> A call comes in
3. Set URL to `https://voice.bizbull.ai/incoming-call`
4. Set method to `HTTP POST`
5. Save

---

## Make a Test Call From Windows

```powershell
cd "D:\Chrishan Solution\Soniox\soniox_examples\apps\soniox-voice-bot-demo\twilio"
python make_call.py
```

Your phone will ring. Pick up and talk to the agent.

---

## Architecture Running on Server

```text
Twilio -> HTTPS -> voice.bizbull.ai (Caddy, port 443)
                         |
                         v
                  twilio-bridge:5050  (Docker internal)
                         |
                         v
                  voice-server:8765   (Docker internal)
```

3 Docker containers:

- `caddy` - handles HTTPS and auto SSL certs via Let's Encrypt
- `twilio-bridge` - FastAPI bridge between Twilio and the voice server
- `voice-server` - VAD + STT + LLM + TTS pipeline

---

## Troubleshooting

### Containers not starting

```bash
docker compose logs voice-server
docker compose logs twilio-bridge
```

### SSL cert issues

```bash
docker compose logs caddy
```

Make sure the DNS A record for `voice.bizbull.ai` points to `194.163.171.241`.

### Rebuild from scratch

```bash
docker compose down
docker compose up -d --build
```
