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
        className={`kio-chat bg-white rounded-2xl shadow-2xl border-2 border-pink-400 ring-4 ring-pink-200/70 w-[26rem] h-[38rem] max-h-[calc(100vh-2rem)] flex flex-col shrink-0 ${
          mode !== "voice" ? "hidden" : ""
        }`}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between px-5 py-3.5 bg-pink-500 shrink-0 rounded-t-xl">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-white inline-block" />
            <span className="text-base font-bold text-white">
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
