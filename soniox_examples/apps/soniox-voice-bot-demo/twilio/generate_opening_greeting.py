import asyncio
import base64
import json
import os
import uuid
import wave
from pathlib import Path

from dotenv import load_dotenv
import websockets

load_dotenv()

GREETING_TEXT = (
    "Hi! This is Sierra calling from Parkaash Sweets. "
    "Would you like to continue in English, Hindi, or Punjabi?"
)

SONIOX_API_KEY = os.getenv("SONIOX_API_KEY", "")
SONIOX_TTS_MODEL = os.getenv("SONIOX_TTS_MODEL", "tts-rt-v1")
SONIOX_API_HOST_TTS = os.getenv(
    "SONIOX_API_HOST_TTS",
    "wss://tts-rt.soniox.com/tts-websocket",
)

OUTPUT_PATH = Path(
    os.getenv("OPENING_GREETING_OUTPUT_PATH", "assets/opening_greeting.wav")
)
VOICE = os.getenv("OPENING_GREETING_VOICE", "Maya")
LANGUAGE = os.getenv("OPENING_GREETING_LANGUAGE", "en")
SAMPLE_RATE = 24000


async def main():
    if not SONIOX_API_KEY:
        raise ValueError("Set SONIOX_API_KEY before generating the greeting.")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    stream_id = f"opening-greeting-{uuid.uuid4()}"
    audio_chunks = []

    async with websockets.connect(SONIOX_API_HOST_TTS) as websocket:
        await websocket.send(json.dumps({
            "api_key": SONIOX_API_KEY,
            "model": SONIOX_TTS_MODEL,
            "language": LANGUAGE,
            "voice": VOICE,
            "audio_format": "pcm_s16le",
            "sample_rate": SAMPLE_RATE,
            "stream_id": stream_id,
        }))

        await websocket.send(json.dumps({
            "text": GREETING_TEXT,
            "text_end": False,
            "stream_id": stream_id,
        }))
        await websocket.send(json.dumps({
            "text": "",
            "text_end": True,
            "stream_id": stream_id,
        }))

        async for message in websocket:
            content = json.loads(message)
            if content.get("stream_id") != stream_id:
                continue

            if content.get("audio"):
                audio_chunks.append(base64.b64decode(content["audio"]))

            if content.get("error_code") or content.get("error_message"):
                raise RuntimeError(
                    f"Soniox TTS error: {content.get('error_code')} "
                    f"{content.get('error_message')}"
                )

            if content.get("terminated"):
                break

    with wave.open(str(OUTPUT_PATH), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(b"".join(audio_chunks))

    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
