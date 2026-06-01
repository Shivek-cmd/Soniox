FROM node:22-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

ENV NODE_ENV=production

ARG VITE_SONIOX_VOICE_BOT_WS_URL
ENV VITE_SONIOX_VOICE_BOT_WS_URL=${VITE_SONIOX_VOICE_BOT_WS_URL}

RUN echo "VITE_SONIOX_VOICE_BOT_WS_URL is set to: ${VITE_SONIOX_VOICE_BOT_WS_URL}"

RUN npm run build

FROM nginx:1.29.1-alpine AS prod

COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

