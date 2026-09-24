import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { logo } from "../assets";
import { useLearningStore } from "../store/learningStore";
import { useCouponStore } from "../store/couponStore";
import { SpeechInput } from "./SpeechInput";

type Mode = "idle" | "voice";

export const AssistantButton = () => {
  const [mode, setMode] = useState<Mode>("idle");
  const [showGreeting, setShowGreeting] = useState(true);

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
      {/* 음성 어시스턴트 채팅 패널 - 항상 마운트, 채팅 내역 유지 */}
      <div
        className={`bg-white rounded-2xl shadow-xl border border-pink-100 w-85 h-120 flex flex-col shrink-0 ${
          mode !== "voice" ? "hidden" : ""
        }`}
      >
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
