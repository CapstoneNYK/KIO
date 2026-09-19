import { useSTT } from "../utils/sttUtil";
import { useState, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { askApi } from "../api/askApi";
import { useCartStore } from "../store/cartStore";
import { useCouponStore } from "../store/couponStore";
import { useLearningStore } from "../store/learningStore";
import { useMenuStore } from "../store/menuStore";
import type { MenuItem, Temperature, MenuOption } from "../types/menu";

type Message = { role: "user" | "bot"; text: string };

function findMenuItem(menuName: string | null, menus: MenuItem[]): MenuItem | null {
  if (!menuName) return null;
  const normalized = menuName.replace(/\s/g, "").toLowerCase();

  // 정확히 일치하는 항목 우선
  const exact = menus.find(
    (m) => m.title.replace(/\s/g, "").toLowerCase() === normalized
  );
  if (exact) return exact;

  // 메뉴 타이틀이 쿼리를 포함하는 경우
  const titleContains = menus.find((m) =>
    m.title.replace(/\s/g, "").toLowerCase().includes(normalized)
  );
  if (titleContains) return titleContains;

  // 쿼리가 메뉴 타이틀을 포함하는 경우 — 가장 긴 타이틀 우선 (아메리카노 < 디카페인 아메리카노)
  const candidates = menus.filter((m) =>
    normalized.includes(m.title.replace(/\s/g, "").toLowerCase())
  );
  if (candidates.length === 0) return null;
  return candidates.reduce((best, m) =>
    m.title.length > best.title.length ? m : best
  );
}

const NUMBER_REF: { pattern: RegExp; index: number }[] = [
  { pattern: /1번|첫\s*번째|첫째/, index: 0 },
  { pattern: /2번|두\s*번째|둘째/, index: 1 },
];

export const SpeechInput = ({ isOpen }: { isOpen: boolean }) => {
  const {
    transcript,
    listening,
    startListening,
    stopListening,
    resetTranscript,
  } = useSTT("ko-KR");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [lastRecommended, setLastRecommended] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const addItem = useCartStore((s) => s.addItem);
  const cartItems = useCartStore((s) => s.items);
  const isPackaging = useCartStore((s) => s.isPackaging);
  const menus = useMenuStore((s) => s.menus);
  const openScan = useCouponStore((s) => s.openScan);
  const setGuideScreen = useLearningStore((s) => s.setGuideScreen);
  const setHighlightPaymentMethod = useLearningStore(
    (s) => s.setHighlightPaymentMethod
  );
  const dismissPaymentOverlay = useLearningStore(
    (s) => s.dismissPaymentOverlay
  );

  const resolveMenusFromRef = (query: string): string[] => {
    const resolved: string[] = [];
    for (const { pattern, index } of NUMBER_REF) {
      if (pattern.test(query)) {
        const menu = lastRecommended[index];
        if (menu) resolved.push(menu);
      }
    }
    return resolved;
  };

  const handleButtonClick = () => {
    if (listening) {
      stopListening();
    } else {
      resetTranscript();
      startListening();
    }
  };

  const handleAsk = async (query: string) => {
    if (!query.trim()) return;
    setLoading(true);
    setMessages((prev) => [...prev, { role: "user", text: query }]);
    try {
      const cartItemNames = cartItems.map(
        (i) =>
          `${i.temperature === "ICE" ? "아이스" : "따뜻한"} ${i.item.title}`
      );
      const res = await askApi(query, cartItemNames);
      let botText = res.answer;

      if (res.intent === "recommend" && res.recommended_menus) {
        setLastRecommended(res.recommended_menus);
      }

      if (res.intent === "payment") {
        if (cartItems.length === 0) {
          botText = "장바구니가 비어 있어요. 먼저 메뉴를 담아주세요.";
          setMessages((prev) => [...prev, { role: "bot", text: botText }]);
        } else {
          setHighlightPaymentMethod(res.payment_method ?? null);
          setGuideScreen(res.payment_method ? "payment" : "order_confirm");
          setMessages([]);
        }
        return;
      }

      if (res.intent === "order" || res.intent === "order_and_pay") {
        dismissPaymentOverlay();
        const ordersToProcess = res.orders ?? [];

        if (
          ordersToProcess.length === 0 ||
          ordersToProcess.every((o) => !o.menu)
        ) {
          const refMenus = resolveMenusFromRef(query);
          const quantity = ordersToProcess[0]?.quantity ?? 1;
          const added: string[] = [];
          for (const refMenu of refMenus) {
            const temperature: Temperature =
              refMenu.startsWith("핫") || refMenu.startsWith("따뜻")
                ? "HOT"
                : "ICE";
            const menuItem = findMenuItem(refMenu, menus);
            if (menuItem) {
              addItem(menuItem, quantity, temperature, [], false);
              added.push(refMenu);
            }
          }
          if (added.length > 0) {
            const qtyText = quantity > 1 ? ` ${quantity}개` : "";
            botText = `${added.join(
              ", "
            )}${qtyText}을(를) 장바구니에 담았습니다.`;
          }
        } else {
          for (const orderInfo of ordersToProcess) {
            if (!orderInfo.menu) continue;
            const temperature = (orderInfo.temperature as Temperature) ?? "ICE";
            const menuItem = findMenuItem(orderInfo.menu, menus);
            const menuOptions: MenuOption[] = (orderInfo.options ?? []).map(
              (name) => ({ name, count: 1 })
            );
            if (menuItem)
              addItem(
                menuItem,
                orderInfo.quantity ?? 1,
                temperature,
                menuOptions,
                false
              );
          }
        }

        if (res.intent === "order_and_pay") {
          setMessages((prev) => [...prev, { role: "bot", text: botText }]);
          setTimeout(() => {
            setHighlightPaymentMethod(res.payment_method ?? null);
            setGuideScreen(res.payment_method ? "payment" : "order_confirm");
          }, 1000);
          return;
        }
      }

      if (res.intent === "coupon") {
        openScan("assistant");
      }

      const newMessages: Message[] = [{ role: "bot", text: botText }];
      if (res.intent === "order" && res.discount_tip) {
        newMessages.push({ role: "bot", text: res.discount_tip });
      }
      setMessages((prev) => [...prev, ...newMessages]);
    } catch (error) {
      console.error(error);
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: "질문 처리 중 오류가 발생했습니다." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (location.pathname === "/") {
      setMessages([]);
      setLastRecommended([]);
    }
  }, [location.pathname]);

  useEffect(() => {
    if (isOpen) {
      resetTranscript();
      startListening();
    } else {
      stopListening();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  useEffect(() => {
    if (!listening && transcript) {
      handleAsk(transcript);
    }
  }, [listening, transcript]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, transcript]);

  return (
    <div className="flex flex-col h-full">
      {/* 채팅 히스토리 영역 (스크롤, 높이 고정) */}
      <div className="flex-1 overflow-y-auto flex flex-col gap-3 p-3 min-h-0">
        {messages.length === 0 && !listening && !loading && (
          <p className="text-xs text-pink-300 text-center pt-4">
            아래 버튼을 눌러 말씀해 주세요
          </p>
        )}

        {messages.map((msg, i) =>
          msg.role === "user" ? (
            <div key={i} className="flex justify-end">
              <div className="bg-pink-500 text-white px-4 py-3 rounded-2xl rounded-br-sm max-w-xs shadow-sm">
                <p className="text-sm leading-relaxed">{msg.text}</p>
              </div>
            </div>
          ) : (
            <div key={i} className="flex justify-start">
              <div className="bg-white border border-pink-100 px-4 py-3 rounded-2xl rounded-bl-sm max-w-xs shadow-sm">
                <p className="text-sm text-gray-800 leading-relaxed">
                  {msg.text}
                </p>
              </div>
            </div>
          )
        )}

        {/* 음성 인식 중 실시간 미리보기 */}
        {listening && transcript && (
          <div className="flex justify-end opacity-60">
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

        <div ref={messagesEndRef} />
      </div>

      {/* 마이크 버튼 (하단 고정) */}
      <div className="flex flex-col items-center gap-2 p-3 border-t border-pink-50">
        <button
          onClick={handleButtonClick}
          className={`
            w-14 h-14 rounded-full flex items-center justify-center shadow-md transition-all duration-200
            ${
              listening
                ? "bg-red-500 hover:bg-red-600 ring-4 ring-red-300 animate-pulse"
                : "bg-pink-500 hover:bg-pink-600 hover:scale-105"
            }
          `}
        >
          {listening ? (
            <svg
              className="w-6 h-6 text-white"
              fill="currentColor"
              viewBox="0 0 24 24"
            >
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
          ) : (
            <svg
              className="w-6 h-6 text-white"
              fill="currentColor"
              viewBox="0 0 24 24"
            >
              <path d="M12 1a4 4 0 0 1 4 4v6a4 4 0 0 1-8 0V5a4 4 0 0 1 4-4zm-1 17.93A8.001 8.001 0 0 1 4 11H6a6 6 0 0 0 12 0h2a8.001 8.001 0 0 1-7 7.93V22h2v2H9v-2h2v-2.07z" />
            </svg>
          )}
        </button>
        <p
          className={`text-xs font-medium ${
            listening ? "text-red-500" : "text-pink-500"
          }`}
        >
          {listening ? "듣는 중... 탭하면 중지" : "탭하면 음성 주문 시작"}
        </p>
      </div>
    </div>
  );
};
