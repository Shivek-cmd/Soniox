FROM node:22-alpine AS build

# Mirror source tree: /build/frontend/ + /build/menu.json
# so import "../../../menu.json" from src/utils/ resolves to /build/menu.json
WORKDIR /build

COPY frontend/package.json ./frontend/
RUN cd frontend && npm install

COPY frontend/ ./frontend/
COPY menu.json .

ENV NODE_ENV=production

ARG VITE_SONIOX_VOICE_BOT_WS_URL
ENV VITE_SONIOX_VOICE_BOT_WS_URL=${VITE_SONIOX_VOICE_BOT_WS_URL}

RUN echo "VITE_SONIOX_VOICE_BOT_WS_URL is set to: ${VITE_SONIOX_VOICE_BOT_WS_URL}"

RUN cd frontend && npm run build

FROM nginx:1.29.1-alpine AS prod

COPY --from=build /build/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /build/frontend/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
