import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

// 多页构建:index.html(主窗口/悬浮窗/迷你条)、selector.html(自由截图选择器)
export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: resolve(__dirname, '../app/webui'),
    emptyOutDir: true,
    target: 'es2020',
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        selector: resolve(__dirname, 'selector.html'),
      },
    },
  },
})
