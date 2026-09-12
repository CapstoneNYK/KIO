import { defineConfig } from "vite";
import react, { reactCompilerPreset } from "@vitejs/plugin-react";
import babel from "@rolldown/plugin-babel";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [
    react(),
    babel({ presets: [reactCompilerPreset()] }),
    tailwindcss(),
  ],
  server: {
    // 0.0.0.0으로 바인딩 -> 같은 와이파이의 다른 기기(노트북, 폰 등)에서
    // http://<PC-IP>:5173 으로 접속 가능해짐. 기본값은 localhost만 허용이라
    // 매번 `npm run dev -- --host`를 안 붙여도 되게 아예 설정에 넣어둠.
    host: true,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
