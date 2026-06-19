import asyncio
import json

import websockets

from messages import (
    ErrorMessage,
    TranscriptionEndpointMessage,
    TranscriptionMessage,
    UserAudioMessage,
)
from processors.message_processor import MessageProcessor

KEEPALIVE_MESSAGE = json.dumps({"type": "keepalive"})
KEEPALIVE_INTERVAL = 5

END_TOKEN = "<end>"
FIN_TOKEN = "<fin>"  # returned by manual {"type": "finalize"} — treated same as <end>


class STTProcessor(MessageProcessor):
    """Processor that transcribes user audio to text using streaming STT."""

    def __init__(
        self,
        api_key: str,
        api_host: str = "wss://stt-rt.soniox.com/transcribe-websocket",
        model: str = "stt-rt-preview",
        audio_format: str = "pcm_s16le",
        audio_sample_rate: int | None = 16000,
        num_channels: int | None = 1,
        language_hints: list[str] | None = None,
        context: str | None = None,
        max_endpoint_delay_ms: int = 500,
        endpoint_sensitivity: float | None = None,
        endpoint_latency_adjustment_level: int = 2,
    ):
        self._api_key = api_key
        self._api_host = api_host
        self._model = model

        self._audio_format = audio_format
        self._sample_rate = audio_sample_rate
        self._num_channels = num_channels

        self._language_hints = language_hints
        self._context = context
        self._max_endpoint_delay_ms = max_endpoint_delay_ms
        self._endpoint_sensitivity = endpoint_sensitivity
        self._endpoint_latency_adjustment_level = endpoint_latency_adjustment_level

        self._websocket = None
        self._receive_task = None
        self._keepalive_task = None
        self._send_task = None
        self._send_queue = asyncio.Queue(maxsize=100)

        self._send_message = None
        self._alive = False

    async def start(
        self,
        send_message,
        log,
    ):
        self.log = log.bind(processor="stt")
        self._send_message = send_message

        try:
            self._websocket = await websockets.connect(self._api_host)
        except websockets.exceptions.ConnectionClosed as e:
            self.log.error("Unable to connect to Soniox API", error=e)
            raise

        # Send the initial configuration message
        config = {
            "api_key": self._api_key,
            "model": self._model,
            "enable_endpoint_detection": True,
            "endpoint_latency_adjustment_level": self._endpoint_latency_adjustment_level,
            "max_endpoint_delay_ms": self._max_endpoint_delay_ms,
            "enable_non_final_tokens": True,
            "enable_language_identification": True,
            "language_hints": self._language_hints,
            "context": self._context,
        }
        if self._endpoint_sensitivity is not None:
            config["endpoint_sensitivity"] = self._endpoint_sensitivity

        # Set the audio format
        if (
            self._audio_format.startswith("pcm")
            or self._audio_format == "mulaw"
            or self._audio_format == "alaw"
        ):
            # Raw audio format
            config["audio_format"] = self._audio_format
            config["sample_rate"] = self._sample_rate
            config["num_channels"] = self._num_channels
        else:
            # auto, aac, aiff, amr, asf, flac, mp3, ogg, wav, webm
            config["audio_format"] = self._audio_format

        # Send the configuration message
        await self._websocket.send(json.dumps(config))

        self._receive_task = asyncio.create_task(self._receive_task_handler())
        self._keepalive_task = asyncio.create_task(self._keepalive_task_handler())
        self._send_task = asyncio.create_task(self._send_task_handler())

        self._alive = True

    async def cleanup(self):
        self._alive = False

        tasks = []

        if self._receive_task:
            self._receive_task.cancel()
            tasks.append(self._receive_task)
        if self._keepalive_task:
            self._keepalive_task.cancel()
            tasks.append(self._keepalive_task)
        if self._send_task:
            self._send_task.cancel()
            tasks.append(self._send_task)

        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass  # Task was cancelled

        if self._websocket:
            await self._websocket.close()
            self._websocket = None

    async def process(self, message):
        if not self._alive:
            return

        if isinstance(message, UserAudioMessage):
            try:
                self._send_queue.put_nowait(message.audio_data())
            except asyncio.QueueFull:
                self.log.debug("STT send queue full, dropping audio")

    async def _send_task_handler(self):
        try:
            while self._alive:
                audio_data = await self._send_queue.get()
                if not self._websocket:
                    break
                try:
                    await self._websocket.send(audio_data)
                except websockets.exceptions.ConnectionClosed:
                    self.log.error("Unable to send audio data to Soniox API")
                    if self._send_message:
                        await self._send_message(ErrorMessage("STT connection lost"))
                    await self.cleanup()
                    break
        except asyncio.CancelledError:
            pass

    async def _keepalive_task_handler(self):
        try:
            while self._alive:
                if self._websocket:
                    await self._websocket.send(KEEPALIVE_MESSAGE)
                else:
                    break

                await asyncio.sleep(KEEPALIVE_INTERVAL)

        except websockets.exceptions.ConnectionClosed:
            pass

    async def _receive_task_handler(self):
        if not self._websocket or not self._send_message:
            return

        try:
            async for message in self._websocket:
                content = json.loads(message)
                tokens = content["tokens"]

                if tokens:
                    final_tokens = []
                    non_final_tokens = []
                    has_endpoint = False

                    for token in tokens:
                        if token["is_final"] and token["text"] in (END_TOKEN, FIN_TOKEN):
                            has_endpoint = True
                        elif token["is_final"]:
                            final_tokens.append(token)
                        else:
                            non_final_tokens.append(token)

                    await self._send_message(
                        TranscriptionMessage(
                            final_tokens=final_tokens,
                            non_final_tokens=non_final_tokens,
                        )
                    )

                    if has_endpoint:
                        await self._send_message(TranscriptionEndpointMessage())

                error_type = content.get("error_type")
                error_message = content.get("error_message")
                if error_type:
                    # Flush any buffered transcript before closing
                    await self._send_message(TranscriptionEndpointMessage())
                    self.log.error(
                        "stt.error",
                        error_type=error_type,
                        error_message=error_message,
                    )

        except websockets.exceptions.ConnectionClosed:
            # Expected when closing the connection
            self.log.debug("Connection to Soniox API closed")
