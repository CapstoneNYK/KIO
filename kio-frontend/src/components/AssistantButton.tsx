import { useState, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { logo } from "../assets";
import { useLearningStore } from "../store/learningStore";
import { useCouponStore } from "../store/couponStore";
import { SpeechInput } from "./SpeechInput";
import { useChatPrefs, CHAT_SCALES } from "../store/chatPrefsStore";
import { ttsSupported, stopSpeaking } from "../utils/tts";

type Mode = "idle" | "voice";

// 음성 창이 열려 있을 때 화면을 직접 만지면 창을 숨기고,
// 되묻는 대화가 남아 있으면 이만큼 가만히 있을 때 다시 연다.
const REOPEN_AFTER_MS = 4000;

export const AssistantButton = () => {
  const [mode, setMode] = useState<Mode>("idle");
  const [showGreeting, setShowGreeting] = useState(true);
  const { scale, setScale, ttsOn, setTtsOn } = useChatPrefs();

  useEffect(() => {
    if (!showGreeting) return;
    const t = setTimeout(() => setShowGreeting(false), 5000);
    return () => clearTimeout(t);
  }, [showGreeting]);
  const location = useLocation();

  useEffect(() => {
    if (location.pathname === "/") {
      setMode("idle");
      setShowGreeting(true);
    }
  }, [location.pathname]);
  const scanOpen = useCouponStore((s) => s.scanOpen);
  const guideScreen = useLearningStore((s) => s.guideScreen);

  useEffect(() => {
    if (scanOpen) setMode("idle");
  }, [scanOpen]);

  useEffect(() => {
    if (guideScreen) setMode("idle");
  }, [guideScreen]);

  const closeCount = useChatPrefs((s) => s.closeCount);
  useEffect(() => {
    if (closeCount > 0) setMode("idle");
  }, [closeCount]);

  // 음성 창을 화면 터치로 자동으로 닫았는지(직접 ✕/버튼으로 닫은 것과 구분)
  const autoClosed = useRef(false);
  const reopenTimer = useRef<number | undefined>(undefined);
  const modeRef = useRef<Mode>("idle");

  // 시작 화면에서 '말로 주문'을 고르면 바로 음성 창을 연다
  const openCount = useChatPrefs((s) => s.openCount);
  useEffect(() => {
    if (openCount > 0) {
      setShowGreeting(false);
      autoClosed.current = false;
      setMode("voice");
    }
  }, [openCount]);

  // 화면을 만지거나 스크롤하면 음성 창만 숨긴다(대화 상태와 말한 내용은 그대로).
  // 손을 떼고 잠시 지나면 중단된 질문부터 다시 이어간다.
  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);
  useEffect(() => {
    const armReopen = () => {
      window.clearTimeout(reopenTimer.current);
      if (!autoClosed.current || !useChatPrefs.getState().dialogActive) return;
      reopenTimer.current = window.setTimeout(() => {
        const busy = useLearningStore.getState().guideScreen || useCouponStore.getState().scanOpen;
        if (autoClosed.current && !busy) {
          autoClosed.current = false;
          setMode("voice");
        }
      }, REOPEN_AFTER_MS);
    };
    const onTouch = (e: Event) => {
      const panel = document.getElementById("kio-assistant");
      if (panel && e.target instanceof Node && panel.contains(e.target)) return;
      if (modeRef.current === "voice") {
        autoClosed.current = true;
        setMode("idle");
      }
      armReopen();
    };
    const events = ["pointerdown", "wheel", "touchmove", "scroll"] as const;
    events.forEach((ev) => document.addEventListener(ev, onTouch, { capture: true, passive: true }));
    return () => {
      events.forEach((ev) => document.removeEventListener(ev, onTouch, { capture: true }));
      window.clearTimeout(reopenTimer.current);
    };
  }, []);

  const handleClick = () => {
    autoClosed.current = false;
    setShowGreeting(false);
    if (mode === "idle") setMode("voice");
    else if (mode === "voice") setMode("idle");
  };

  return (
    <div
      id="kio-assistant"
      className="fixed top-4 right-4 z-9999 flex flex-row items-start gap-3"
    >
      <div
        className={`kio-chat bg-white rounded-2xl shadow-2xl border-2 border-pink-400 ring-4 ring-pink-200/70 h-[40rem] max-h-[calc(100dvh-2rem)] flex flex-col shrink-0 overflow-hidden ${
          mode !== "voice" ? "hidden" : ""
        }`}
        style={{ "--kio-s": scale, width: "min(calc(26rem * var(--kio-s)), calc(100vw - 8rem))" } as React.CSSProperties}
      >
        <div className="flex items-center justify-between px-5 py-3.5 bg-pink-500 shrink-0 rounded-t-xl">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-white inline-block" />
            <span className="text-[1em] font-bold text-white">
              KIO 어시스턴트
            </span>
          </div>
          <button
            onClick={() => { autoClosed.current = false; setMode("idle"); }}
            className="text-pink-100 hover:text-white transition-colors text-lg leading-none"
          >
            ✕
          </button>
        </div>

        <div className="flex items-center justify-between gap-2 px-3 py-2 bg-pink-50 border-b border-pink-100 shrink-0">
          <div className="flex items-center gap-1" role="group" aria-label="글자 크기">
            <span className="text-[0.8em] font-semibold text-pink-700 mr-1">글자</span>
            {CHAT_SCALES.map((c) => (
              <button
                key={c.value}
                onClick={() => setScale(c.value)}
                className={`rounded-lg border px-2 py-1 text-[0.8em] font-bold transition ${
                  scale === c.value
                    ? "bg-pink-500 border-pink-500 text-white"
                    : "bg-white border-pink-200 text-pink-600 active:bg-pink-100"
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>
          {ttsSupported && (
            <button
              onClick={() => { if (ttsOn) stopSpeaking(); setTtsOn(!ttsOn); }}
              className={`rounded-lg border px-3 py-1 text-[0.8em] font-bold transition ${
                ttsOn ? "bg-pink-500 border-pink-500 text-white" : "bg-white border-pink-200 text-pink-600"
              }`}
              aria-pressed={ttsOn}
            >
              {ttsOn ? "🔊 소리 켜짐" : "🔇 소리 꺼짐"}
            </button>
          )}
        </div>

        <div className="flex-1 min-h-0">
          <SpeechInput isOpen={mode === "voice"} />
        </div>
      </div>

      <div className="relative flex flex-col items-end shrink-0">
        {showGreeting && mode === "idle" && (
          <div
            className="kio-chat absolute right-full top-0 mr-3 w-72 bg-white rounded-2xl shadow-xl px-5 py-4 text-gray-800 leading-relaxed border-2 border-pink-300"
            style={{ "--kio-s": scale } as React.CSSProperties}
          >
            <p className="break-keep">
              말로 주문하고 싶으시면 <span className="font-bold text-pink-600">음성주문</span>을 클릭하세요
            </p>
            <div className="absolute -right-2 top-6 w-4 h-4 bg-white border-t border-r border-pink-100 rotate-45" />
          </div>
        )}
        <button
          onClick={handleClick}
          className={`w-20 h-20 rounded-full transition-all duration-200
            ${
              mode === "voice"
                ? "ring-4 ring-pink-400 scale-105"
                : "hover:ring-4 hover:ring-pink-400 hover:scale-105"
            }
            ${showGreeting && mode === "idle" ? "animate-kio-bounce" : ""}
          `}
          title="클릭: 음성 어시스턴트"
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
