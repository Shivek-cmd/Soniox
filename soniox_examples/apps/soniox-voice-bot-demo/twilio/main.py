# Based on the Twilio sample:
# https://github.com/twilio-samples/speech-assistant-openai-realtime-api-python/tree/main

import asyncio
import base64
import hmac
import json
import os
import urllib.request
from urllib.parse import quote

import audioop
import websockets
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.websockets import WebSocketDisconnect

from twilio.rest import Client as TwilioRestClient
from twilio.twiml.voice_response import Connect, Dial, Number, VoiceResponse

load_dotenv()

# Configuration
PORT = int(os.getenv("PORT", 5050))
SONIOX_VOICE_BOT_WS_URL = os.getenv("SONIOX_VOICE_BOT_WS_URL", "")
VOICE_BOT_LANGUAGE = os.getenv("VOICE_BOT_LANGUAGE", "en")
VOICE_BOT_VOICE = os.getenv("VOICE_BOT_VOICE", "Maya")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
OWNER_PHONE_NUMBER = os.getenv("OWNER_PHONE_NUMBER", "")
NGROK_URL = os.getenv("NGROK_URL", "")

CLOVER_WEBHOOK_SECRET = os.getenv("CLOVER_WEBHOOK_SECRET", "")
VOICE_SERVER_INTERNAL_URL = os.getenv("VOICE_SERVER_INTERNAL_URL", "http://localhost:8765")

_CLOVER_RELOAD_TYPES = frozenset({"I", "IC", "IG", "IM"})

if not SONIOX_VOICE_BOT_WS_URL:
    raise ValueError(
        "Missing the SONIOX_VOICE_BOT_WS_URL. Please set it in the .env file."
    )

if not OWNER_PHONE_NUMBER:
    print("WARNING: OWNER_PHONE_NUMBER is not set. Call transfer will log but not connect.")

if not NGROK_URL:
    print("WARNING: NGROK_URL is not set. Call transfer will not work.")

app = FastAPI()


@app.post("/clover-webhook")
async def handle_clover_webhook(request: Request):
    """Receive Clover inventory webhooks and forward a reload signal to the voice server."""
    body = await request.body()

    try:
        payload = json.loads(body)
    except Exception:
        return HTMLResponse(status_code=400, content="Invalid JSON")

    # Clover sends a verification POST with no auth header — just a verificationCode.
    # Return 200 immediately so the dashboard can complete verification.
    # Copy the code from logs, paste it into the Clover dashboard to finish setup.
    if "verificationCode" in payload:
        print(f"clover.webhook.verification_code={payload['verificationCode']}")
        return HTMLResponse(status_code=200, content="OK")

    auth_header = request.headers.get("X-Clover-Auth", "")
    if CLOVER_WEBHOOK_SECRET and not hmac.compare_digest(auth_header, CLOVER_WEBHOOK_SECRET):
        return HTMLResponse(status_code=401, content="Unauthorized")

    # Clover format: {"merchants": {"MID": {"data": [{"type": "I", ...}]}}}
    should_reload = any(
        event.get("type") in _CLOVER_RELOAD_TYPES
        for merchant_data in payload.get("merchants", {}).values()
        for event in merchant_data.get("data", [])
    )

    if should_reload:
        def _ping_voice_server() -> None:
            try:
                urllib.request.urlopen(
                    f"{VOICE_SERVER_INTERNAL_URL}/internal/clover-reload",
                    timeout=3,
                )
            except Exception as exc:
                print(f"clover.webhook.forward_failed: {exc}")

        await asyncio.to_thread(_ping_voice_server)

    return HTMLResponse(status_code=200, content="OK")


@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """Handle incoming call and return TwiML response to connect to Media Stream."""
    form_data = await request.form()
    caller_phone = form_data.get("From", "")

    response = VoiceResponse()
    host = request.url.hostname
    connect = Connect()
    stream_url = f"wss://{host}/media-stream"
    if caller_phone:
        stream_url += f"?caller_phone={quote(str(caller_phone), safe='')}"
    connect.stream(url=stream_url)
    response.append(connect)

    return HTMLResponse(content=str(response), media_type="application/xml")


@app.api_route("/transfer-twiml", methods=["GET", "POST"])
async def handle_transfer_twiml(request: Request):
    """TwiML returned when Twilio redirects a call for transfer to the restaurant owner."""
    response = VoiceResponse()

    if OWNER_PHONE_NUMBER:
        dial = Dial()
        dial.number(OWNER_PHONE_NUMBER)
        response.append(dial)
    else:
        response.say("We're sorry, we could not complete the transfer. Please call back.")

    return HTMLResponse(content=str(response), media_type="application/xml")


@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle WebSocket connections between Twilio and Soniox voice bot."""
    await websocket.accept()

    caller_phone = websocket.query_params.get("caller_phone", "")

    # phone=true tells the voice server: speak the language-selection greeting via TTS
    # and wait for the caller to choose English / Hindi / Punjabi before ordering.
    voice_bot_url_with_params = (
        f"{SONIOX_VOICE_BOT_WS_URL}"
        f"?audio_in_format=mulaw&audio_in_sample_rate=8000&audio_in_num_channels=1"
        f"&language={VOICE_BOT_LANGUAGE}&voice={VOICE_BOT_VOICE}"
        f"&phone=true"
    )
    if caller_phone:
        voice_bot_url_with_params += f"&caller_phone={quote(caller_phone, safe='')}"
    async with websockets.connect(voice_bot_url_with_params) as voicebot_ws:
        # Per-call state
        stream_sid = None
        call_sid = None

        # Queue to track 'mark' messages sent to Twilio — used for barge-in
        mark_queue = []

        async def receive_from_twilio():
            """Receive audio data from Twilio and forward it to the voice bot."""
            nonlocal stream_sid, call_sid
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    if data["event"] == "media" and voicebot_ws.state.name == "OPEN":
                        audio_payload = data["media"]["payload"]
                        ulaw_audio_bytes = base64.b64decode(audio_payload)
                        await voicebot_ws.send(ulaw_audio_bytes)
                    elif data["event"] == "start":
                        stream_sid = data["start"]["streamSid"]
                        call_sid = data["start"]["callSid"]
                        print(f"Stream started: stream_sid={stream_sid} call_sid={call_sid}")
                    elif data["event"] == "mark":
                        if mark_queue:
                            mark_queue.pop(0)
                    elif data["event"] == "stop":
                        print(f"Twilio stream {stream_sid} stopped.")
                        break
            except WebSocketDisconnect:
                print("Twilio client disconnected.")

        async def send_to_twilio():
            """Receive events from the voice bot, send audio back to Twilio."""
            nonlocal stream_sid, call_sid
            # Carry resampler state across chunks — passing None each call resets the
            # interpolation filter at every chunk boundary, causing audible pops/clicks.
            _ratecv_state = None
            try:
                async for message in voicebot_ws:
                    if isinstance(message, str):
                        event = json.loads(message)
                        event_type = event.get("type")

                        if event_type in {"user_speech_start", "transcription"}:
                            # Barge-in: customer started speaking — cut bot audio
                            await handle_speech_started_event()
                            _ratecv_state = None  # reset resampler after audio gap

                        elif event_type == "transfer":
                            reason = event.get("reason", "unknown")
                            print(f"Call transfer requested. reason={reason} call_sid={call_sid}")
                            await initiate_call_transfer(call_sid, reason)

                        else:
                            print(f"Received event: {message}")
                    else:
                        # Raw PCM audio from Soniox TTS (24kHz, 16-bit, mono)
                        pcm_audio_bytes = message

                        # Resample to 8kHz and convert to µ-law for Twilio.
                        # State is carried between chunks for smooth interpolation.
                        pcm_8k, _ratecv_state = audioop.ratecv(pcm_audio_bytes, 2, 1, 24000, 8000, _ratecv_state)
                        ulaw_audio_bytes = audioop.lin2ulaw(pcm_8k, 2)

                        audio_payload = base64.b64encode(ulaw_audio_bytes).decode("utf-8")
                        await websocket.send_json({
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {"payload": audio_payload},
                        })
                        await send_mark(websocket, stream_sid)

            except Exception as e:
                print(f"Error in send_to_twilio: {e}")

        async def handle_speech_started_event():
            """Cut bot audio if customer speaks while bot is talking."""
            if mark_queue:
                await websocket.send_json({"event": "clear", "streamSid": stream_sid})
                mark_queue.clear()

        async def send_mark(connection, sid):
            if sid:
                await connection.send_json({
                    "event": "mark",
                    "streamSid": sid,
                    "mark": {"name": "responsePart"},
                })
                mark_queue.append("responsePart")

        async def initiate_call_transfer(cid: str | None, reason: str):
            """Redirect the live call to the restaurant owner via Twilio REST API."""
            if not cid:
                print("Cannot transfer: call_sid not available yet.")
                return
            if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
                print("Cannot transfer: Twilio credentials not configured.")
                return
            if not OWNER_PHONE_NUMBER:
                print("Cannot transfer: OWNER_PHONE_NUMBER not configured.")
                return
            if not NGROK_URL:
                print("Cannot transfer: NGROK_URL not configured.")
                return

            transfer_url = f"{NGROK_URL}/transfer-twiml"
            print(f"Redirecting call {cid} to {transfer_url} (reason={reason})")

            def do_redirect():
                client = TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                client.calls(cid).update(url=transfer_url, method="GET")

            try:
                await asyncio.to_thread(do_redirect)
                print(f"Call {cid} successfully redirected to owner.")
            except Exception as e:
                print(f"Failed to redirect call {cid}: {e}")

        receive_task = asyncio.create_task(receive_from_twilio())
        send_task = asyncio.create_task(send_to_twilio())

        _, pending = await asyncio.wait(
            [receive_task, send_task], return_when=asyncio.FIRST_COMPLETED
        )

        for task in pending:
            task.cancel()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
