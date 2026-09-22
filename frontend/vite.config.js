import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Lets you call /api/... in dev without CORS. Production uses VITE_API_URL.
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        // Split the big third-party libraries into their own chunks so a deploy
        // that only changes app code does not invalidate all of them, and so
        // the ones a given page does not need are never fetched.
        //
        // Measured 2026-09-22: before route-level splitting the whole app was a
        // single 777 kB chunk, so the login screen downloaded the admin course
        // editor before it could paint.
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          // Auth runs on every page, but it is large and changes rarely.
          supabase: ['@supabase/supabase-js'],
          // Only the lesson/chat/course screens render markdown.
          markdown: ['react-markdown', 'remark-gfm'],
          // Pulled in by the header's streak and XP widgets, so it is on the
          // critical path; at least keep it independently cacheable.
          motion: ['framer-motion'],
        },
      },
    },
  },
});
