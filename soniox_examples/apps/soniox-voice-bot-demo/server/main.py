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
from messages import ErrorMessage, TransferCallMessage
from processors.llm import LLMProcessor
from processors.message_processor import MessageProcessor
from processors.stt import STTProcessor
from processors.tts import TTSProcessor
from processors.vad import VADProcessor
from session import Session
from tools import (
    LANGUAGE_CONFIG,
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
        "Parkash Sweets", "Aloo Samosa", "Noodle Samosa",
        "Chole Bhatura", "Choley Puri", "Aloo Puri", "Chaat Papdi",
        "Dahi Bhalla", "Samosa Choley", "Tawa Tikki Chaat",
        "Tawa Tikki Choley", "Aloo Besan Tikki Chaat", "Mix Veg Pakora",
        "Baingan Pakora", "Spring Roll", "Aloo Cutlet", "Parkash Platter",
        "Paneer Pakora", "Mirchi Pakora", "Hara Bara Kabab", "Gobi Pakora",
        "Dahi Kabab", "Mushroom Delux", "Aloo Besan Tikki",
        "Shimla Mirch Pakora", "Aloo Finger", "Tawa Tikki",
        "Aloo Bread Pakora", "Paneer Aloo Bread Pakora", "Bread Roll",
        "Aloo Tikki Burger", "Noodle Burger", "Paneer Tikki Burger",
        "Grilled Cheese Sandwich", "Super Veggie Sandwich",
        "Sweet Corn Sandwich", "Paneer Mayo Sandwich", "Coleslaw Sandwich",
        "Aloo Parantha", "Gobi Parantha", "Muli Parantha",
        "Paneer Parantha", "Mix Parantha", "Rasmalai", "Spongey Rasgulla",
        "Garam Gulab Jamun", "Moong Dal Halwa", "Garam Gajrela",
        "Kesar Rasmalai", "Mango Shake", "Strawberry Shake", "Oreo Shake",
        "Chocolate Shake", "Vanilla Shake", "Mango Faluda",
        "Strawberry Faluda", "Vanilla Faluda", "Masala Chai", "Elachi Chai",
        "Gur Chai", "Dudh Patti", "Coffee Indian Style", "Sweet Lassi",
        "Salty Lassi", "Mango Lassi", "Badam Milk", "Butter", "Dahi",
        "Raita", "Extra Bhatura", "Extra Puri", "Choley", "Mix Pickle",
        "Tamarind Sauce", "Mint Sauce", "dine-in", "pickup", "delivery",
    ],
}

SONIOX_API_KEY_TTS = os.getenv("SONIOX_API_KEY_TTS") or SONIOX_API_KEY
SONIOX_API_HOST_TTS = os.getenv("SONIOX_API_HOST_TTS") or "wss://tts-rt.soniox.com/tts-websocket"


class DynamicTTSProcessor(TTSProcessor):
    """Reads language/voice from RestaurantState on each new TTS stream.

    When select_language tool updates state mid-call, the next spoken
    response automatically uses the correct language and voice.

    When transfer_call tool sets state.transfer_requested, fires
    TransferCallMessage after the goodbye audio finishes playing.
    """

    def __init__(self, state: RestaurantState, **kwargs):
        super().__init__(**kwargs)
        self._state = state

    async def _generate_tts_response(self, message):
        if not self._active_stream_id:
            self._language = self._state.tts_language
            self._voice = self._state.tts_voice
        await super()._generate_tts_response(message)

    async def _on_stream_finalized(self):
        if self._state.transfer_requested and self._send_message:
            self._state.transfer_requested = False
            await self._send_message(TransferCallMessage(self._state.transfer_reason))


class QueryParams(pydantic.BaseModel):
    language: str
    voice: str

    audio_in_format: str = "pcm_s16le"
    audio_in_sample_rate: int = 16000
    audio_in_num_channels: int = 1
    audio_out_format: str = "pcm_s16le"
    audio_out_sample_rate: int = 24000
    skip_opening_greeting: bool = False
    caller_phone: str = ""

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

    state = RestaurantState(caller_phone=params.caller_phone)

    def select_language_without_llm(language: str):
        config = LANGUAGE_CONFIG.get(language.lower(), LANGUAGE_CONFIG["english"])
        state.tts_language = config["tts_language"]
        state.tts_voice = config["tts_voice"]

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
            system_message=get_system_message(LANGUAGES_MAP[params.language], caller_phone=params.caller_phone),
            tools=get_tools(state),
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            on_language_selected=select_language_without_llm,
            send_opening_greeting=not params.skip_opening_greeting,
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
