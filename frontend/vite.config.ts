import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [react()],
    build: { sourcemap: false },
    server: {
      port: 3000,
      // Local development proxies /api to a deployed stack (e.g. https://dxxxx.cloudfront.net). No mock backend exists.
      proxy: env.VITE_DEV_PROXY_TARGET
        ? { '/api': { target: env.VITE_DEV_PROXY_TARGET, changeOrigin: true, secure: true } }
        : undefined,
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      globals: true,
    },
  };
});
