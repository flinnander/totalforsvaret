import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: './',
  plugins: [react()],
  resolve: {
    dedupe: ['three', 'react', 'react-dom'],
  },
  optimizeDeps: {
    include: ['three', 'three-spritetext', 'react-force-graph-2d', 'react-force-graph-3d'],
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});
