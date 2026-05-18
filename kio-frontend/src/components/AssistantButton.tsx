import { useRef, useState } from "react";
import { toBlob } from "html-to-image";
import { useNavigate } from "react-router-dom";
import { logo } from "../assets";
import { useCategoryStore } from "../store/categoryStore";

const LEARN_SCREENS = ["전체", "커피", "디카페인", "스무디", "에이드", "주스", "티"];
const API = "http://localhost:8000/ocr";

type Mode = "idle" | "learning" | "querying";

interface Highlight {
  x1: number; y1: number; x2: number; y2: number;
  text: string; screen_name: string;
}

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
  const [queryText, setQueryText] = useState("");
  const [highlight, setHighlight] = useState<Highlight | null>(null);
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

  const handleQuery = async () => {
    const trimmed = queryText.trim();
    if (!trimmed) return;

    const res = await fetch(`${API}/query?text=${encodeURIComponent(trimmed)}`);
    const data = await res.json();
    if (!data.results.length) return;

    const best: Highlight = data.results[0];
    const cat = best.screen_name.replace("home_", "");

    navigate("/home");
    await new Promise((r) => setTimeout(r, 300));
    setCategory(cat === "전체" ? "전체" : cat);
    await new Promise((r) => setTimeout(r, 300));

    const dpr = window.devicePixelRatio || 1;
    setHighlight({ ...best, x1: best.x1 / dpr, y1: best.y1 / dpr, x2: best.x2 / dpr, y2: best.y2 / dpr });
    setMode("idle");
    setQueryText("");
    setTimeout(() => setHighlight(null), 3000);
  };

  const handleMouseDown = () => {
    pressTimer.current = setTimeout(() => startLearning(), 1500);
  };
  const handleMouseUp = () => clearTimeout(pressTimer.current);

  const handleClick = () => {
    if (mode === "idle") setMode("querying");
    else if (mode === "querying") setMode("idle");
  };

  return (
    <>
      <div id="kio-assistant" className="fixed top-4 right-4 z-[9999] flex flex-col items-end gap-2">
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
              : "ring-2 ring-pink-300 hover:ring-4 hover:ring-pink-400"}
          `}
          title="클릭: 검색 | 길게 누르기: 화면 학습"
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

        {mode === "querying" && (
          <div className="bg-white rounded-xl shadow-lg p-3 w-56">
            <p className="text-xs font-bold text-gray-700 mb-2">무엇을 찾으시나요?</p>
            <input
              autoFocus
              type="text"
              value={queryText}
              onChange={(e) => setQueryText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleQuery()}
              placeholder="예: 아메리카노"
              className="w-full text-sm border border-gray-200 rounded-lg px-2 py-1 outline-none focus:border-pink-300"
            />
            <button
              onClick={handleQuery}
              className="mt-2 w-full text-xs bg-pink-400 text-white rounded-lg py-1.5 hover:bg-pink-500 transition-colors"
            >
              찾기
            </button>
          </div>
        )}
      </div>

      {highlight && (
        <div
          className="fixed z-[9998] pointer-events-none"
          style={{
            left: highlight.x1,
            top: highlight.y1,
            width: highlight.x2 - highlight.x1,
            height: highlight.y2 - highlight.y1,
          }}
        >
          <div className="absolute inset-0 rounded-xl border-4 border-pink-500 animate-pulse" />
          <div className="absolute inset-0 rounded-xl bg-pink-300 opacity-20" />
        </div>
      )}
    </>
  );
};
