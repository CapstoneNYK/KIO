import { defineConfig } from "vite";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import babel from "@rolldown/plugin-babel";
import tailwindcss from "@tailwindcss/vite";
import basicSsl from "@vitejs/plugin-basic-ssl";

export default defineConfig({
  plugins: [
    react(),
    babel({ presets: [reactCompilerPreset()] }),
    tailwindcss(),
    basicSsl(),
  ],
  server: {
    host: true,
    allowedHosts: true,
    proxy: {
      "/api": { target: "https://inbox-jpeg-experiment-incident.trycloudflare.com", changeOrigin: true },
      "/uploads": { target: "https://inbox-jpeg-experiment-incident.trycloudflare.com", changeOrigin: true },
    },
  },
});
