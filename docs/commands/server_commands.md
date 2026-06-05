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

`soniox_examples` is part of this repo directly. No submodule commands needed.

### 3. Create `.env` file with all credentials

```bash
nano .env
```

Paste the following (fill in all `your_*` placeholders):

```env
# ── Soniox ───────────────────────────────────────────────────────────────────
SONIOX_API_KEY=your_soniox_key
SONIOX_STT_MODEL=stt-rt-v4
SONIOX_TTS_MODEL=tts-rt-v1

# ── OpenAI ───────────────────────────────────────────────────────────────────
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.85
LLM_MAX_TOKENS=200

# ── Twilio ───────────────────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_NUMBER=+15878175156
YOUR_NUMBER=+919413752688
OWNER_PHONE_NUMBER=+919413752688
NGROK_URL=https://voice.bizbull.ai

# ── Voice bot defaults ────────────────────────────────────────────────────────
VOICE_BOT_LANGUAGE=pa
VOICE_BOT_VOICE=Maya

# ── n8n fallback (leave empty to skip) ───────────────────────────────────────
N8N_WEBHOOK_URL=

# ── Clover POS ───────────────────────────────────────────────────────────────
# Sandbox: https://apisandbox.dev.clover.com  |  Production: https://api.clover.com
CLOVER_BASE_URL=https://api.clover.com
CLOVER_MERCHANT_ID=your_clover_merchant_id
CLOVER_ACCESS_TOKEN=your_clover_access_token
# Leave empty for sandbox (sandbox tokens don't expire).
# For production, set this to enable auto-refresh 5 min before the 1-hour expiry.
CLOVER_REFRESH_TOKEN=
CLOVER_WEBHOOK_SECRET=parkash-clover-webhook-secret
CLOVER_MENU_POLL_INTERVAL=300
```

Press `Ctrl+O`, `Enter`, then `Ctrl+X` to save.

### 4. Build and start

First build takes 10–15 minutes (downloads Python, Node, npm packages).

```bash
docker compose up -d --build
```

### 5. Register Clover webhook

After the stack is running, register the webhook URL in the Clover developer dashboard:

- URL: `https://voice.bizbull.ai/clover-webhook`
- Secret: the value you set for `CLOVER_WEBHOOK_SECRET`
- Events to subscribe: inventory item changes (`I`, `IC`, `IG`, `IM`)

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

All 4 containers should be `Up`.

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
docker compose logs -f frontend
```

---

## Updating Code

### Commit changes on Windows

```powershell
cd "D:\Chrishan Solution\Soniox"
git add .
git commit -m "your message here"
git push
```

### Deploy on server (full rebuild)

```bash
cd ~/Soniox
git pull
docker compose up -d --build
```

### Python-only changes (faster — skips frontend rebuild)

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

1. Go to `console.twilio.com` → Phone Numbers → `+15878175156`
2. Voice Configuration → A call comes in
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
Internet → voice.bizbull.ai (Caddy, ports 80/443)
                 |
    ┌────────────┼──────────────────────┐
    |            |                      |
/ws             /incoming-call         /*
    |           /transfer-twiml         |
    v           /media-stream           v
voice-server    /clover-webhook     frontend
  :8765              |                :80
                     v
               twilio-bridge
                  :5050
```

4 Docker containers:

- `caddy` — HTTPS, path-based routing, auto SSL via Let's Encrypt
- `twilio-bridge` — Twilio phone bridge + Clover inventory webhook relay
- `voice-server` — VAD + STT + LLM + TTS pipeline + Clover POS client
- `frontend` — React UI served by nginx (browser testing)

---

## Troubleshooting

### Containers not starting

```bash
docker compose logs voice-server
docker compose logs twilio-bridge
```

If voice-server exits immediately, check Clover credentials — the server calls `CloverClient.init()` at startup and exits with code 1 if Clover is unreachable.

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
