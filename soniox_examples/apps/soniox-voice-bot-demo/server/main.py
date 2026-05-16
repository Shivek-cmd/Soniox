#!/usr/bin/env python

import asyncio
import os
from typing import List
from urllib.parse import parse_qs, urlparse

import dotenv
import pydantic
import structlog
import websockets
from websockets import ServerConnection
from websockets.asyncio.server import serve

from languages import LANGUAGES, LANGUAGES_MAP
from messages import ErrorMessage
from processors.llm import LLMProcessor
from processors.message_processor import MessageProcessor
from processors.stt import STTProcessor
from processors.tts import TTSProcessor
from processors.vad import VADProcessor
from session import Session
from tools import (
    RestaurantState,
    get_system_message,
    get_tools,
)

dotenv.load_dotenv()
log = structlog.get_logger()

WEBSOCKET_HOST = os.getenv("WEBSOCKET_HOST", "localhost")
WEBSOCKET_PORT = int(os.getenv("WEBSOCKET_PORT", "8765"))

SONIOX_API_KEY = os.getenv("SONIOX_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

OPENAI_MODEL = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"

SONIOX_STT_MODEL = os.getenv("SONIOX_STT_MODEL") or "stt-rt-v4"
SONIOX_TTS_MODEL = os.getenv("SONIOX_TTS_MODEL") or "tts-rt-v1"

LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE") or "0.85")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS") or "120")

STT_CONTEXT = {
    "general": [
        {"key": "domain", "value": "restaurant"},
        {"key": "topic", "value": "food ordering"},
    ],
    "terms": [
        "Bizbull Restaurant", "Butter Chicken", "Chicken Tikka Masala", "Saag Chicken",
        "Lamb Curry", "Goat Curry", "Dal Makhani", "Palak Paneer", "Kadai Paneer",
        "Chana Masala", "Aloo Gobi", "Mix Vegetable", "Samosa", "Veg Pakora",
        "Aloo Tikki", "Tandoori Chicken", "Chicken Tikka", "Butter Naan", "Garlic Naan",
        "Peshwari Naan", "Paratha", "Roti", "Basmati Rice", "Chicken Biryani",
        "Veg Biryani", "Mango Lassi", "Sweet Lassi", "Salted Lassi", "Masala Chai",
        "Gulab Jamun", "Kheer", "Rasmalai", "dine-in", "pickup", "delivery",
    ],
}

SONIOX_API_KEY_TTS = os.getenv("SONIOX_API_KEY_TTS") or SONIOX_API_KEY
SONIOX_API_HOST_TTS = os.getenv("SONIOX_API_HOST_TTS") or "wss://tts-rt.soniox.com/tts-websocket"


class DynamicTTSProcessor(TTSProcessor):
    """Reads language/voice from RestaurantState on each new TTS stream.

    When select_language tool updates state mid-call, the next spoken
    response automatically uses the correct language and voice.
    """

    def __init__(self, state: RestaurantState, **kwargs):
        super().__init__(**kwargs)
        self._state = state

    async def _generate_tts_response(self, message):
        if not self._active_stream_id:
            self._language = self._state.tts_language
            self._voice = self._state.tts_voice
        await super()._generate_tts_response(message)


class QueryParams(pydantic.BaseModel):
    language: str
    voice: str

    audio_in_format: str = "pcm_s16le"
    audio_in_sample_rate: int = 16000
    audio_in_num_channels: int = 1
    audio_out_format: str = "pcm_s16le"
    audio_out_sample_rate: int = 24000

    @pydantic.model_validator(mode="before")
    @classmethod
    def unwrap_single_item_lists(cls, values):
        unwrapped = {}
        for key, value in values.items():
            if isinstance(value, list) and len(value) == 1:
                unwrapped[key] = value[0]
            else:
                unwrapped[key] = value
        return unwrapped


async def send_error_and_close(websocket: ServerConnection, error: str):
    log.error(
        "Error occurred, sending error message and closing connection", error=error
    )
    try:
        await websocket.send(ErrorMessage(error).json())
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        await websocket.close()


async def handle(websocket: ServerConnection):
    # Get query parameters
    request = websocket.request
    if not request:
        await send_error_and_close(websocket, "No request found in websocket")
        return

    parsed_url = urlparse(request.path)
    query_params = parse_qs(parsed_url.query, keep_blank_values=True)

    try:
        params = QueryParams.model_validate(query_params)
    except pydantic.ValidationError as e:
        log.error("Invalid query parameters", query_params=query_params, error=e)
        await send_error_and_close(websocket, "Invalid query parameters")
        return

    if params.language not in LANGUAGES:
        await send_error_and_close(websocket, "Invalid language")
        return

    state = RestaurantState()

    processors: List[MessageProcessor] = [
        VADProcessor(
            sample_rate=params.audio_in_sample_rate,
        ),
        STTProcessor(
            api_key=SONIOX_API_KEY,
            model=SONIOX_STT_MODEL,
            audio_format=params.audio_in_format,
            audio_sample_rate=params.audio_in_sample_rate,
            num_channels=params.audio_in_num_channels,
            language_hints=["pa", "hi", "en"],
            context=STT_CONTEXT,
        ),
        LLMProcessor(
            api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            system_message=get_system_message(LANGUAGES_MAP[params.language]),
            tools=get_tools(state),
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        ),
        DynamicTTSProcessor(
            state=state,
            api_key=SONIOX_API_KEY_TTS,
            api_host=SONIOX_API_HOST_TTS,
            model=SONIOX_TTS_MODEL,
            language=state.tts_language,
            audio_format=params.audio_out_format,
            sample_rate=params.audio_out_sample_rate,
            voice=state.tts_voice,
        ),
    ]

    session = Session(
        processors,
        websocket,
    )
    await session.run()


async def main():
    log.info("Warming up VAD model...")
    VADProcessor.warmup()
    log.info("Starting WebSocket server", host=WEBSOCKET_HOST, port=WEBSOCKET_PORT)
    async with serve(handle, WEBSOCKET_HOST, WEBSOCKET_PORT) as server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
