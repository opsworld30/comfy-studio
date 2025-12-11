import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // 代码分割配置
    rollupOptions: {
      output: {
        manualChunks: {
          // React 核心库
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          // UI 组件库
          'vendor-radix': [
            '@radix-ui/react-accordion',
            '@radix-ui/react-alert-dialog',
            '@radix-ui/react-dialog',
            '@radix-ui/react-dropdown-menu',
            '@radix-ui/react-popover',
            '@radix-ui/react-select',
            '@radix-ui/react-tabs',
            '@radix-ui/react-tooltip',
          ],
          // 数据处理
          'vendor-data': ['@tanstack/react-query', 'axios', 'zustand'],
          // 图表库（较大）
          'vendor-charts': ['recharts'],
          // 流程图库（较大）
          'vendor-flow': ['@xyflow/react'],
          // 工具库
          'vendor-utils': ['date-fns', 'clsx', 'tailwind-merge', 'class-variance-authority'],
        },
      },
    },
    // 压缩配置
    minify: 'esbuild',
    // 启用 CSS 代码分割
    cssCodeSplit: true,
    // 资源内联阈值（小于 4kb 的资源内联）
    assetsInlineLimit: 4096,
    // 生成 sourcemap（生产环境可关闭）
    sourcemap: false,
    // chunk 大小警告阈值
    chunkSizeWarningLimit: 500,
  },
  // 优化依赖预构建
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-router-dom',
      '@tanstack/react-query',
      'axios',
      'zustand',
      'lucide-react',
    ],
  },
})
