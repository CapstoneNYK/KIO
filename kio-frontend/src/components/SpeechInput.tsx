import { useServerSTT } from "../utils/serverSttUtil";
import { useState, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { askApi } from "../api/askApi";
import type { CartAction } from "../api/askApi";
import { useCartStore } from "../store/cartStore";
import { useCouponStore } from "../store/couponStore";
import { useLearningStore } from "../store/learningStore";
import { useMenuStore } from "../store/menuStore";
import type { MenuItem, Temperature, MenuOption } from "../types/menu";

type Message = { role: "user" | "bot"; text: string };

// 봇 답변 렌더링: 줄바꿈을 살리고, "1번 …"/"1. …"로 시작하는 줄은 번호 배지가 있는 목록으로 보여준다
function BotText({ text }: { text: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      {text.split("\n").map((line, idx) => {
        const m = line.match(/^(\d+)\s*(?:번|\.)\s*(.+)$/);
        if (!m) return <p key={idx} className="text-[15px] leading-relaxed break-keep">{line}</p>;
        return (
          <p key={idx} className="flex items-start gap-2 text-[15px] leading-relaxed break-keep">
            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-pink-500 text-xs font-bold text-white">
              {m[1]}
            </span>
            <span className="font-semibold">{m[2]}</span>
          </p>
        );
      })}
    </div>
  );
}

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
    processing,
    startListening,
    stopListening,
    resetTranscript,
  } = useServerSTT("ko");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [lastRecommended, setLastRecommended] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const addItem = useCartStore((s) => s.addItem);
  const removeItem = useCartStore((s) => s.removeItem);
  const updateQuantity = useCartStore((s) => s.updateQuantity);
  const updateTemperature = useCartStore((s) => s.updateTemperature);
  const updateOptions = useCartStore((s) => s.updateOptions);
  const clearCart = useCartStore((s) => s.clear);
  const setIsPackaging = useCartStore((s) => s.setIsPackaging);
  const cartItems = useCartStore((s) => s.items);
  const menus = useMenuStore((s) => s.menus);
  const openScan = useCouponStore((s) => s.openScan);
  const setGuideScreen = useLearningStore((s) => s.setGuideScreen);
  const setHighlightPaymentMethod = useLearningStore(
    (s) => s.setHighlightPaymentMethod
  );
  const dismissPaymentOverlay = useLearningStore(
    (s) => s.dismissPaymentOverlay
  );

  // 백엔드가 해석한 장바구니 취소·변경 명령을 실제 장바구니에 적용한다.
  const applyCartActions = (actions: CartAction[]) => {
    const current = useCartStore.getState().items;
    const lines = (menu: string, temperature?: Temperature | null) =>
      current.filter(
        (i) => i.item.title === menu && (!temperature || i.temperature === temperature)
      );

    for (const action of actions) {
      if (action.type === "remove_all") {
        clearCart();
      } else if (action.type === "remove_last") {
        const all = useCartStore.getState().items;
        const last = all[all.length - 1];
        if (last) removeItem(last.cartId);
      } else if (action.type === "remove_item") {
        // 같은 메뉴가 여러 줄이면(온도가 다른 경우) 온도가 지정된 줄만, 아니면 해당 메뉴 전부
        lines(action.menu, action.temperature).forEach((i) => removeItem(i.cartId));
      } else if (action.type === "set_quantity") {
        const found = lines(action.menu, action.temperature);
        const target = found[found.length - 1];
        if (target) updateQuantity(target.cartId, action.quantity);
      } else if (action.type === "set_temperature") {
        const found = lines(action.menu);
        const target = found[found.length - 1];
        if (target) updateTemperature(target.cartId, action.temperature);
      } else if (action.type === "remove_line") {
        action.indexes.forEach((idx) => {
          const line = current[idx];
          if (line) removeItem(line.cartId);
        });
      } else if (action.type === "set_options") {
        const line = current[action.index];
        if (line) {
          if (action.count >= line.quantity) {
            updateOptions(line.cartId, action.options);
          } else {
            // 일부만 바꾸는 경우: 기존 줄 수량을 줄이고, 바뀐 옵션으로 새 줄을 만든다
            updateQuantity(line.cartId, line.quantity - action.count);
            addItem(line.item, action.count, line.temperature, action.options, line.isPackaging);
          }
        }
      } else if (action.type === "replace_item") {
        const found = lines(action.menu);
        const target = found[found.length - 1];
        const next = findMenuItem(action.to_menu, menus);
        if (target && next) {
          removeItem(target.cartId);
          addItem(next, target.quantity, target.temperature, target.options, target.isPackaging);
        }
      }
    }
  };

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
    } else if (!processing) {
      // 인식 결과를 기다리는 중에는 새 녹음을 또 시작하지 않도록 막는다.
      resetTranscript();
      startListening();
    }
  };

  const handleAsk = async (query: string) => {
    if (!query.trim()) return;
    setLoading(true);
    setMessages((prev) => [...prev, { role: "user", text: query }]);
    try {
      // 백엔드가 "처음에 시킨 카페라떼"처럼 특정 줄을 가리킬 수 있도록 수량·옵션까지 보낸다
      // 형식: "아이스 카페라떼 ×2 (시럽 적게, 샷추가 ×2, 포장)"
      const cartItemNames = cartItems.map((i) => {
        const extra = [
          ...i.options.map((o) => (o.count > 1 ? `${o.name} ×${o.count}` : o.name)),
          ...(i.isPackaging ? ["포장"] : []),
        ];
        return (
          `${i.temperature === "ICE" ? "아이스" : "따뜻한"} ${i.item.title}` +
          (i.quantity > 1 ? ` ×${i.quantity}` : "") +
          (extra.length ? ` (${extra.join(", ")})` : "")
        );
      });
      const res = await askApi(query, cartItemNames);
      let botText = res.answer;

      if (res.intent === "recommend" && res.recommended_menus) {
        setLastRecommended(res.recommended_menus);
      }

      if (res.intent === "cancel" || res.intent === "modify") {
        applyCartActions(res.cart_actions ?? []);
        setMessages((prev) => [...prev, { role: "bot", text: botText }]);
        return;
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
            // 구조화된 옵션(샷 개수, 시럽·크림 양, 사이즈)을 우선 사용하고, 없으면 기존 이름 목록으로 폴백
            const menuOptions: MenuOption[] = orderInfo.option_details
              ? orderInfo.option_details.map((d) => ({ name: d.name, count: d.count }))
              : (orderInfo.options ?? []).map((name) => ({ name, count: 1 }));
            const packaging = orderInfo.packaging === true;
            if (packaging) setIsPackaging(true);
            if (menuItem)
              addItem(
                menuItem,
                orderInfo.quantity ?? 1,
                temperature,
                menuOptions,
                packaging
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
    <div className="kio-chat flex flex-col h-full">
      {/* 채팅 히스토리 영역 (스크롤, 높이 고정) */}
      <div className="flex-1 overflow-y-auto flex flex-col gap-3 p-4 min-h-0 bg-pink-50/60">
        {messages.length === 0 && !listening && !loading && (
          <p className="text-sm text-pink-400 text-center pt-4">
            아래 버튼을 눌러 말씀해 주세요
          </p>
        )}

        {messages.map((msg, i) =>
          msg.role === "user" ? (
            <div key={i} className="flex justify-end">
              <div className="bg-pink-500 text-white px-4 py-3 rounded-2xl rounded-br-sm max-w-[85%] shadow-sm">
                <p className="text-[15px] leading-relaxed break-keep">{msg.text}</p>
              </div>
            </div>
          ) : (
            <div key={i} className="flex justify-start">
              <div className="bg-white border border-pink-200 px-4 py-3 rounded-2xl rounded-bl-sm max-w-[90%] shadow-sm text-gray-900">
                <BotText text={msg.text} />
              </div>
            </div>
          )
        )}

        {/* 음성 인식 중 실시간 미리보기 */}
        {listening && transcript && (
          <div className="flex justify-end opacity-60">
            <div className="bg-pink-500 text-white px-4 py-3 rounded-2xl rounded-br-sm max-w-[85%] shadow-sm">
              <p className="text-[15px] leading-relaxed">{transcript}</p>
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
          disabled={processing}
          className={`
            w-14 h-14 rounded-full flex items-center justify-center shadow-md transition-all duration-200
            ${
              listening
                ? "bg-red-500 hover:bg-red-600 ring-4 ring-red-300 animate-pulse"
                : processing
                ? "bg-pink-300 cursor-not-allowed"
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
          ) : processing ? (
            <div className="flex gap-1 items-center">
              <span className="w-1.5 h-1.5 bg-white rounded-full animate-bounce [animation-delay:0ms]" />
              <span className="w-1.5 h-1.5 bg-white rounded-full animate-bounce [animation-delay:150ms]" />
              <span className="w-1.5 h-1.5 bg-white rounded-full animate-bounce [animation-delay:300ms]" />
            </div>
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
          className={`text-sm font-medium ${
            listening ? "text-red-500" : "text-pink-500"
          }`}
        >
          {listening
            ? "듣는 중... 탭하면 중지"
            : processing
            ? "인식 처리 중..."
            : "탭하면 음성 주문 시작"}
        </p>
      </div>
    </div>
  );
};
