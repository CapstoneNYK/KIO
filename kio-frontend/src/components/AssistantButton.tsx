import { useRef, useState, useEffect } from "react";
import { toBlob } from "html-to-image";
import { useNavigate, useLocation } from "react-router-dom";
import { logo } from "../assets";
import ktPoster from "../assets/images/poster/kt_poster.png";
import tPoster from "../assets/images/poster/t_poster.png";
import tpassPoster from "../assets/images/poster/tpass_poster.png";
import { useCategoryStore } from "../store/categoryStore";
import { useLearningStore } from "../store/learningStore";
import { useCartStore } from "../store/cartStore";
import { useCouponStore } from "../store/couponStore";
import { MENUS } from "../data/menus";
import { SpeechInput } from "./SpeechInput";

const HOME_CATEGORIES = [
  "전체",
  "커피",
  "디카페인",
  "스무디",
  "에이드",
  "주스",
  "티",
];
const MODAL_SCREENS = [
  "menu_modal",
  "cart",
  "order_confirm",
  "payment",
  "payment_card",
  "payment_complete",
];
const POSTER_ASSETS = [
  { url: ktPoster, name: "poster_kt" },
  { url: tPoster, name: "poster_t" },
  { url: tpassPoster, name: "poster_tpass" },
];
const TOTAL_SCREENS = 1 + HOME_CATEGORIES.length + MODAL_SCREENS.length + POSTER_ASSETS.length;

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
      // eslint-disable-next-line no-empty
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
  const [showGreeting, setShowGreeting] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => setShowGreeting(false), 6000);
    return () => clearTimeout(t);
  }, []);
  const pressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (location.pathname === "/") setMode("idle");
  }, [location.pathname]);
  const scanOpen = useCouponStore((s) => s.scanOpen);
  const guideScreen = useLearningStore((s) => s.guideScreen);
  const setCategory = useCategoryStore((s) => s.setCategory);
  const setLearningScreen = useLearningStore((s) => s.setLearningScreen);
  const { addItem, clear: clearCart } = useCartStore();

  useEffect(() => {
    if (scanOpen) setMode("idle");
  }, [scanOpen]);

  useEffect(() => {
    if (guideScreen) setMode("idle");
  }, [guideScreen]);

  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

  const captureAndLearn = async (
    screenName: string,
    progress: { count: number }
  ) => {
    setCurrentScreen(screenName);
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
    setLearnProgress(++progress.count);
  };

  const learnPoster = async (url: string, screenName: string, progress: { count: number }) => {
    setCurrentScreen(screenName);
    const res = await fetch(url);
    const blob = await res.blob();
    const formData = new FormData();
    formData.append("file", blob, "poster.png");
    formData.append("screen_name", screenName);
    await fetch(`${API}/learn`, { method: "POST", body: formData });
    setLearnProgress(++progress.count);
  };

  const startLearning = async () => {
    setMode("learning");
    setLearnProgress(0);
    const progress = { count: 0 };

    navigate("/");
    await sleep(800);
    await captureAndLearn("splash", progress);

    for (const { url, name } of POSTER_ASSETS) {
      await learnPoster(url, name, progress);
    }

    navigate("/home");
    await sleep(800);
    for (const cat of HOME_CATEGORIES) {
      setCategory(cat);
      await sleep(600);
      await captureAndLearn(`home_${cat}`, progress);
    }
    setCategory("전체");

    setLearningScreen("menu_modal");
    await sleep(600);
    await captureAndLearn("menu_modal", progress);
    setLearningScreen(null);
    await sleep(300);

    addItem(MENUS[0], 1, "HOT", [], false);
    await sleep(600);
    await captureAndLearn("cart", progress);

    setLearningScreen("order_confirm");
    await sleep(600);
    await captureAndLearn("order_confirm", progress);

    setLearningScreen("payment");
    await sleep(600);
    await captureAndLearn("payment", progress);

    setLearningScreen("payment_card");
    await sleep(800);
    await captureAndLearn("payment_card", progress);

    setLearningScreen("payment_complete");
    await sleep(1000);
    await captureAndLearn("payment_complete", progress);

    setLearningScreen(null);
    clearCart();
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
    setShowGreeting(false);
    if (mode === "idle") setMode("voice");
    else if (mode === "voice") setMode("idle");
  };

  return (
    <div
      id="kio-assistant"
      className="fixed top-4 right-4 z-9999 flex flex-row items-start gap-3"
    >
      {/* 학습 진행 패널 */}
      {mode === "learning" && (
        <div className="bg-white rounded-xl shadow-lg p-3 text-xs w-48 mt-2">
          <p className="font-bold text-gray-700 mb-1">화면 학습 중...</p>
          <p className="text-gray-400 mb-2 truncate">{currentScreen}</p>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-pink-400 transition-all duration-300"
              style={{ width: `${(learnProgress / TOTAL_SCREENS) * 100}%` }}
            />
          </div>
          <p className="text-right text-gray-400 mt-1">
            {learnProgress} / {TOTAL_SCREENS}
          </p>
        </div>
      )}

      {/* 음성 어시스턴트 채팅 패널 - 항상 마운트, 채팅 내역 유지 */}
      <div className={`bg-white rounded-2xl shadow-xl border border-pink-100 w-85 h-120 flex flex-col shrink-0 ${mode !== "voice" ? "hidden" : ""}`}>
        {/* 헤더 */}
        <div className="flex items-center justify-between px-4 py-3 bg-pink-50 border-b border-pink-100 shrink-0 rounded-t-2xl">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-pink-400 inline-block" />
            <span className="text-sm font-bold text-pink-700">
              KIO 어시스턴트
            </span>
          </div>
          <button
            onClick={() => setMode("idle")}
            className="text-pink-300 hover:text-pink-500 transition-colors text-base leading-none"
          >
            ✕
          </button>
        </div>

        {/* SpeechInput이 남은 높이를 채움 */}
        <div className="flex-1 min-h-0">
          <SpeechInput isOpen={mode === "voice"} />
        </div>
      </div>

      {/* KIO 버튼 + 말풍선 */}
      <div className="relative flex flex-col items-end shrink-0">
        {showGreeting && mode === "idle" && (
          <div className="absolute right-full top-0 mr-3 w-56 bg-white rounded-2xl shadow-lg px-4 py-3 text-sm text-gray-700 leading-relaxed border border-pink-100">
            <p className="font-semibold text-pink-600 mb-1">안녕하세요!</p>
            <p className="break-keep">저는 AI 키오스크 도우미 키오예요. 도움이 필요하면 저를 눌러주세요!</p>
            <div className="absolute -right-2 top-6 w-4 h-4 bg-white border-t border-r border-pink-100 rotate-45" />
          </div>
        )}
        <button
          onMouseDown={handleMouseDown}
          onMouseUp={handleMouseUp}
          onTouchStart={handleMouseDown}
          onTouchEnd={handleMouseUp}
          onClick={handleClick}
          disabled={mode === "learning"}
          className={`w-20 h-20 rounded-full transition-all duration-200
            ${
              mode === "learning"
                ? "animate-pulse ring-4 ring-yellow-400"
                : mode === "voice"
                ? "ring-4 ring-pink-400 scale-105"
                : "hover:ring-4 hover:ring-pink-400 hover:scale-105"
            }
            ${showGreeting && mode === "idle" ? "animate-kio-bounce" : ""}
          `}
          title="클릭: 음성 어시스턴트 | 길게 누르기: 화면 학습"
        >
          <img
            src={logo}
            alt="KIO"
            className="w-full h-full rounded-full object-cover"
          />
        </button>
      </div>
    </div>
  );
};
