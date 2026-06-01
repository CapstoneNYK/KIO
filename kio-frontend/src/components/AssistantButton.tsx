import { useRef, useState } from "react";
import { toBlob } from "html-to-image";
import { useNavigate } from "react-router-dom";
import { logo } from "../assets";
import { useCategoryStore } from "../store/categoryStore";
import { SpeechInput } from "./SpeechInput";

const LEARN_SCREENS = ["전체", "커피", "디카페인", "스무디", "에이드", "주스", "티"];
const API = `${import.meta.env.VITE_API_URL}/ocr`;

type Mode = "idle" | "learning" | "voice";

function injectOklchOverride(): () => void {
  const entries: Array<{ prop: string; val: string }> = [];
  for (const sheet of Array.from(document.styleSheets)) {
    try {
      for (const rule of Array.from(sheet.cssRules)) {
        if (!(rule instanceof CSSStyleRule)) continue;
        const { style } = rule;
        for (let i = 0; i < style.length; i++) {
          const prop = style[i];
          const val = style.getPropertyValue(prop).trim();
          if (val.includes("oklch")) entries.push({ prop, val });
        }
      }
    } catch {}
  }
  if (entries.length === 0) return () => {};

  const container = document.createElement("div");
  container.style.display = "none";
  entries.forEach(({ val }) => {
    const div = document.createElement("div");
    div.style.color = val;
    container.appendChild(div);
  });
  document.body.appendChild(container);
  const overrides = entries.map(
    ({ prop }, i) => `${prop}: ${getComputedStyle(container.children[i]).color}`
  );
  document.body.removeChild(container);

  const el = document.createElement("style");
  el.id = "__oklch_fix";
  el.textContent = `:root { ${overrides.join("; ")} }`;
  document.head.appendChild(el);
  return () => el.remove();
}

async function captureScreen(): Promise<Blob> {
  const blob = await toBlob(document.body, {
    filter: (el) => (el as HTMLElement).id !== "kio-assistant",
  });
  if (!blob) throw new Error("캡처 실패");
  return blob;
}

export const AssistantButton = () => {
  const [mode, setMode] = useState<Mode>("idle");
  const [learnProgress, setLearnProgress] = useState(0);
  const [currentScreen, setCurrentScreen] = useState("");
  const pressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navigate = useNavigate();
  const setCategory = useCategoryStore((s) => s.setCategory);

  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

  const startLearning = async () => {
    setMode("learning");
    setLearnProgress(0);
    navigate("/home");
    await sleep(800);

    for (let i = 0; i < LEARN_SCREENS.length; i++) {
      const cat = LEARN_SCREENS[i];
      const screenName = `home_${cat}`;
      setCurrentScreen(screenName);
      setCategory(cat);
      await sleep(600);

      const removeOverride = injectOklchOverride();
      try {
        const blob = await captureScreen();
        const formData = new FormData();
        formData.append("file", blob, "screen.png");
        formData.append("screen_name", screenName);
        await fetch(`${API}/learn`, { method: "POST", body: formData });
      } finally {
        removeOverride();
      }
      setLearnProgress(i + 1);
    }

    setCategory("전체");
    setMode("idle");
    setLearnProgress(0);
    setCurrentScreen("");
  };

  const handleMouseDown = () => {
    pressTimer.current = setTimeout(() => startLearning(), 1500);
  };
  const handleMouseUp = () => {
    if (pressTimer.current) clearTimeout(pressTimer.current);
  };

  const handleClick = () => {
    if (mode === "idle") setMode("voice");
    else if (mode === "voice") setMode("idle");
  };

  return (
    <div id="kio-assistant" className="fixed top-4 right-4 z-9999 flex flex-col items-end gap-2">
      <button
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onTouchStart={handleMouseDown}
        onTouchEnd={handleMouseUp}
        onClick={handleClick}
        disabled={mode === "learning"}
        className={`w-20 h-20 rounded-full transition-all duration-200
          ${mode === "learning"
            ? "animate-pulse ring-4 ring-yellow-400"
            : mode === "voice"
            ? "ring-4 ring-amber-400"
            : "ring-2 ring-pink-300 hover:ring-4 hover:ring-pink-400"}
        `}
        title="클릭: 음성 입력 | 길게 누르기: 화면 학습"
      >
        <img src={logo} alt="KIO" className="w-full h-full rounded-full object-cover" />
      </button>

      {mode === "learning" && (
        <div className="bg-white rounded-xl shadow-lg p-3 text-xs w-52">
          <p className="font-bold text-gray-700 mb-1">화면 학습 중...</p>
          <p className="text-gray-400 mb-2 truncate">{currentScreen}</p>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-pink-400 transition-all duration-300"
              style={{ width: `${(learnProgress / LEARN_SCREENS.length) * 100}%` }}
            />
          </div>
          <p className="text-right text-gray-400 mt-1">
            {learnProgress} / {LEARN_SCREENS.length}
          </p>
        </div>
      )}

      {mode === "voice" && (
        <div className="bg-white rounded-2xl shadow-xl p-4 w-80">
          <div className="flex justify-between items-center mb-3">
            <p className="text-sm font-bold text-gray-700">무엇을 도와드릴까요?</p>
            <button
              onClick={() => setMode("idle")}
              className="text-gray-400 hover:text-gray-600 text-lg leading-none"
            >
              ✕
            </button>
          </div>
          <SpeechInput />
        </div>
      )}
    </div>
  );
};
