# Daily Run Commands

Every time you want to run the voice agent locally, you need 2–5 terminals open.
- **Browser AI tab only** → Terminal 1 + Terminal 2
- **Browser AI tab + Browse Store tab** → Terminal 1 + Terminal 2 + Terminal 5
- **Real phone calls (Twilio)** → Terminal 1 + Terminal 3 + Terminal 4
- **Everything** → Terminal 1 + Terminal 2 + Terminal 3 + Terminal 4 + Terminal 5

---

## Terminal 1 — Voice Server (ALWAYS required for AI tab)

```powershell
cd "D:\Chrishan Solution\Soniox\soniox_examples\apps\soniox-voice-bot-demo\server"
.\.venv\Scripts\python.exe main.py
```

**You should see:**
```
Warming up VAD model...
Starting WebSocket server  host=localhost port=8765
```

---

## Terminal 2 — Frontend (browser testing)

```powershell
cd "D:\Chrishan Solution\Soniox\soniox_examples\apps\soniox-voice-bot-demo\frontend"
npm run dev
```

**Then open:** http://localhost:5173

The app has two tabs:
- **Order with Sierra** — AI voice ordering (requires Terminal 1)
- **Browse Store** — e-commerce store (requires Terminal 5 for live menu, or falls back to static `menu.json`)

---

## Terminal 3 — Twilio Bridge (phone calls only)

```powershell
cd "D:\Chrishan Solution\Soniox\soniox_examples\apps\soniox-voice-bot-demo\twilio"
python main.py
```

**You should see:**
```
Uvicorn running on http://0.0.0.0:5050
```

### Optional — generate cached opening greeting

Run this once when you want Twilio to play the first greeting faster from a local WAV file:

```powershell
cd "D:\Chrishan Solution\Soniox\soniox_examples\apps\soniox-voice-bot-demo\twilio"
$env:SONIOX_API_KEY="your_soniox_key"
python generate_opening_greeting.py
```

Then set this in `twilio/.env`:

```env
OPENING_GREETING_AUDIO_PATH=assets/opening_greeting.wav
```

---

## Terminal 4 — ngrok Tunnel (phone calls only)

```powershell
& "C:\Users\shive\ngrok\ngrok.exe" http 5050
```

**You should see:**
```
Forwarding  https://xxxx.ngrok-free.app -> http://localhost:5050
```

> Note: The ngrok URL changes every time you restart it (on free plan).
> Every time you get a new URL, update it in Twilio Console (see below).

---

## Terminal 5 — Store API (Browse Store tab)

```powershell
cd "D:\Chrishan Solution\Soniox\soniox_examples\apps\soniox-voice-bot-demo\store-api"
pip install -r requirements.txt   # first time only
$env:CLOVER_BASE_URL="https://apisandbox.dev.clover.com"
$env:CLOVER_MERCHANT_ID="your_merchant_id"
$env:CLOVER_ACCESS_TOKEN="your_access_token"
uvicorn main:app --host 0.0.0.0 --port 8766 --reload
```

**You should see:**
```
INFO:     Uvicorn running on http://0.0.0.0:8766
```

The Vite dev server automatically proxies `/store-api/*` → `http://localhost:8766` (configured in `vite.config.ts`). So when the React app calls `/store-api/menu`, it reaches this service.

> **Without Terminal 5:** The Browse Store tab still works — it falls back to static `menu.json` data. Items are visible but prices/inventory won't reflect live Clover data. No order placement without the store-api running.

---

## Twilio Console Setup (do once per ngrok restart)

1. Go to https://console.twilio.com
2. Phone Numbers → Manage → Active Numbers → click **+15878175156**
3. Under **Voice Configuration** → **A call comes in** → set URL to:
   ```
   https://YOUR-NGROK-URL.ngrok-free.app/incoming-call
   ```
4. Method: **HTTP POST** → Save

---

## Make Twilio Call You (for testing)

Make sure Terminal 1, 3, and 4 are all running first, then:

```powershell
cd "D:\Chrishan Solution\Soniox\soniox_examples\apps\soniox-voice-bot-demo\twilio"
python make_call.py
```

Your phone (+919413752688) will ring. Pick up and talk to the agent.

> If call doesn't come through, verify your number at:
> console.twilio.com → Phone Numbers → Verified Caller IDs → Add +919413752688

---

## Quick Checklist Before Testing

### AI ordering tab (browser)
- [ ] Terminal 1 running (server on port 8765)
- [ ] Terminal 2 running (Vite dev on port 5173)

### Browse Store tab
- [ ] Terminal 5 running (store-api on port 8766) — or accept static fallback data

### Phone calls
- [ ] Terminal 1 running (server on port 8765)
- [ ] Terminal 3 running (twilio bridge on port 5050)
- [ ] Terminal 4 running (ngrok tunnel active)
- [ ] Twilio Console webhook URL updated with latest ngrok URL
- [ ] `make_call.py` has correct ngrok URL

---

## Update ngrok URL in make_call.py

Open `twilio/make_call.py` and update this line with your current ngrok URL:

```python
NGROK_URL = "https://YOUR-NEW-NGROK-URL.ngrok-free.app"
```
