"""Anthropic Claude drop-in replacement for LLMProcessor.

Same __init__ signature and process/start/cleanup interface as LLMProcessor so
main.py only needs to swap the import + class name. OpenAI code in llm.py is
untouched and can be restored by reverting main.py.

Key API differences handled here:
  - system message is a separate param, not a messages[] entry
  - tool schema uses input_schema instead of function.parameters
  - tool calls come as content_block events (type: tool_use) not delta.tool_calls
  - tool results go back as role:user content blocks (type: tool_result)
  - stop_reason: "tool_use" triggers another round; "end_turn" means done
"""

import asyncio
import json
import random
import re
import time
from difflib import SequenceMatcher
from typing import Any, Awaitable, Callable, List, Tuple

import anthropic

from messages import (
    ErrorMessage,
    LLMChunkMessage,
    LLMFullMessage,
    MetricsMessage,
    SessionStartMessage,
    TranscriptionEndpointMessage,
    TranscriptionMessage,
    UserSpeechStartMessage,
)
from processors.llm import (
    LANGUAGE_SELECTED_RESPONSES,
    LANGUAGE_SELECTION_PATTERNS,
    OPENING_GREETING,
    TOOL_CALL_FILLERS,
)
from processors.message_processor import MessageProcessor


def _openai_tools_to_anthropic(tools: list) -> list:
    """Convert OpenAI function tool schema to Anthropic tool schema."""
    result = []
    for tool in tools:
        if tool.get("type") != "function":
            continue
        fn = tool["function"]
        result.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return result


class AnthropicLLMProcessor(MessageProcessor):
    """LLM processor backed by Anthropic Claude (drop-in for LLMProcessor)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        system_message: str,
        base_url: str | None = None,
        tools: List[Tuple[dict, Callable[..., Awaitable[Any]]]] = [],
        temperature: float = 0.85,
        max_tokens: int = 1024,
        on_language_selected: Callable[[str], None] | None = None,
        send_opening_greeting: bool = True,
        opening_greeting: str | None = None,
        language_preselected: bool = False,
        initial_language: str = "english",
    ):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._system_message = system_message
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._on_language_selected = on_language_selected
        self._send_opening_greeting_enabled = send_opening_greeting

        # Convert tool schemas; keep callable map
        openai_tool_defs = [t[0] for t in tools]
        self._anthropic_tools = _openai_tools_to_anthropic(openai_tool_defs)
        self._tool_functions: dict[str, Callable] = {}
        for tool in tools:
            if tool[0].get("type") == "function":
                self._tool_functions[tool[0]["function"]["name"]] = tool[1]

        self._opening_greeting = opening_greeting or OPENING_GREETING
        self._current_language: str = initial_language
        self._active_task: asyncio.Task | None = None
        self._generation: int = 0  # incremented each time a new LLM task is created
        self._awaiting_language_selection = not language_preselected
        self._user_speech_started = False
        self._recent_assistant_texts: list[str] = []

        # Anthropic messages: role must alternate user / assistant.
        # System message is passed separately to the API, not stored here.
        self._messages: list[dict] = []

        self._llm_start_time: float | None = None
        self._first_token_sent: bool = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self, send_message, log):
        self.log = log.bind(processor="anthropic_llm")
        self._send_message = send_message

    async def cleanup(self):
        if self._active_task and not self._active_task.done():
            self._active_task.cancel()
            try:
                await self._active_task
            except asyncio.CancelledError:
                pass

    # ── Message routing ───────────────────────────────────────────────────────

    async def process(self, message):
        if isinstance(message, TranscriptionMessage):
            self._append_user_message(message)
            if self._awaiting_language_selection and self._user_speech_started:
                language = self._detect_language_selection(message.text())
                if language:
                    await self._handle_language_selection(language)

        elif isinstance(message, SessionStartMessage):
            if self._send_opening_greeting_enabled:
                await self._send_opening_greeting()
            else:
                self._record_opening_greeting()

        elif isinstance(message, TranscriptionEndpointMessage):
            if self._awaiting_language_selection:
                if not self._has_latest_user_message():
                    return
                language = self._latest_user_message_language_selection()
                if not language:
                    await self._send_language_prompt()
                    return
                await self._handle_language_selection(language)
                return
            # Cancel any in-flight task before creating a new one.
            # Soniox can fire TranscriptionEndpointMessage twice per utterance
            # (manual VAD finalize + automatic endpoint detection) — without this
            # guard, two LLM tasks run simultaneously and both write to TTS,
            # causing the "stream already closed" error and audio cuts.
            if self._active_task and not self._active_task.done():
                self._active_task.cancel()
            self._generation += 1  # invalidate any in-flight response that still completes
            self._active_task = asyncio.create_task(self._generate_llm_response())

        elif isinstance(message, UserSpeechStartMessage):
            self._user_speech_started = True
            if self._active_task and not self._active_task.done():
                self._active_task.cancel()
            self._generation += 1  # discard any response already in-flight

    # ── Message history helpers ───────────────────────────────────────────────

    def _append_user_message(self, message: TranscriptionMessage):
        if self._active_task and not self._active_task.done():
            self._active_task.cancel()

        text = message.final_text()
        if not text:
            return
        if self._is_likely_bot_echo(text):
            return

        if self._messages and self._messages[-1]["role"] == "user":
            last = self._messages[-1]["content"]
            if isinstance(last, str):
                self._messages[-1]["content"] = last + text
            else:
                self._messages[-1]["content"] = text
        else:
            self._messages.append({"role": "user", "content": text.lstrip()})

    def _append_assistant_text(self, text: str):
        if self._messages and self._messages[-1]["role"] == "assistant":
            last = self._messages[-1]["content"]
            if isinstance(last, str):
                self._messages[-1]["content"] = last + text
            else:
                self._messages[-1]["content"] = text
        else:
            self._messages.append({"role": "assistant", "content": text.lstrip()})

    def _has_latest_user_message(self):
        return bool(self._messages and self._messages[-1]["role"] == "user")

    # ── Greeting / language helpers ───────────────────────────────────────────

    async def _send_opening_greeting(self):
        chunk = LLMChunkMessage(self._opening_greeting)
        await self._send_message(chunk)
        self._append_assistant_text(self._opening_greeting)
        self._remember_assistant_text(self._opening_greeting)
        await self._send_message(LLMFullMessage(self._opening_greeting))

    def _record_opening_greeting(self):
        self._append_assistant_text(self._opening_greeting)
        self._remember_assistant_text(self._opening_greeting)

    async def _send_language_prompt(self):
        from processors.llm import LANGUAGE_PROMPT
        chunk = LLMChunkMessage(LANGUAGE_PROMPT)
        await self._send_message(chunk)
        self._append_assistant_text(LANGUAGE_PROMPT)
        self._remember_assistant_text(LANGUAGE_PROMPT)
        await self._send_message(LLMFullMessage(LANGUAGE_PROMPT))

    def _detect_language_selection(self, text: str):
        normalized = text.casefold()
        if not normalized.strip():
            return None
        for language, patterns in LANGUAGE_SELECTION_PATTERNS.items():
            if any(p.casefold() in normalized for p in patterns):
                return language
        return None

    def _latest_user_message_language_selection(self):
        if not self._has_latest_user_message():
            return None
        content = self._messages[-1].get("content", "")
        if not isinstance(content, str):
            return None
        return self._detect_language_selection(content)

    async def _handle_language_selection(self, language: str):
        self._awaiting_language_selection = False
        self._current_language = language
        if self._on_language_selected:
            self._on_language_selected(language)
        response_text = LANGUAGE_SELECTED_RESPONSES[language]
        chunk = LLMChunkMessage(response_text)
        await self._send_message(chunk)
        self._append_assistant_text(response_text)
        self._remember_assistant_text(response_text)
        await self._send_message(LLMFullMessage(response_text))

    def _remember_assistant_text(self, text: str):
        self._recent_assistant_texts.append(text)
        self._recent_assistant_texts = self._recent_assistant_texts[-6:]

    def _normalize_for_echo_check(self, text: str):
        return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()

    def _is_likely_bot_echo(self, text: str):
        normalized = self._normalize_for_echo_check(text)
        if not normalized:
            return False
        for assistant_text in self._recent_assistant_texts:
            norm_a = self._normalize_for_echo_check(assistant_text)
            if not norm_a:
                continue
            if len(normalized) > 20 and normalized in norm_a:
                return True
            if SequenceMatcher(None, normalized, norm_a).ratio() >= 0.72:
                return True
        return False

    # ── Core LLM call ─────────────────────────────────────────────────────────

    async def _generate_llm_response(self):
        if not self._messages or self._messages[-1]["role"] == "assistant":
            return

        my_gen = self._generation  # snapshot — if superseded, _generation will be higher
        last_msg = self._messages[-1]
        self.log.info("User → LLM", text=(str(last_msg.get("content") or ""))[:200])

        self._llm_start_time = time.perf_counter()
        self._first_token_sent = False

        try:
            await self._stream_response(my_gen)
        except asyncio.CancelledError:
            self.log.debug("LLM generation task was cancelled")
        except Exception as e:
            self.log.error(f"Error during LLM generation: {e}")
            if self._send_message:
                await self._send_message(ErrorMessage("Failed to generate response."))
        finally:
            self._active_task = None

    async def _stream_response(self, my_gen: int):
        full_text = ""
        _filler_sent = False

        def _is_current() -> bool:
            return my_gen == self._generation

        async with self._client.messages.stream(
            model=self._model,
            system=self._system_message,
            messages=self._messages,
            tools=self._anthropic_tools,
            max_tokens=self._max_tokens,
        ) as stream:
            # Collect tool_use blocks as we go
            tool_use_blocks: list[dict] = []
            current_tool_block: dict | None = None
            current_tool_json: str = ""

            async for event in stream:
                etype = event.type

                if etype == "content_block_start":
                    block = event.content_block
                    if block.type == "tool_use":
                        # Fire filler immediately so there's no dead air
                        if not _filler_sent and self._send_message and _is_current():
                            filler = random.choice(
                                TOOL_CALL_FILLERS.get(
                                    self._current_language,
                                    TOOL_CALL_FILLERS["english"],
                                )
                            )
                            await self._send_message(LLMChunkMessage(filler))
                            await self._send_message(LLMFullMessage(filler))
                            self._remember_assistant_text(filler)
                            _filler_sent = True
                        current_tool_block = {"id": block.id, "name": block.name}
                        current_tool_json = ""

                elif etype == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        text = delta.text
                        if text:
                            if not self._first_token_sent and self._llm_start_time and _is_current():
                                self._first_token_sent = True
                                first_token_ms = (time.perf_counter() - self._llm_start_time) * 1000
                                await self._send_message(MetricsMessage("llm_first_token_ms", first_token_ms))
                            if _is_current():
                                await self._send_message(LLMChunkMessage(text))
                            self._append_assistant_text(text)
                            full_text += text
                    elif delta.type == "input_json_delta":
                        current_tool_json += delta.partial_json

                elif etype == "content_block_stop":
                    if current_tool_block is not None:
                        try:
                            current_tool_block["input"] = json.loads(current_tool_json) if current_tool_json else {}
                        except json.JSONDecodeError:
                            current_tool_block["input"] = {}
                        tool_use_blocks.append(current_tool_block)
                        current_tool_block = None
                        current_tool_json = ""

        # All tool calls collected — now execute them
        if tool_use_blocks:
            # Add the assistant message with tool_use content blocks
            self._messages.append({
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": b["id"], "name": b["name"], "input": b["input"]}
                    for b in tool_use_blocks
                ],
            })

            # Execute each tool and collect results
            tool_results = []
            for block in tool_use_blocks:
                self.log.info("Calling tool", tool=block["name"], input=block["input"])
                result = await self._call_tool(block)
                self.log.info("Tool result", tool=block["name"], result=result)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": result,
                })

            # Add all tool results in one user message
            self._messages.append({"role": "user", "content": tool_results})

            # Recurse for LLM's follow-up response (only if still the current generation)
            if not _is_current():
                return
            await self._stream_response(my_gen)
            return

        # No tool calls — finalize
        if full_text:
            self.log.info("Sierra → User", text=full_text[:300])
            self._remember_assistant_text(full_text)
            if _is_current():
                await self._send_message(LLMFullMessage(full_text))
                if self._llm_start_time:
                    total_ms = (time.perf_counter() - self._llm_start_time) * 1000
                    await self._send_message(MetricsMessage("llm_total_ms", total_ms))

    async def _call_tool(self, block: dict) -> str:
        name = block["name"]
        arguments = block["input"]
        try:
            result = await self._tool_functions[name](**arguments)
            if not isinstance(result, str):
                return json.dumps(result)
            return result
        except Exception as e:
            self.log.error(f"Error calling tool {name}: {e}")
            return f"Error calling tool: {e}"
