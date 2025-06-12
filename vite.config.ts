import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path'; // <-- ADD THIS LINE

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  
  // Your existing optimizeDeps configuration remains unchanged
  optimizeDeps: {
    exclude: ['lucide-react'],
  },

  // --- ADD THIS ENTIRE 'build' SECTION ---
  // This tells Vite to build your project as a multi-page application
  build: {
    rollupOptions: {
      input: {
        // 'main' will be your primary single-page application
        main: resolve(__dirname, 'index.html'),
        
        // 'dataDeletion' will be a separate, standalone HTML page
        // that satisfies the Facebook bot.
        dataDeletion: resolve(__dirname, 'data-deletion.html'),
      },
    },
  },
});