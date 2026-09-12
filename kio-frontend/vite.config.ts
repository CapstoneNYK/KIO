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
    // 마이크(getUserMedia) 등 브라우저 보안 API는 HTTPS 또는 localhost에서만 동작한다.
    // PC의 IP로 다른 기기(노트북 등)에서 접속하면 일반 HTTP라 막히므로, 자체
    // 서명 인증서로 HTTPS를 켜서 이 문제를 원천적으로 없앤다. 접속 시 브라우저가
    // "안전하지 않음" 경고를 한 번 띄우는데, 그때 "고급 > 계속 진행"을 누르면 된다.
    basicSsl(),
  ],
  server: {
    // 0.0.0.0으로 바인딩 -> 같은 와이파이의 다른 기기(노트북, 폰 등)에서
    // https://<PC-IP>:5173 으로 접속 가능해짐.
    host: true,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
