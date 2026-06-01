import { useSTT } from "../utils/sttUtil";
import { useState, useEffect, useRef } from "react";
import { askApi } from "../api/askApi";
import { useCartStore } from "../store/cartStore";
import { MENUS } from "../data/menus";
import type { MenuItem, Temperature } from "../types/menu";

function findMenuItem(menuName: string | null): MenuItem | null {
  if (!menuName) return null;
  const normalized = menuName.replace(/\s/g, "").toLowerCase();
  return (
    MENUS.find((m) => {
      const title = m.title.replace(/\s/g, "").toLowerCase();
      return title.includes(normalized) || normalized.includes(title);
    }) ?? null
  );
}

export const SpeechInput = () => {
  const { transcript, listening, startListening, stopListening, resetTranscript } = useSTT("ko-KR");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const answerRef = useRef<HTMLDivElement>(null);
  const addItem = useCartStore((s) => s.addItem);

  const handleButtonClick = () => {
    if (listening) {
      stopListening();
    } else {
      resetTranscript();
      setAnswer("");
      startListening();
    }
  };

  const handleAsk = async (query: string) => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const res = await askApi(query);
      setAnswer(res.answer);

      if (res.intent === "order" && res.order?.menu) {
        const menuItem = findMenuItem(res.order.menu);
        if (menuItem) {
          addItem(menuItem, 1, res.order.temperature as Temperature, [], false);
        }
      }
    } catch (error) {
      console.error(error);
      setAnswer("질문 처리 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!listening && transcript) {
      handleAsk(transcript);
    }
  }, [listening, transcript]);

  useEffect(() => {
    if (answer) answerRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [answer]);

  return (
    <div className="w-full max-w-md flex flex-col gap-4">
      {transcript && (
        <div className="flex justify-end">
          <div className="bg-amber-400 text-amber-950 px-4 py-3 rounded-2xl rounded-br-sm max-w-xs shadow-sm">
            <p className="text-sm leading-relaxed">{transcript}</p>
          </div>
        </div>
      )}

      {loading && (
        <div className="flex justify-start">
          <div className="bg-white border border-amber-200 px-4 py-3 rounded-2xl rounded-bl-sm shadow-sm">
            <div className="flex gap-1 items-center h-5">
              <span className="w-2 h-2 bg-amber-400 rounded-full animate-bounce [animation-delay:0ms]" />
              <span className="w-2 h-2 bg-amber-400 rounded-full animate-bounce [animation-delay:150ms]" />
              <span className="w-2 h-2 bg-amber-400 rounded-full animate-bounce [animation-delay:300ms]" />
            </div>
          </div>
        </div>
      )}

      {answer && !loading && (
        <div className="flex justify-start" ref={answerRef}>
          <div className="bg-white border border-amber-200 px-4 py-3 rounded-2xl rounded-bl-sm max-w-xs shadow-sm">
            <p className="text-sm text-gray-800 leading-relaxed">{answer}</p>
          </div>
        </div>
      )}

      <div className="flex flex-col items-center gap-2 pt-2">
        <button
          onClick={handleButtonClick}
          className={`
            w-16 h-16 rounded-full flex items-center justify-center shadow-md transition-all duration-200
            ${listening
              ? "bg-red-500 hover:bg-red-600 scale-110 ring-4 ring-red-300 animate-pulse"
              : "bg-amber-500 hover:bg-amber-600 hover:scale-105"}
          `}
        >
          {listening ? (
            <svg className="w-7 h-7 text-white" fill="currentColor" viewBox="0 0 24 24">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
          ) : (
            <svg className="w-7 h-7 text-white" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 1a4 4 0 0 1 4 4v6a4 4 0 0 1-8 0V5a4 4 0 0 1 4-4zm-1 17.93A8.001 8.001 0 0 1 4 11H6a6 6 0 0 0 12 0h2a8.001 8.001 0 0 1-7 7.93V22h2v2H9v-2h2v-2.07z" />
            </svg>
          )}
        </button>
        <p className="text-xs text-amber-700">
          {listening ? "듣는 중... 탭하면 중지" : "탭하면 음성 주문 시작"}
        </p>
      </div>
    </div>
  );
};
