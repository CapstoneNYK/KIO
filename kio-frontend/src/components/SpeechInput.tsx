import { useServerSTT } from "../utils/serverSttUtil";
import { useState, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { askApi, sendFeedback } from "../api/askApi";
import type { CartAction } from "../api/askApi";
import { useCartStore } from "../store/cartStore";
import { useCouponStore } from "../store/couponStore";
import { useLearningStore } from "../store/learningStore";
import { useMenuStore } from "../store/menuStore";
import type { MenuItem, Temperature, MenuOption } from "../types/menu";
import { useChatPrefs } from "../store/chatPrefsStore";
import {
  speak, stopSpeaking, summarizeForSpeech, ttsSupported,
  GREETING_TEXT, GREETING_SPEECH, GREETING_EXAMPLES,
} from "../utils/tts";

type Message = {
  role: "user" | "bot";
  text: string;
  recommended?: string[];
  asked?: string;
  intent?: string;
  reported?: boolean;
};

function BotText({ text }: { text: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      {text.split("\n").map((line, idx) => {
        const m = line.match(/^(\d+)\s*(?:번|\.)\s*(.+)$/);
        if (!m) return <p key={idx} className="text-[1em] leading-relaxed break-keep">{line}</p>;
        return (
          <p key={idx} className="flex items-start gap-2 text-[1em] leading-relaxed break-keep">
            <span className="mt-0.5 flex h-[1.5em] w-[1.5em] shrink-0 items-center justify-center rounded-full bg-pink-500 text-[0.8em] font-bold text-white">
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

  const exact = menus.find(
    (m) => m.title.replace(/\s/g, "").toLowerCase() === normalized
  );
  if (exact) return exact;

  const titleContains = menus.find((m) =>
    m.title.replace(/\s/g, "").toLowerCase().includes(normalized)
  );
  if (titleContains) return titleContains;

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
  const ttsOn = useChatPrefs((s) => s.ttsOn) && ttsSupported;
  const spokenCount = useRef(0);
  const greeted = useRef(false);
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
        lines(action.menu, action.temperature).forEach((i) => removeItem(i.cartId));
      } else if (action.type === "set_quantity") {
        const found = lines(action.menu, action.temperature);
        const target = found[found.length - 1];
        if (target) updateQuantity(target.cartId, action.quantity);
      } else if (action.type === "set_temperature") {
        const found = lines(action.menu);
        const target = found[found.length - 1];
        if (target) updateTemperature(target.cartId, action.temperature);
      } else if (action.type === "set_temperature_all") {
        current
          .filter((i) => action.menus.includes(i.item.title))
          .forEach((i) => updateTemperature(i.cartId, action.temperature));
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
    stopSpeaking();
    if (listening) {
      stopListening();
    } else if (!processing) {
      resetTranscript();
      startListening();
    }
  };

  const reportWrong = (index: number) => {
    const msg = messages[index];
    if (!msg?.asked || msg.reported) return;
    setMessages((prev) => prev.map((m, i) => (i === index ? { ...m, reported: true } : m)));
    sendFeedback(msg.asked, msg.text, msg.intent ?? "").catch(() => {});
  };

  const handleAsk = async (query: string) => {
    if (!query.trim()) return;
    setLoading(true);
    setMessages((prev) => [...prev, { role: "user", text: query }]);
    try {
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
        setMessages((prev) => [...prev, { role: "bot", text: botText, asked: query, intent: res.intent }]);
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
          useChatPrefs.getState().closeChat();
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
            useChatPrefs.getState().closeChat();
          }, 1000);
          return;
        }
      }

      if (res.intent === "coupon") {
        openScan("assistant");
      }

      const newMessages: Message[] = [
        {
          role: "bot",
          text: botText,
          recommended: res.intent === "recommend" ? res.recommended_menus : undefined,
          asked: query,
          intent: res.intent,
        },
      ];
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

  const resetCount = useChatPrefs((s) => s.resetCount);
  useEffect(() => {
    if (resetCount > 0 || location.pathname === "/") {
      setMessages([]);
      setLastRecommended([]);
      greeted.current = false;
      spokenCount.current = 0;
      stopSpeaking();
    }
  }, [location.pathname, resetCount]);

  useEffect(() => {
    if (isOpen) {
      resetTranscript();
      if (ttsOn && !greeted.current && messages.length === 0) {
        greeted.current = true;
        speak(GREETING_SPEECH, () => startListening());
      } else {
        startListening();
      }
    } else {
      stopListening();
      stopSpeaking();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  useEffect(() => {
    if (!listening && transcript) {
      handleAsk(transcript);
    }
  }, [listening, transcript]);

  useEffect(() => {
    if (messages.length < spokenCount.current) spokenCount.current = messages.length;
    const fresh = messages.slice(spokenCount.current);
    spokenCount.current = messages.length;
    if (!isOpen || !ttsOn) return;
    const bots = fresh.filter((m) => m.role === "bot");
    if (bots.length === 0) return;
    const text = bots
      .map((m) => summarizeForSpeech(m.text, m.recommended))
      .join(" ")
      .slice(0, 220);
    speak(text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, transcript]);

  return (
    <div className="kio-chat flex flex-col h-full">
      <div className="flex-1 overflow-y-auto flex flex-col gap-3 p-4 min-h-0 bg-pink-50/60">
        {messages.length === 0 && !loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-pink-200 px-4 py-3 rounded-2xl rounded-bl-sm max-w-[92%] shadow-sm text-gray-900">
              <p className="font-bold text-pink-600 text-[1em] mb-1">안녕하세요!</p>
              <p className="text-[1em] leading-relaxed break-keep">{GREETING_TEXT.replace("안녕하세요! ", "")}</p>
              <p className="mt-2 text-[0.85em] font-semibold text-gray-500">이렇게 말씀해 보세요</p>
              <ul className="mt-1 flex flex-col gap-1">
                {GREETING_EXAMPLES.map((ex) => (
                  <li key={ex} className="rounded-lg bg-pink-50 px-3 py-1.5 text-[0.95em] text-pink-700 break-keep">
                    “{ex}”
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {messages.map((msg, i) =>
          msg.role === "user" ? (
            <div key={i} className="flex justify-end">
              <div className="bg-pink-500 text-white px-4 py-3 rounded-2xl rounded-br-sm max-w-[85%] shadow-sm">
                <p className="text-[1em] leading-relaxed break-keep">{msg.text}</p>
              </div>
            </div>
          ) : (
            <div key={i} className="flex justify-start">
              <div className="bg-white border border-pink-200 px-4 py-3 rounded-2xl rounded-bl-sm max-w-[90%] shadow-sm text-gray-900">
                <BotText text={msg.text} />
                {msg.asked && (
                  <button
                    onClick={() => reportWrong(i)}
                    disabled={msg.reported}
                    className="mt-2 text-[0.7em] text-gray-400 underline disabled:no-underline disabled:text-gray-300"
                  >
                    {msg.reported ? "의견이 접수됐어요" : "잘못 알아들었어요"}
                  </button>
                )}
              </div>
            </div>
          )
        )}

        {listening && transcript && (
          <div className="flex justify-end opacity-60">
            <div className="bg-pink-500 text-white px-4 py-3 rounded-2xl rounded-br-sm max-w-[85%] shadow-sm">
              <p className="text-[1em] leading-relaxed">{transcript}</p>
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

      <div className="flex flex-col items-center gap-2 p-3 border-t border-pink-100 bg-white">
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
          className={`text-[0.9em] font-medium ${
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
