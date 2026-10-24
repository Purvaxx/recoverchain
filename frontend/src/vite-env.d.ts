/// <reference types="vite/client" />

interface ImportMetaEnv {
    /** API key sent as X-API-Key on mutating backend calls. Injected at build
     *  time from VITE_API_KEY; falls back to the backend dev key for local use. */
    readonly VITE_API_KEY?: string;
}

interface ImportMeta {
    readonly env: ImportMetaEnv;
}
