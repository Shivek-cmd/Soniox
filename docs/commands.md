# Daily Run Commands

Every time you want to run the voice agent, you need 2 or 3 terminals open.
- **Browser testing** → Terminal 1 + Terminal 2
- **Real phone calls (Twilio)** → Terminal 1 + Terminal 3 + Terminal 4

---

## Terminal 1 — Voice Server (ALWAYS required)

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

## Terminal 2 — Frontend (browser testing only)

```powershell
cd "D:\Chrishan Solution\Soniox\soniox_examples\apps\soniox-voice-bot-demo\frontend"
npm run dev
```

**Then open:** http://localhost:5173

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
