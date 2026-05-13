import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// GitHub Pages base path — set VITE_BASE at build time (e.g. "/repo-name/") for project pages.
// Defaults to "./" so the build works on user pages, project pages, and any static host.
export default defineConfig({
  plugins: [react()],
  base: process.env.VITE_BASE ?? './',
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});
