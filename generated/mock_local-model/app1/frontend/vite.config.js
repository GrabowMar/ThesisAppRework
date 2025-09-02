import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');

  const backendApiTarget = env.VITE_BACKEND_API_TARGET;
  const frontendPort = parseInt(env.VITE_FRONTEND_PORT)

  return {
    plugins: [react()],
    server: {
      host: true,
      port: frontendPort,
      strictPort: true,
      proxy: {
        '/api': {
          target: backendApiTarget,
          changeOrigin: true,
          secure: false,
        }
      }
    }
  };
});