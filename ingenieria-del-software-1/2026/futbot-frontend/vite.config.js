import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  test: {
    include: ['tests/**/*.test.{js,jsx,ts,tsx}'],
    environment: 'jsdom',
    globals: true,
    setupFiles: './tests/setupTests.js',
    coverage: {
      include: ['src/**'],
    },
  },
})
