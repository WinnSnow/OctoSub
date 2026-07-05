import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { DEFAULT_DEV_API_PROXY_TARGET, DEFAULT_DEV_SERVER_PORT } from './dev.config.js';

const apiTarget = process.env.VITE_API_PROXY_TARGET || DEFAULT_DEV_API_PROXY_TARGET;

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: Number(process.env.PORT) || DEFAULT_DEV_SERVER_PORT,
    strictPort: true,
    proxy: {
      '/api': apiTarget,
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/setupTests.js',
    globals: true,
  },
});
