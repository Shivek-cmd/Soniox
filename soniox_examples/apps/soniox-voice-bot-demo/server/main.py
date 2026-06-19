#!/usr/bin/env python

import asyncio
import logging
import os
import time
from http import HTTPStatus
from typing import List
from urllib.parse import parse_qs, urlparse

import dotenv
import pydantic
import structlog
import websockets
from websockets import ServerConnection
from websockets.asyncio.server import serve

from languages import LANGUAGES, LANGUAGES_MAP
from messages import ErrorMessage, LLMChunkMessage, OrderConfirmedMessage, TransferCallMessage
from tts_substitutions import apply_tts_substitutions
from processors.llm import LLMProcessor, OPENING_GREETING, OPENING_GREETINGS
# from processors.anthropic_llm import AnthropicLLMProcessor  # Anthropic — kept for easy revert
from processors.message_processor import MessageProcessor
from processors.stt import STTProcessor
from processors.tts import TTSProcessor
from processors.vad import VADProcessor
from session import Session
from clover import CloverClient, CloverError, get_client, set_client
from square_client import SquareClient, SquareError
from tools import (
    LANGUAGE_CONFIG,
    RESTAURANT_NAME,
    STT_TERMS,
    RestaurantState,
    get_system_message,
    get_tools,
)

dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO)
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
# Silence third-party stdlib loggers — their calls are re-emitted as structlog
# clover.api.* events where useful; the rest is noise.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)
log = structlog.get_logger()

# Reconnect TTS before Soniox's ~60 s idle keepalive timeout fires.
_TTS_IDLE_RECONNECT_SECS = 45

WEBSOCKET_HOST = os.getenv("WEBSOCKET_HOST", "localhost")
WEBSOCKET_PORT = int(os.getenv("WEBSOCKET_PORT", "8765"))

SONIOX_API_KEY = os.getenv("SONIOX_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

OPENAI_MODEL = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL") or "claude-opus-4-8"

SONIOX_STT_MODEL = os.getenv("SONIOX_STT_MODEL") or "stt-rt-v5"
SONIOX_TTS_MODEL = os.getenv("SONIOX_TTS_MODEL") or "tts-rt-v1"

LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE") or "0.85")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS") or "120")

STT_CONTEXT = {
    "general": [
        {"key": "restaurant", "value": RESTAURANT_NAME},
        {"key": "location",   "value": "Canada"},
        {"key": "setting",    "value": "Phone ordering"},
        {"key": "domain",     "value": "restaurant"},
        {"key": "topic",      "value": "Customer placing a takeaway order"},
        {"key": "language",   "value": "Punjabi, Hindi, English"},
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
        self._last_stream_end: float = 0.0

    async def start(self, send_message, log):
        # Store callbacks but do NOT open the Soniox WebSocket yet.
        # Opening at session start causes an ~10s idle window while the cached
        # greeting WAV plays, which makes Soniox time out the connection.
        # We connect lazily on first actual TTS use instead.
        self.log = log.bind(processor="tts")
        self._send_message = send_message

    async def _ensure_tts_alive(self):
        """Open (or reopen) the Soniox TTS WebSocket when needed.

        Two-layer safety net:
          1. Time-based (pre-emptive): reconnect if the connection has been idle
             for _TTS_IDLE_RECONNECT_SECS.  Soniox kills connections after ~60 s
             of silence with a keepalive ping timeout.  We reconnect at 45 s so
             the new stream always starts on a fresh socket.
          2. Task-based (reactive): reconnect if the receive task has already
             exited (unexpected drop, server restart, network blip).
        """
        idle_secs = time.monotonic() - self._last_stream_end
        task_running = (
            self._receive_task is not None and not self._receive_task.done()
        )
        if task_running and idle_secs < _TTS_IDLE_RECONNECT_SECS:
            return
        # Cancel any stale tasks before opening a fresh connection.
        for task in (self._receive_task, self._send_task, self._keepalive_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        # Fresh connection — old dead-stream IDs are irrelevant on the new socket.
        self._dead_stream_ids.clear()
        # Retry the handshake — Soniox can transiently time out on new connections.
        _last_exc: Exception | None = None
        for _attempt in range(1, 4):
            try:
                self.log.debug(
                    "TTS — opening WebSocket connection",
                    idle_secs=round(idle_secs), attempt=_attempt,
                )
                self._websocket = await websockets.connect(self._api_host)
                _last_exc = None
                break
            except Exception as exc:
                _last_exc = exc
                if _attempt < 3:
                    _wait = _attempt * 2.0
                    self.log.warning(
                        "tts.connect.retry",
                        attempt=_attempt, wait=_wait, error=str(exc),
                    )
                    await asyncio.sleep(_wait)
        if _last_exc is not None:
            self.log.error("tts.connect.failed", attempts=3, error=str(_last_exc))
            raise _last_exc
        self._receive_task = asyncio.create_task(self._receive_task_handler())
        self._send_task = asyncio.create_task(self._send_task_handler())
        self._keepalive_task = asyncio.create_task(self._keepalive_task_handler())
        self._alive = True

    async def _generate_tts_response(self, message):
        if not self._active_stream_id:
            self._language = self._state.tts_language
            self._voice = self._state.tts_voice
            try:
                await self._ensure_tts_alive()
            except Exception as exc:
                self.log.error("tts.connect.fatal_closing_session", error=str(exc))
                if self._send_message:
                    await self._send_message(ErrorMessage("TTS connection failed"))
                return
        if isinstance(message, LLMChunkMessage):
            substituted = apply_tts_substitutions(message.text())
            if substituted != message.text():
                message = LLMChunkMessage(substituted)
        await super()._generate_tts_response(message)

    async def _on_stream_finalized(self):
        self._last_stream_end = time.monotonic()
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


_square_client: SquareClient | None = None


class QueryParams(pydantic.BaseModel):
    language: str
    voice: str

    audio_in_format: str = "pcm_s16le"
    audio_in_sample_rate: int = 16000
    audio_in_num_channels: int = 1
    audio_out_format: str = "pcm_s16le"
    audio_out_sample_rate: int = 24000
    skip_opening_greeting: bool = False
    phone: bool = False
    caller_phone: str = ""
    pos: str = "clover"

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

    if params.pos == "square" and _square_client is not None and _square_client.available:
        state.pos_client = _square_client
    else:
        state.pos_client = get_client()

    def select_language_without_llm(language: str):
        config = LANGUAGE_CONFIG.get(language.lower(), LANGUAGE_CONFIG["english"])
        state.tts_language = config["tts_language"]
        state.tts_voice = config["tts_voice"]

    initial_language = LANGUAGES_MAP.get(params.language, "English").lower()
    # Phone calls: opening greeting is English — TTS must be set to English so
    # Maya reads the text correctly. After the caller says their language,
    # on_language_selected switches TTS to the chosen language automatically.
    # Browser: language was pre-selected in the UI dropdown, use it directly.
    select_language_without_llm("english" if params.phone else initial_language)

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
            system_message=get_system_message(
                "auto" if (params.phone or params.skip_opening_greeting) else LANGUAGES_MAP[params.language],
                caller_phone=params.caller_phone,
                pos_client=state.pos_client,
            ),
            tools=get_tools(state),
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            on_language_selected=select_language_without_llm,
            send_opening_greeting=not params.skip_opening_greeting,
            opening_greeting=(
                OPENING_GREETING
                if params.phone
                else OPENING_GREETINGS.get(initial_language, OPENING_GREETINGS["english"])
            ),
            language_preselected=not (params.phone or params.skip_opening_greeting),
            initial_language=initial_language,
        ),
        # AnthropicLLMProcessor(                 # ← Anthropic Claude Opus 4.8 (kept for easy revert)
        #     api_key=ANTHROPIC_API_KEY,
        #     model=ANTHROPIC_MODEL,
        #     system_message=get_system_message(
        #         "auto" if (params.phone or params.skip_opening_greeting) else LANGUAGES_MAP[params.language],
        #         caller_phone=params.caller_phone,
        #         pos_client=state.pos_client,
        #     ),
        #     tools=get_tools(state),
        #     temperature=LLM_TEMPERATURE,
        #     max_tokens=LLM_MAX_TOKENS,
        #     on_language_selected=select_language_without_llm,
        #     send_opening_greeting=not params.skip_opening_greeting,
        #     opening_greeting=(
        #         OPENING_GREETING
        #         if params.phone
        #         else OPENING_GREETINGS.get(initial_language, OPENING_GREETINGS["english"])
        #     ),
        #     language_preselected=not (params.phone or params.skip_opening_greeting),
        #     initial_language=initial_language,
        # ),
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


async def process_request(connection, request):
    """Handle non-WebSocket HTTP requests to the voice server.

    POST /internal/clover-reload: called by the Twilio bridge when it receives
    a Clover inventory webhook, so the menu cache is refreshed here where the
    CloverClient singleton lives.
    """
    if request.path == "/internal/clover-reload":
        client = get_client()
        if client is not None:
            client.schedule_menu_reload()
            log.info("clover.webhook.reload_via_bridge")
        return connection.respond(HTTPStatus.OK, {}, b"OK\n")
    return None


async def main():
    global _square_client

    log.info("Warming up VAD model...")
    VADProcessor.warmup()

    # ── Clover POS init ───────────────────────────────────────────────────────
    clover_client = CloverClient()
    try:
        await clover_client.init()
    except CloverError as exc:
        log.critical("clover.init.failed", error=str(exc))
        raise SystemExit(1) from exc
    set_client(clover_client)

    # ── Square POS init (optional — enabled when SQUARE_ACCESS_TOKEN is set) ──
    if os.getenv("SQUARE_ACCESS_TOKEN"):
        try:
            _square_client = SquareClient()
            await _square_client.init()
        except SquareError as exc:
            log.warning("square.init.failed", error=str(exc))
            _square_client = None
    # ─────────────────────────────────────────────────────────────────────────

    log.info("Starting WebSocket server", host=WEBSOCKET_HOST, port=WEBSOCKET_PORT)
    try:
        async with serve(handle, WEBSOCKET_HOST, WEBSOCKET_PORT, process_request=process_request) as server:
            await server.serve_forever()
    finally:
        await clover_client.close()
        if _square_client is not None:
            await _square_client.close()


if __name__ == "__main__":
    asyncio.run(main())
