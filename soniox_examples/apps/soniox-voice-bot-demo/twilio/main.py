# Based on the Twilio sample:
# https://github.com/twilio-samples/speech-assistant-openai-realtime-api-python/tree/main

import asyncio
import base64
import json
import os

import audioop
import websockets
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.websockets import WebSocketDisconnect
from pathlib import Path
import wave

from twilio.rest import Client as TwilioRestClient
from twilio.twiml.voice_response import Connect, Dial, Number, VoiceResponse

load_dotenv()

# Configuration
PORT = int(os.getenv("PORT", 5050))
SONIOX_VOICE_BOT_WS_URL = os.getenv("SONIOX_VOICE_BOT_WS_URL", "")
VOICE_BOT_LANGUAGE = os.getenv("VOICE_BOT_LANGUAGE", "en")
VOICE_BOT_VOICE = os.getenv("VOICE_BOT_VOICE", "Maya")
OPENING_GREETING_AUDIO_PATH = os.getenv("OPENING_GREETING_AUDIO_PATH", "")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
OWNER_PHONE_NUMBER = os.getenv("OWNER_PHONE_NUMBER", "")
NGROK_URL = os.getenv("NGROK_URL", "")

if not SONIOX_VOICE_BOT_WS_URL:
    raise ValueError(
        "Missing the SONIOX_VOICE_BOT_WS_URL. Please set it in the .env file."
    )

if not OWNER_PHONE_NUMBER:
    print("WARNING: OWNER_PHONE_NUMBER is not set. Call transfer will log but not connect.")

if not NGROK_URL:
    print("WARNING: NGROK_URL is not set. Call transfer will not work.")

if OPENING_GREETING_AUDIO_PATH and not Path(OPENING_GREETING_AUDIO_PATH).exists():
    print(
        "WARNING: OPENING_GREETING_AUDIO_PATH is set but the file does not exist. "
        "Falling back to generated voice-server greeting."
    )


app = FastAPI()


def load_opening_greeting_ulaw() -> bytes | None:
    """Load a cached greeting as Twilio-ready 8kHz mulaw bytes.

    Supported inputs:
    - raw .ulaw/.mulaw bytes at 8kHz
    - PCM .wav, which is converted to 8kHz mulaw
    """
    if not OPENING_GREETING_AUDIO_PATH:
        return None

    path = Path(OPENING_GREETING_AUDIO_PATH)
    if not path.exists():
        return None

    if path.suffix.lower() in {".ulaw", ".mulaw"}:
        return path.read_bytes()

    if path.suffix.lower() == ".wav":
        with wave.open(str(path), "rb") as wav_file:
            num_channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            pcm_audio = wav_file.readframes(wav_file.getnframes())

        if sample_width != 2:
            raise ValueError("Opening greeting WAV must be 16-bit PCM.")

        if num_channels != 1:
            pcm_audio = audioop.tomono(pcm_audio, sample_width, 0.5, 0.5)
            num_channels = 1

        if sample_rate != 8000:
            pcm_audio = audioop.ratecv(
                pcm_audio, sample_width, num_channels, sample_rate, 8000, None
            )[0]

        return audioop.lin2ulaw(pcm_audio, sample_width)

    raise ValueError(
        "OPENING_GREETING_AUDIO_PATH must point to a .wav, .ulaw, or .mulaw file."
    )


@app.api_route("/incoming-call", methods=["GET", "POST"])
async def handle_incoming_call(request: Request):
    """Handle incoming call and return TwiML response to connect to Media Stream."""
    response = VoiceResponse()

    host = request.url.hostname
    connect = Connect()
    connect.stream(url=f"wss://{host}/media-stream")
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

    opening_greeting_ulaw = load_opening_greeting_ulaw()
    skip_voice_server_greeting = "true" if opening_greeting_ulaw else "false"

    voice_bot_url_with_params = (
        f"{SONIOX_VOICE_BOT_WS_URL}"
        f"?audio_in_format=mulaw&audio_in_sample_rate=8000&audio_in_num_channels=1"
        f"&language={VOICE_BOT_LANGUAGE}&voice={VOICE_BOT_VOICE}"
        f"&skip_opening_greeting={skip_voice_server_greeting}"
    )
    async with websockets.connect(voice_bot_url_with_params) as voicebot_ws:
        # Per-call state
        stream_sid = None
        call_sid = None
        opening_greeting_sent = False
        opening_greeting_task = None

        # Queue to track 'mark' messages sent to Twilio — used for barge-in
        mark_queue = []

        async def receive_from_twilio():
            """Receive audio data from Twilio and forward it to the voice bot."""
            nonlocal stream_sid, call_sid, opening_greeting_sent, opening_greeting_task
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
                        if opening_greeting_ulaw and not opening_greeting_sent:
                            opening_greeting_sent = True
                            opening_greeting_task = asyncio.create_task(send_cached_opening_greeting())
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
            try:
                async for message in voicebot_ws:
                    if isinstance(message, str):
                        event = json.loads(message)
                        event_type = event.get("type")

                        if event_type in {"user_speech_start", "transcription"}:
                            # Barge-in: customer started speaking — cut bot audio
                            await handle_speech_started_event()

                        elif event_type == "transfer":
                            reason = event.get("reason", "unknown")
                            print(f"Call transfer requested. reason={reason} call_sid={call_sid}")
                            await initiate_call_transfer(call_sid, reason)

                        else:
                            print(f"Received event: {message}")
                    else:
                        # Raw PCM audio from Soniox TTS (24kHz, 16-bit, mono)
                        pcm_audio_bytes = message

                        # Resample to 8kHz and convert to µ-law for Twilio
                        pcm_8k = audioop.ratecv(pcm_audio_bytes, 2, 1, 24000, 8000, None)[0]
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
            nonlocal opening_greeting_task
            if opening_greeting_task and not opening_greeting_task.done():
                opening_greeting_task.cancel()
                opening_greeting_task = None
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

        async def send_cached_opening_greeting():
            """Stream cached 8kHz mulaw greeting audio directly to Twilio."""
            if not opening_greeting_ulaw or not stream_sid:
                return

            chunk_size = 160  # 20ms at 8kHz mulaw.
            print("Sending cached opening greeting to Twilio.")
            mark_queue.append("cachedOpeningGreeting")
            try:
                for start in range(0, len(opening_greeting_ulaw), chunk_size):
                    if not stream_sid:
                        return

                    chunk = opening_greeting_ulaw[start:start + chunk_size]
                    audio_payload = base64.b64encode(chunk).decode("utf-8")
                    await websocket.send_json({
                        "event": "media",
                        "streamSid": stream_sid,
                        "media": {"payload": audio_payload},
                    })
                    await asyncio.sleep(0.02)
            except asyncio.CancelledError:
                print("Cached opening greeting cancelled by caller speech.")
                return

            if stream_sid:
                await websocket.send_json({
                    "event": "mark",
                    "streamSid": stream_sid,
                    "mark": {"name": "cachedOpeningGreeting"},
                })

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
