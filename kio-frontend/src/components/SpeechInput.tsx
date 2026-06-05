import { useSTT } from "../utils/sttUtil";
import { useState, useEffect, useRef } from "react";
import { askApi } from "../api/askApi";
import { useCartStore } from "../store/cartStore";
import { useCouponStore } from "../store/couponStore";
import { useLearningStore } from "../store/learningStore";
import { MENUS } from "../data/menus";
import type { MenuItem, Temperature } from "../types/menu";

function findMenuItem(menuName: string | null): MenuItem | null {
  if (!menuName) return null;
  const normalized = menuName.replace(/\s/g, "").toLowerCase();

  // 정확히 일치하는 항목 우선
  const exact = MENUS.find((m) => m.title.replace(/\s/g, "").toLowerCase() === normalized);
  if (exact) return exact;

  // 메뉴 타이틀이 쿼리를 포함하는 경우
  const titleContains = MENUS.find((m) => m.title.replace(/\s/g, "").toLowerCase().includes(normalized));
  if (titleContains) return titleContains;

  // 쿼리가 메뉴 타이틀을 포함하는 경우 — 가장 긴 타이틀 우선 (아메리카노 < 디카페인 아메리카노)
  const candidates = MENUS.filter((m) => normalized.includes(m.title.replace(/\s/g, "").toLowerCase()));
  if (candidates.length === 0) return null;
  return candidates.reduce((best, m) => (m.title.length > best.title.length ? m : best));
}

const NUMBER_REF: { pattern: RegExp; index: number }[] = [
  { pattern: /1번|첫\s*번째|첫째/, index: 0 },
  { pattern: /2번|두\s*번째|둘째/, index: 1 },
];

export const SpeechInput = () => {
  const { transcript, listening, startListening, stopListening, resetTranscript } = useSTT("ko-KR");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [lastRecommended, setLastRecommended] = useState<string[]>([]);
  const answerRef = useRef<HTMLDivElement>(null);
  const addItem = useCartStore((s) => s.addItem);
  const cartItems = useCartStore((s) => s.items);
  const openScan = useCouponStore((s) => s.openScan);
  const setGuideScreen = useLearningStore((s) => s.setGuideScreen);
  const setHighlightPaymentMethod = useLearningStore((s) => s.setHighlightPaymentMethod);

  const resolveMenuFromRef = (query: string): string | null => {
    for (const { pattern, index } of NUMBER_REF) {
      if (pattern.test(query)) return lastRecommended[index] ?? null;
    }
    return null;
  };

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

      if (res.intent === "recommend" && res.recommended_menus) {
        setLastRecommended(res.recommended_menus);
      }

      if (res.intent === "payment") {
        if (cartItems.length === 0) {
          setAnswer("장바구니가 비어 있어요. 먼저 메뉴를 담아주세요.");
        } else {
          setHighlightPaymentMethod(res.payment_method ?? null);
          setGuideScreen(res.payment_method ? "payment" : "order_confirm");
        }
        return;
      }

      if (res.intent === "order") {
        const ordersToProcess = res.orders ?? [];

        if (ordersToProcess.length === 0 || ordersToProcess.every((o) => !o.menu)) {
          const refMenu = resolveMenuFromRef(query);
          if (refMenu) {
            const temperature: Temperature = refMenu.startsWith("핫") || refMenu.startsWith("따뜻") ? "HOT" : "ICE";
            const menuItem = findMenuItem(refMenu);
            if (menuItem) addItem(menuItem, 1, temperature, [], false);
          }
        } else {
          for (const orderInfo of ordersToProcess) {
            if (!orderInfo.menu) continue;
            const temperature = orderInfo.temperature as Temperature ?? "ICE";
            const menuItem = findMenuItem(orderInfo.menu);
            if (menuItem) addItem(menuItem, orderInfo.quantity ?? 1, temperature, [], false);
          }
        }
      }

      if (res.intent === "coupon") {
        openScan("assistant");
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
    <div className="flex flex-col h-full">
      {/* 채팅 히스토리 영역 (스크롤) */}
      <div className="flex-1 overflow-y-auto flex flex-col gap-3 p-3 min-h-0">
        {!transcript && !answer && !loading && (
          <p className="text-xs text-pink-300 text-center pt-4">
            아래 버튼을 눌러 말씀해 주세요
          </p>
        )}

        {transcript && (
          <div className="flex justify-end">
            <div className="bg-pink-500 text-white px-4 py-3 rounded-2xl rounded-br-sm max-w-xs shadow-sm">
              <p className="text-sm leading-relaxed">{transcript}</p>
            </div>
          </div>
        )}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-pink-100 px-4 py-3 rounded-2xl rounded-bl-sm shadow-sm">
              <div className="flex gap-1 items-center h-5">
                <span className="w-2 h-2 bg-pink-400 rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-2 h-2 bg-pink-400 rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-2 h-2 bg-pink-400 rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}

        {answer && !loading && (
          <div className="flex justify-start" ref={answerRef}>
            <div className="bg-white border border-pink-100 px-4 py-3 rounded-2xl rounded-bl-sm max-w-xs shadow-sm">
              <p className="text-sm text-gray-800 leading-relaxed">{answer}</p>
            </div>
          </div>
        )}
      </div>

      {/* 마이크 버튼 (하단 고정) */}
      <div className="flex flex-col items-center gap-2 p-3 border-t border-pink-50">
        <button
          onClick={handleButtonClick}
          className={`
            w-14 h-14 rounded-full flex items-center justify-center shadow-md transition-all duration-200
            ${listening
              ? "bg-red-500 hover:bg-red-600 scale-110 ring-4 ring-red-300 animate-pulse"
              : "bg-pink-500 hover:bg-pink-600 hover:scale-105"}
          `}
        >
          {listening ? (
            <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
          ) : (
            <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 1a4 4 0 0 1 4 4v6a4 4 0 0 1-8 0V5a4 4 0 0 1 4-4zm-1 17.93A8.001 8.001 0 0 1 4 11H6a6 6 0 0 0 12 0h2a8.001 8.001 0 0 1-7 7.93V22h2v2H9v-2h2v-2.07z" />
            </svg>
          )}
        </button>
        <p className={`text-xs font-medium ${listening ? "text-red-500" : "text-pink-500"}`}>
          {listening ? "듣는 중... 탭하면 중지" : "탭하면 음성 주문 시작"}
        </p>
      </div>
    </div>
  );
};
