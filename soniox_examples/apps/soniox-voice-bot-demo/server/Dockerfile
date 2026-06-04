FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.14 /uv /uvx /bin/

WORKDIR /app

# Install deps first for layer caching
COPY server/pyproject.toml server/uv.lock ./
RUN uv sync

# Copy server source + menu.json (context is now soniox-voice-bot-demo/)
COPY server/ .
COPY menu.json .

# Pre-download Silero VAD model to avoid runtime delay
RUN uv run python -c "from processors.vad import VADProcessor; VADProcessor.warmup()"

ENV WEBSOCKET_HOST=0.0.0.0
ENV WEBSOCKET_PORT=8765
EXPOSE 8765

CMD ["uv", "run", "main.py"]
