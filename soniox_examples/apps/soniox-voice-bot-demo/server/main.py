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
from messages import ErrorMessage, OrderConfirmedMessage, TransferCallMessage
from processors.llm import LLMProcessor, OPENING_GREETINGS
from processors.message_processor import MessageProcessor
from processors.stt import STTProcessor
from processors.tts import TTSProcessor
from processors.vad import VADProcessor
from session import Session
from tools import (
    LANGUAGE_CONFIG,
    RESTAURANT_NAME,
    STT_TERMS,
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
    "terms": [RESTAURANT_NAME] + STT_TERMS + ["dine-in", "pickup", "delivery"],
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

    async def start(self, send_message, log):
        # Store callbacks but do NOT open the Soniox WebSocket yet.
        # Opening at session start causes an ~10s idle window while the cached
        # greeting WAV plays, which makes Soniox time out the connection.
        # We connect lazily on first actual TTS use instead.
        self.log = log.bind(processor="tts")
        self._send_message = send_message

    async def _ensure_tts_alive(self):
        """Open (or reopen) the Soniox TTS WebSocket when needed."""
        # Connection is alive when the receive task exists and hasn't exited.
        if self._receive_task is not None and not self._receive_task.done():
            return
        # Cancel any stale tasks from a dropped connection.
        for task in (self._receive_task, self._send_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self.log.info("TTS — opening WebSocket connection")
        self._websocket = await websockets.connect(self._api_host)
        self._receive_task = asyncio.create_task(self._receive_task_handler())
        self._send_task = asyncio.create_task(self._send_task_handler())
        self._alive = True

    async def _generate_tts_response(self, message):
        if not self._active_stream_id:
            self._language = self._state.tts_language
            self._voice = self._state.tts_voice
            await self._ensure_tts_alive()
        await super()._generate_tts_response(message)

    async def _on_stream_finalized(self):
        if self._state.confirmed_order and self._send_message:
            order = self._state.confirmed_order
            self._state.confirmed_order = None
            await self._send_message(
                OrderConfirmedMessage(
                    order_id=order["order_id"],
                    customer_name=order["customer_name"],
                    phone_number=order.get("phone_number", ""),
                    order_type=order["order_type"],
                    items=order["items"],
                    total_amount=order["total_amount"],
                    wait_time=order["wait_time"],
                    special_instructions=order.get("special_instructions", ""),
                )
            )
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

    # Pre-select the language chosen in the frontend — no need to ask again
    initial_language = LANGUAGES_MAP.get(params.language, "English").lower()
    select_language_without_llm(initial_language)

    # STT hints scoped to the selected language so transcription stays in the right script.
    # English → Latin only. Hindi → Devanagari + Latin. Punjabi → all three.
    STT_LANGUAGE_HINTS = {
        "english": ["en"],
        "hindi":   ["hi", "en"],
        "punjabi": ["pa", "hi", "en"],
    }
    stt_hints = STT_LANGUAGE_HINTS.get(initial_language, ["pa", "hi", "en"])

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
            language_hints=stt_hints,
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
            opening_greeting=OPENING_GREETINGS.get(initial_language, OPENING_GREETINGS["english"]),
            language_preselected=True,
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
