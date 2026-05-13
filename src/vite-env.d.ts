/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly BASE_URL: string;
  readonly VITE_REPO_SLUG?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
