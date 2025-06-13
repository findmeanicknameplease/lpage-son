// vite.config.ts

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // No 'build' section is needed, as Vite will automatically
  // use 'index.html' as the default entry point.
})