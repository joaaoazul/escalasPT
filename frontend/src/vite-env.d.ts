/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Full WebSocket URL (wss://host/ws). Unset means same host as the page. */
  readonly VITE_WS_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
