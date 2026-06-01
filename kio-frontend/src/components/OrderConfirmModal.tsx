import { useState, useEffect } from "react";
import { LuX } from "react-icons/lu";
import { useCartStore } from "../store/cartStore";
import { useLearningStore } from "../store/learningStore";
import { OptionCounter } from "./OptionCounter";
import { PaymentModal } from "./PaymentModal";

interface OrderConfirmModalProps {
  onClose: () => void;
  onCancelAll: () => void;
  onNext: () => void;
}

const PAYMENT_SCREENS = ["payment", "payment_card", "payment_complete"];

export const OrderConfirmModal = ({ onClose, onCancelAll, onNext }: OrderConfirmModalProps) => {
  const { items, updateQuantity } = useCartStore();
  const [showPayment, setShowPayment] = useState(false);
  const learningScreen = useLearningStore((s) => s.learningScreen);

  const guideScreen = useLearningStore((s) => s.guideScreen);

  useEffect(() => {
    setShowPayment(PAYMENT_SCREENS.includes(learningScreen ?? ""));
  }, [learningScreen]);

  useEffect(() => {
    if (PAYMENT_SCREENS.includes(guideScreen ?? "")) setShowPayment(true);
  }, [guideScreen]);

  const totalPrice = items.reduce((sum, i) => sum + i.item.price * i.quantity, 0);
  const discountPrice = 0;

  const getOptionSummary = (cartItem: typeof items[number]) => {
    const parts: string[] = [];
    // 온도 표시
    parts.push(`${cartItem.item.title}(${cartItem.temperature})`);
    // 선택된 옵션만
    const activeOptions = cartItem.options.filter((o) => o.count > 0);
    activeOptions.forEach((o) => parts.push(`+${o.name}`));
    return parts;
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="relative bg-white rounded-2xl w-[80%] h-[88vh] flex flex-col overflow-hidden shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-center py-4 px-6 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">주문확인</h2>
          <button
            onClick={onClose}
            className="absolute right-4 text-gray-400 hover:text-gray-600 active:scale-90 transition"
          >
            <LuX className="w-5 h-5" />
          </button>
        </div>

        {/* 아이템 목록 */}
        <div className="flex-1 overflow-y-auto">
          {items.map((cartItem, idx) => {
            const summaryLines = getOptionSummary(cartItem);
            return (
              <div key={cartItem.cartId}>
                <div className="flex items-start gap-4 px-6 py-5">
                  {/* 이미지 + 카운터 */}
                  <div className="flex flex-col items-center gap-2 shrink-0">
                    <img
                      src={cartItem.item.img}
                      alt={cartItem.item.title}
                      className="w-16 h-16 object-contain"
                    />
                    <OptionCounter
                      count={cartItem.quantity}
                      min={1}
                      onDecrement={() => updateQuantity(cartItem.cartId, cartItem.quantity - 1)}
                      onIncrement={() => updateQuantity(cartItem.cartId, cartItem.quantity + 1)}
                    />
                  </div>

                  {/* 이름 + 옵션 */}
                  <div className="flex-1 min-w-0 pt-1">
                    <p className="font-semibold text-gray-900 text-base mb-1">
                      {cartItem.item.title}
                    </p>
                    <div className="flex flex-col gap-0.5">
                      <p className="text-sm" style={{ color: "#E17100" }}>
                        {summaryLines[0]}
                      </p>
                      {summaryLines.slice(1).map((line) => (
                        <p key={line} className="text-sm" style={{ color: "#E17100" }}>
                          {line}
                        </p>
                      ))}
                      <p className="text-sm text-gray-400">
                        {cartItem.isPackaging ? "포장 (일회용컵)" : "매장 (다회용컵)"}
                      </p>
                    </div>
                  </div>

                  {/* 가격 */}
                  <p className="text-orange-500 font-bold text-base shrink-0 pt-1">
                    {(cartItem.item.price * cartItem.quantity).toLocaleString()}원
                  </p>
                </div>

                {idx < items.length - 1 && (
                  <div className="mx-6 border-t border-gray-100" />
                )}
              </div>
            );
          })}
        </div>

        {/* 금액 요약 */}
        <div className="px-6 py-5" style={{ backgroundColor: "#FFFBEB" }}>
          <div className="flex justify-between mb-2">
            <span className="text-gray-700">주문 금액</span>
            <span className="font-semibold text-gray-900">{totalPrice.toLocaleString()}원</span>
          </div>
          <div className="flex justify-between mb-2">
            <span className="text-gray-700">할인 금액</span>
            <span className="font-semibold text-gray-900">{discountPrice.toLocaleString()}원</span>
          </div>
          <div className="flex justify-between">
            <span className="font-bold text-gray-900">결제 금액</span>
            <span className="font-bold text-orange-500 text-lg">
              {(totalPrice - discountPrice).toLocaleString()}원
            </span>
          </div>
        </div>

        {/* 버튼 */}
        <div className="flex gap-2 px-6 py-4 bg-white">
          <button
            onClick={onCancelAll}
            className="flex-1 py-3 rounded-xl border-2 border-gray-300 text-gray-600 font-bold active:bg-gray-50 transition"
          >
            전체취소
          </button>
          <button
            onClick={onClose}
            className="flex-1 py-3 rounded-xl border-2 font-bold active:opacity-80 transition"
            style={{ borderColor: "#FFB900", color: "#FFB900" }}
          >
            이전
          </button>
          <button
            onClick={() => setShowPayment(true)}
            className="flex-1 py-3 rounded-xl text-white font-bold active:brightness-95 transition"
            style={{ backgroundColor: "#FFB900" }}
          >
            다음
          </button>
        </div>
      </div>

      {showPayment && (
        <PaymentModal
          onClose={() => setShowPayment(false)}
          onSelect={(_method) => {
            setShowPayment(false);
            onNext();
          }}
        />
      )}
    </div>
  );
};
