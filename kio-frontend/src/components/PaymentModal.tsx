import { useState, useEffect } from "react";
import { LuX, LuCreditCard, LuSmartphone, LuGift, LuTicket, LuSparkles } from "react-icons/lu";
import { PaymentDetailModal } from "./PaymentDetailModal";
import { iconKT, iconCJONE, iconTMembership, iconTUzu, iconKakao, iconNaver } from "../assets";
import { useLearningStore } from "../store/learningStore";
import { useCartStore } from "../store/cartStore";
import { useCouponStore, calcDiscount } from "../store/couponStore";

interface PaymentModalProps {
  onClose: () => void;
  onSelect: (method: string) => void;
}

const DISCOUNT_METHODS = [
  { id: "kt", label: "KT VIP 초이스", icon: iconKT, iconSize: "w-10 h-10" },
  { id: "tmembership", label: "T 멤버십", icon: iconTMembership, iconSize: "w-10 h-10" },
  { id: "cjone", label: "CJ ONE", icon: iconCJONE, iconSize: "w-14 h-14" },
  { id: "uzu", label: "T우주 우주패스", icon: iconTUzu, iconSize: "w-14 h-14" },
];

const PAYMENT_METHODS = [
  { id: "card", label: "카드결제", icon: <LuCreditCard className="w-7 h-7" />, imgIcon: null },
  { id: "appcard", label: "앱카드", icon: <LuSmartphone className="w-7 h-7" />, imgIcon: null },
  { id: "kakao", label: "카카오페이", icon: null, imgIcon: iconKakao },
  { id: "voucher", label: "모바일상품권", icon: <LuTicket className="w-7 h-7" />, imgIcon: null },
  { id: "giftcard", label: "기프트카드", icon: <LuGift className="w-7 h-7" />, imgIcon: null },
  { id: "naver", label: "네이버페이", icon: null, imgIcon: iconNaver },
];

const DETAIL_SCREENS = ["payment_card", "payment_complete"];

export const PaymentModal = ({ onClose, onSelect }: PaymentModalProps) => {
  const [selectedMethod, setSelectedMethod] = useState<string | null>(null);
  const learningScreen = useLearningStore((s) => s.learningScreen);
  const guideScreen = useLearningStore((s) => s.guideScreen);
  const highlightPaymentMethod = useLearningStore((s) => s.highlightPaymentMethod);
  const setHighlightPaymentMethod = useLearningStore((s) => s.setHighlightPaymentMethod);
  const items = useCartStore((s) => s.items);
  const coupons = useCouponStore((s) => s.coupons);

  const cartTotal = items.reduce((sum, i) => sum + i.item.price * i.quantity, 0);
  const freeDiscount = items.reduce((sum, i) => (i.isFree ? sum + i.item.price : sum), 0);
  const couponDiscount = calcDiscount(coupons, cartTotal - freeDiscount);
  const remainingPrice = cartTotal - freeDiscount - couponDiscount;
  const hasAmountCoupon = coupons.some((c) => c.type === "amount");

  useEffect(() => {
    setSelectedMethod(DETAIL_SCREENS.includes(learningScreen ?? "") ? "card" : null);
  }, [learningScreen]);

  useEffect(() => {
    if (DETAIL_SCREENS.includes(guideScreen ?? "")) setSelectedMethod("card");
  }, [guideScreen]);

  const handleSelect = (id: string) => {
    setHighlightPaymentMethod(null);
    setSelectedMethod(id);
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
        <div className="flex items-center justify-center py-4 px-6 shrink-0">
          <h2 className="text-lg font-bold text-gray-900">결제수단 선택</h2>
          <button
            onClick={onClose}
            className="absolute right-4 text-gray-400 hover:text-gray-600 active:scale-90 transition"
          >
            <LuX className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 pb-6">
          {/* 상품권 차액 결제 안내 */}
          {hasAmountCoupon && remainingPrice > 0 && (
            <div className="mb-5 p-3 rounded-xl bg-amber-50 border border-amber-200">
              <p className="text-sm font-semibold text-amber-700">상품권이 적용됐어요</p>
              <p className="text-sm text-amber-600">
                남은 결제금액{" "}
                <span className="font-bold">{remainingPrice.toLocaleString()}원</span>을 결제해주세요
              </p>
            </div>
          )}

          {/* 할인수단 */}
          <p className="font-bold text-gray-800 text-lg mb-4">할인수단</p>
          <div className="grid grid-cols-2 gap-4 mb-8">
            {DISCOUNT_METHODS.map((m) => (
              <button
                key={m.id}
                onClick={() => handleSelect(m.id)}
                className="rounded-2xl border border-gray-200 py-5 px-4 flex items-center gap-3 active:brightness-95 transition"
              >
                <img src={m.icon} alt={m.label} className="w-10 h-10 object-contain shrink-0" />
                <span className="text-sm font-semibold text-gray-700 text-left leading-tight">{m.label}</span>
              </button>
            ))}
          </div>

          {/* 결제수단 */}
          <p className="font-bold text-gray-800 text-lg mb-4">결제수단</p>
          <div className="grid grid-cols-2 gap-4">
            {PAYMENT_METHODS.map((m) => {
              const isHighlighted = highlightPaymentMethod === m.id;
              return (
                <button
                  key={m.id}
                  onClick={() => handleSelect(m.id)}
                  className={`relative rounded-2xl py-5 px-4 flex items-center gap-4 active:brightness-95 transition
                    ${isHighlighted
                      ? "border-2 border-pink-400 bg-pink-50 ring-2 ring-pink-300 ring-offset-1"
                      : "border border-gray-200"
                    }`}
                >
                  {isHighlighted && (
                    <span className="absolute top-2 right-2 flex items-center gap-0.5 text-xs font-bold text-pink-500">
                      <LuSparkles className="w-3 h-3" />
                      추천
                    </span>
                  )}
                  <div className="w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center shrink-0 overflow-hidden">
                    {m.imgIcon
                      ? <img src={m.imgIcon} alt={m.label} className="w-full h-full object-cover" />
                      : <span className="text-gray-500">{m.icon}</span>
                    }
                  </div>
                  <span className={`text-base font-semibold ${isHighlighted ? "text-pink-600" : "text-gray-700"}`}>
                    {m.label}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {selectedMethod && (
        <PaymentDetailModal
          method={selectedMethod}
          onClose={() => setSelectedMethod(null)}
          onCancel={() => setSelectedMethod(null)}
          onComplete={() => { setSelectedMethod(null); onSelect(selectedMethod); }}
        />
      )}
    </div>
  );
};
