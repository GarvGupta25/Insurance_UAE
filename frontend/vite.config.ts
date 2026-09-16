import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
export default defineConfig(({ mode }) => {
  const apiTarget = loadEnv(mode, '.', 'HELM_').HELM_API_URL || 'http://127.0.0.1:8000';
  return { plugins: [react(), tailwindcss()], server: { proxy: { '/api': apiTarget, '/health': apiTarget } } };
});
