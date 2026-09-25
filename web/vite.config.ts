/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

// 开发时把 /api 转给本地的 Python 编排端（werewolf-server，默认 :8000）
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiTarget = env.WEREWOLF_API_PROXY || 'http://127.0.0.1:8000';

  return {
    plugins: [react(), tailwindcss()],
    // 相对路径：dist/ 可以直接丢到任意静态托管的任意子路径下
    base: './',
    resolve: {
      alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    server: {
      port: 5173,
      proxy: { '/api': { target: apiTarget, changeOrigin: true } },
    },
    preview: {
      port: 4173,
      proxy: { '/api': { target: apiTarget, changeOrigin: true } },
    },
    build: {
      outDir: 'dist',
      sourcemap: true,
      target: 'es2022',
    },
    test: {
      environment: 'jsdom',
      globals: false,
      setupFiles: ['./src/test/setup.ts'],
      css: false,
    },
  };
});
