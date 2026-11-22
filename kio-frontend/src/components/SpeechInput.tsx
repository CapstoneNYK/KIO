import { useServerSTT } from "../utils/serverSttUtil";
import { useState, useEffect, useRef, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { askApi, sendFeedback } from "../api/askApi";
import type { CartAction, DialogState } from "../api/askApi";
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

const NUMBERED_LINE = /^(\d+)\s*(?:번|\.)\s*(.+)$/;

// 한 줄로 길게 이어진 안내는 문장마다 줄을 바꿔서 보여 준다(읽어 주는 음성은 원문 그대로)
const splitSentences = (line: string) =>
  line.split(/(?<=[.!?。])\s+/).map((sentence) => sentence.trim()).filter(Boolean);

// **굵게** 로 표시된 부분(담은 메뉴·수량 등 중요한 내용)을 굵은 강조색 글씨로 그린다
function renderBold(line: string): ReactNode {
  return line.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4 ? (
      <strong key={i} className="font-bold text-pink-600">{part.slice(2, -2)}</strong>
    ) : (
      part
    )
  );
}

function BotText({ text }: { text: string }) {
  const rows = text.split("\n").flatMap((line) => (NUMBERED_LINE.test(line) ? [line] : splitSentences(line)));
  // 되묻는 질문("…있으세요?")부터는 앞 내용과 간격을 벌려서 지금 답할 것이 눈에 띄게 한다
  const askAt = rows.findIndex((row, i) => i > 0 && /[?？]$/.test(row) && !NUMBERED_LINE.test(row));
  return (
    <div className="flex flex-col gap-1.5">
      {rows.map((line, idx) => {
        const m = line.match(NUMBERED_LINE);
        const gap = idx === askAt ? " mt-2" : "";
        if (!m) return <p key={idx} className={`text-[1em] leading-relaxed break-keep${gap}`}>{renderBold(line)}</p>;
        return (
          <p key={idx} className={`flex items-start gap-2 text-[1em] leading-relaxed break-keep${gap}`}>
            <span className="mt-0.5 flex h-[1.5em] w-[1.5em] shrink-0 items-center justify-center rounded-full bg-pink-500 text-[0.8em] font-bold text-white">
              {m[1]}
            </span>
            <span className="font-semibold">{renderBold(m[2])}</span>
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

// 인사말이 끝나기 전에 마이크를 먼저 열면 스피커 소리(인사말)가 같이 녹음될 수 있어서, 그 부분을 걷어낸다.
// 인사말 마지막 문장("어떤 음료 드릴까요?") 뒤의 말만 남기고, 인사말만 들어왔으면 빈 문자열을 돌려준다.
function stripGreetingEcho(text: string): string {
  const m = text.match(/드릴까요[?.!\s]*/);
  if (m && m.index !== undefined) return text.slice(m.index + m[0].length).trim();
  return /도우미|키오예요|말로\s*주문/.test(text) ? "" : text;
}

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
  // 옵션 되묻기(슬롯 채우기) 대화 상태: 서버가 만들고 다음 요청에 그대로 되돌려 보낸다.
  // 창을 닫아도 지우지 않아서 다시 열면 중단된 질문부터 이어진다.
  const dialogRef = useRef<DialogState | null>(null);
  // 질문을 말한 뒤 마이크를 자동으로 다시 켤지
  const autoListen = useRef(false);
  // 어르신이 인사말이 끝나기 전에 말을 꺼내도 놓치지 않도록, 인사말이 나오기 시작하고 1초 뒤에 마이크를 먼저 연다
  const earlyMic = useRef(false);
  const earlyMicTimer = useRef<number | undefined>(undefined);
  const ttsOn = useChatPrefs((s) => s.ttsOn) && ttsSupported;
  const spokenCount = useRef(0);
  const greeted = useRef(false);
  // 결제 안내를 말하는 중에 창이 닫혀도 음성을 끊지 않기 위한 표시
  const keepSpeaking = useRef(false);
  const setPackagingHint = useCartStore((s) => s.setPackagingHint);
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

  // 결제 쪽으로 넘어가면서 안내를 끝까지 읽어 준다 (창이 닫혀도 음성은 이어진다)
  const goToPayment = (method: string | null | undefined, spoken: string) => {
    setHighlightPaymentMethod(method ?? null);
    setGuideScreen("order_confirm"); // 먹고가기/가져가기를 먼저 고르게 하고, 고른 뒤 결제수단을 강조한다
    if (ttsOn && spoken) {
      keepSpeaking.current = true;
      speak(spoken);
    }
    useChatPrefs.getState().closeChat();
  };

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
      } else if (action.type === "set_temperature_part") {
        // "두 잔 중 한 잔만 따뜻하게": 일부만 온도를 바꾸면 줄을 나눈다
        const found = lines(action.menu);
        const target = found[found.length - 1];
        if (target) {
          const n = Math.min(action.count, target.quantity);
          if (n >= target.quantity) {
            updateTemperature(target.cartId, action.temperature);
          } else {
            updateQuantity(target.cartId, target.quantity - n);
            addItem(target.item, n, action.temperature, target.options, target.isPackaging);
          }
        }
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
        // 한 줄을 여러 번 나눠 적용할 수 있으니(하나는 연하게 하나는 샷 추가) 매번 최신 장바구니에서 그 줄을 다시 찾는다
        const stale = current[action.index];
        const line = stale && useCartStore.getState().items.find((i) => i.cartId === stale.cartId);
        if (line) {
          if (action.count >= line.quantity) {
            updateOptions(line.cartId, action.options);
          } else {
            updateQuantity(line.cartId, line.quantity - action.count);
            addItem(line.item, action.count, line.temperature, action.options, line.isPackaging);
          }
        }
      } else if (action.type === "set_packaging") {
        // 메뉴 없이 "가지고 갈게요"만 말한 경우: 주문 확인 화면에서 해당 버튼을 미리 강조한다
        setIsPackaging(action.packaging);
        setPackagingHint(action.packaging ? "take" : "dine");
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
    sendFeedback(msg.asked, msg.text.replace(/\*\*/g, ""), msg.intent ?? "").catch(() => {});
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
      const res = await askApi(query, cartItemNames, dialogRef.current);
      dialogRef.current = res.dialog ?? null;
      if (res.question && res.question !== query) {
        // 서버가 음성 인식 오류를 고쳤으면("티카페인"→"디카페인") 말풍선에도 고친 문장을 보여 준다
        setMessages((prev) => {
          const idx = prev.map((m) => m.role).lastIndexOf("user");
          return idx < 0 ? prev : prev.map((m, i) => (i === idx ? { ...m, text: res.question } : m));
        });
      }
      if (res.memo) useCartStore.getState().addMemo(res.memo, res.memo_menu);
      // 질문·추천에 답한 뒤에도 열린 대화가 있으면 계속 듣는다.
      // 메뉴를 추천했으면 손님이 '1번 주세요'처럼 고를 차례이므로 대화 상태가 없어도 마이크를 다시 켠다.
      autoListen.current =
        !!res.dialog || (res.intent === "recommend" && (res.recommended_menus?.length ?? 0) > 0);
      useChatPrefs.getState().setDialogActive(dialogRef.current !== null);
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
          // "가져갈게, 교환권 쓸게"처럼 포장/매장을 같이 말했으면 그 버튼도 함께 강조한다
          if (res.packaging === true || res.packaging === false) {
            setIsPackaging(res.packaging);
            setPackagingHint(res.packaging ? "take" : "dine");
          }
          const packName = res.packaging === true ? "가져가기" : res.packaging === false ? "먹고가기" : "먹고가기나 가져가기";
          const hint = res.payment_method
            ? `강조된 ${packName}를 먼저 눌러 주세요. 그다음 강조된 결제수단을 눌러 주세요.`
            : `${packName}를 눌러 주세요.`;
          goToPayment(res.payment_method, `${summarizeForSpeech(botText)} ${hint}`);
        }
        return;
      }

      if (res.intent === "order" || res.intent === "order_and_pay" || res.intent === "dialog") {
        dismissPaymentOverlay();
        const ordersToProcess = res.orders ?? [];

        if (
          res.intent !== "dialog" &&
          (ordersToProcess.length === 0 || ordersToProcess.every((o) => !o.menu))
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
            if (orderInfo.packaging === true) setPackagingHint("take");
            else if (orderInfo.packaging === false) setPackagingHint("dine");
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

        if (res.intent === "order_and_pay" || res.go_payment) {
          setMessages((prev) => [...prev, { role: "bot", text: botText }]);
          // 말풍선의 음성은 messages 효과가 읽으니, 닫혀도 끊기지 않게만 해 둔다
          keepSpeaking.current = ttsOn;
          setTimeout(() => goToPayment(res.payment_method, ""), 1000);
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
        { role: "bot", text: "잠시 연결이 원활하지 않아요. 다시 한 번 말씀해 주세요." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // 화면에서 직접 담거나 주문하기를 누르면 되묻기를 멈추고 알려준다(화면 조작이 우선)
  const dialogCancelCount = useChatPrefs((s) => s.dialogCancelCount);
  useEffect(() => {
    if (dialogCancelCount === 0) return;
    dialogRef.current = null;
    autoListen.current = false;
    setMessages((prev) => [
      ...prev,
      { role: "bot", text: "화면에서 직접 고르셔서 질문은 여기서 멈출게요." },
    ]);
  }, [dialogCancelCount]);

  const resetCount = useChatPrefs((s) => s.resetCount);
  useEffect(() => {
    if (resetCount > 0 || location.pathname === "/") {
      setMessages([]);
      setLastRecommended([]);
      dialogRef.current = null;
      autoListen.current = false;
      useChatPrefs.getState().setDialogActive(false);
      greeted.current = false;
      spokenCount.current = 0;
      window.clearTimeout(earlyMicTimer.current);
      earlyMic.current = false;
      stopSpeaking();
    }
  }, [location.pathname, resetCount]);

  useEffect(() => {
    if (isOpen) {
      resetTranscript();
      earlyMic.current = false;
      // 되묻는 도중에 창이 다시 열렸으면 마지막 질문을 한 번 더 말하고 이어서 듣는다
      const lastBot = dialogRef.current
        ? [...messages].reverse().find((m) => m.role === "bot")
        : undefined;
      if (lastBot) {
        if (ttsOn) speak(summarizeForSpeech(lastBot.text, lastBot.recommended), () => startListening());
        else startListening();
      } else if (ttsOn && !greeted.current && messages.length === 0) {
        greeted.current = true;
        speak(
          GREETING_SPEECH,
          () => { if (!earlyMic.current) startListening(); },
          () => {
            earlyMicTimer.current = window.setTimeout(() => {
              earlyMic.current = true;
              startListening();
            }, 1000);
          }
        );
      } else {
        startListening();
      }
    } else {
      window.clearTimeout(earlyMicTimer.current);
      earlyMic.current = false;
      stopListening();
      if (keepSpeaking.current) keepSpeaking.current = false;
      else stopSpeaking();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  useEffect(() => {
    if (!listening && transcript) {
      if (earlyMic.current) {
        earlyMic.current = false;
        const spoken = stripGreetingEcho(transcript);
        if (!spoken) {
          // 인사말만 녹음된 경우: 주문으로 처리하지 않고 다시 듣는다
          resetTranscript();
          startListening();
          return;
        }
        handleAsk(spoken);
        return;
      }
      handleAsk(transcript);
    }
  }, [listening, transcript]);

  useEffect(() => {
    if (messages.length < spokenCount.current) spokenCount.current = messages.length;
    const fresh = messages.slice(spokenCount.current);
    spokenCount.current = messages.length;
    if (!isOpen) return;
    const bots = fresh.filter((m) => m.role === "bot");
    if (bots.length === 0) return;
    // 되묻는 질문이면 말이 끝난 뒤 마이크를 자동으로 다시 켠다
    const reopen = () => {
      if (!autoListen.current) return;
      autoListen.current = false;
      resetTranscript();
      startListening();
    };
    if (!ttsOn) {
      if (autoListen.current) setTimeout(reopen, 400);
      return;
    }
    const text = bots
      .map((m) => summarizeForSpeech(m.text, m.recommended))
      .join(" ");
    speak(text, autoListen.current ? reopen : undefined);
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
