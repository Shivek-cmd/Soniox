# Docker Commands For This Project

Use these commands on the server after SSH:

```bash
ssh root@194.163.171.241
cd ~/Soniox
```

---

## Most Common Deploy Command

Use this after you push code from your laptop and run `git pull` on the server.

```bash
git pull
docker compose up -d --build
```

What it does:

- Pulls latest code from GitHub
- Rebuilds Docker images if needed
- Starts containers in the background
- Keeps the app running after you close SSH

Use when:

- You changed Python code
- You changed `docker-compose.yml`
- You changed a `Dockerfile`
- You changed dependencies
- You are not sure what changed and want the safe deploy command

---

## Check Running Containers

```bash
docker compose ps
```

Use when:

- You want to check if the app is running
- You want to see `voice-server`, `twilio-bridge`, and `caddy`

Expected services:

```text
caddy
twilio-bridge
voice-server
```

---

## Watch Logs

Watch all logs:

```bash
docker compose logs -f
```

Use when:

- You are testing a call
- You want to see what is happening live
- You do not know which service has the problem

Stop watching logs with:

```bash
Ctrl+C
```

---

## Watch Logs For One Service

Core voice bot logs:

```bash
docker compose logs -f voice-server
```

Use when:

- STT is not working
- OpenAI response is not working
- TTS is not speaking
- The bot logic feels wrong

Twilio bridge logs:

```bash
docker compose logs -f twilio-bridge
```

Use when:

- Twilio call is not connecting
- `/incoming-call` is failing
- `/media-stream` is failing
- Audio is not reaching the voice server

Caddy logs:

```bash
docker compose logs -f caddy
```

Use when:

- Domain is not opening
- HTTPS/SSL has an issue
- `voice.bizbull.ai` is not routing to the app

---

## Restart Services

Restart everything:

```bash
docker compose restart
```

Use when:

- You did not change code
- You only want to restart the running containers
- Something feels stuck

Restart only the core voice server:

```bash
docker compose restart voice-server
```

Use when:

- Only the AI voice pipeline is acting weird
- You changed environment variables for the voice server

Restart only the Twilio bridge:

```bash
docker compose restart twilio-bridge
```

Use when:

- Twilio connection is acting weird
- Incoming calls are not reaching the voice server

Restart only Caddy:

```bash
docker compose restart caddy
```

Use when:

- You changed `Caddyfile`
- Domain or HTTPS routing needs refresh

---

## Faster Deploy For Python-Only Changes

```bash
git pull
docker compose up -d --force-recreate voice-server twilio-bridge
```

Use when:

- You only changed Python files
- You did not change dependencies
- You did not change Dockerfiles

If unsure, use the safer full command:

```bash
git pull
docker compose up -d --build
```

---

## Stop The App

```bash
docker compose down
```

Use when:

- You want to stop all project containers
- You are doing maintenance

This keeps Docker images and volumes.

---

## Stop And Remove Volumes

```bash
docker compose down --volumes
```

Use carefully.

This removes Docker volumes too. In this project, Caddy stores SSL certificate data in the `caddy_data` volume, so removing volumes can force Caddy to request certificates again.

Avoid this unless you really need a clean reset.

---

## Clean Rebuild

```bash
docker compose build --no-cache
docker compose up -d
```

Use when:

- Docker is not picking up changes
- Dependency installation seems stale
- Normal `docker compose up -d --build` does not fix the issue

---

## Validate Compose File

```bash
docker compose config
```

Use when:

- You changed `docker-compose.yml`
- You want to check if the compose file is valid
- You want to see the final resolved Docker config

---

## General Docker Inspection

Show running containers:

```bash
docker ps
```

Show all containers, including stopped:

```bash
docker ps -a
```

Show Docker images:

```bash
docker images
```

Show Docker disk usage:

```bash
docker system df
```

---

## Best Daily Server Flow

Use this most of the time:

```bash
cd ~/Soniox
git pull
docker compose up -d --build
docker compose ps
docker compose logs -f
```
