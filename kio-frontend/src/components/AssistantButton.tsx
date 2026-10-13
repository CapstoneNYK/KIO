import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { logo } from "../assets";
import { useLearningStore } from "../store/learningStore";
import { useCouponStore } from "../store/couponStore";
import { SpeechInput } from "./SpeechInput";
import { useChatPrefs, CHAT_SCALES } from "../store/chatPrefsStore";
import { ttsSupported, stopSpeaking } from "../utils/tts";

type Mode = "idle" | "voice";

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
      <div
        className={`kio-chat bg-white rounded-2xl shadow-2xl border-2 border-pink-400 ring-4 ring-pink-200/70 h-[40rem] max-h-[calc(100vh-2rem)] flex flex-col shrink-0 overflow-hidden ${
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
            onClick={() => setMode("idle")}
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
            <p className="font-bold text-pink-600 mb-1">안녕하세요!</p>
            <p className="break-keep">
              저는 AI 키오스크 도우미 키오예요. 도움이 필요하면 저를 눌러주세요!
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
