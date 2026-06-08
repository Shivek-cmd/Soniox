/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SONIOX_VOICE_BOT_WS_URL: string;
  readonly VITE_STORE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
