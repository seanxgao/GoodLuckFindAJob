import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Host must be "0.0.0.0" to listen on all network interfaces, allowing LAN access.
    // Users can access the site via http://<local-ip>:5174/
    host: "0.0.0.0",
    port: 5174,
    strictPort: true,
  },
})
