import { useState } from "react";
import { LuX, LuCreditCard, LuSmartphone, LuGift, LuTicket } from "react-icons/lu";
import { PaymentDetailModal } from "./PaymentDetailModal";

interface PaymentModalProps {
  onClose: () => void;
  onSelect: (method: string) => void;
}

const DISCOUNT_METHODS = [
  { id: "kt", label: "KT VIP 쏘이스", bg: "#E8001D", textColor: "#fff", prefix: "kt" },
  { id: "tmembership", label: "T 멤버십", bg: "#E4003B", textColor: "#fff", prefix: "T" },
  { id: "cjone", label: "CJ ONE", bg: "#006DB7", textColor: "#fff", prefix: "CJ" },
  { id: "uzu", label: "T우주 우주패스", bg: "#E4003B", textColor: "#fff", prefix: "T우주" },
  { id: "empty1", label: "", bg: "#fff", textColor: "#fff", prefix: "" },
  { id: "empty2", label: "", bg: "#fff", textColor: "#fff", prefix: "" },
];

const PAYMENT_METHODS = [
  { id: "card", label: "카드결제", icon: <LuCreditCard className="w-7 h-7" />, bg: "#fff", accent: "#555" },
  { id: "appcard", label: "앱카드", icon: <LuSmartphone className="w-7 h-7" />, bg: "#fff", accent: "#555" },
  { id: "kakao", label: "카카오페이", icon: <span className="text-xs font-black text-black">pay</span>, bg: "#FEE500", accent: "#000" },
  { id: "voucher", label: "모바일상품권", icon: <LuTicket className="w-7 h-7" />, bg: "#fff", accent: "#555" },
  { id: "giftcard", label: "기프트카드", icon: <LuGift className="w-7 h-7" />, bg: "#fff", accent: "#555" },
  { id: "naver", label: "네이버페이", icon: <span className="text-xs font-black text-white">pay</span>, bg: "#03C75A", accent: "#fff" },
];

export const PaymentModal = ({ onClose, onSelect }: PaymentModalProps) => {
  const [selectedMethod, setSelectedMethod] = useState<string | null>(null);

  const handleSelect = (id: string) => {
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
          {/* 할인수단 */}
          <p className="font-bold text-gray-800 text-lg mb-4">할인수단</p>
          <div className="grid grid-cols-2 gap-4 mb-8">
            {DISCOUNT_METHODS.filter((m) => m.label).map((m) => (
              <button
                key={m.id}
                onClick={() => handleSelect(m.id)}
                className="rounded-2xl border border-gray-200 py-5 px-4 flex items-center gap-3 active:brightness-95 transition"
              >
                <span
                  className="text-sm font-black px-2 py-1 rounded shrink-0"
                  style={{ backgroundColor: m.bg, color: m.textColor }}
                >
                  {m.prefix}
                </span>
                <span className="text-sm font-semibold text-gray-700 text-left leading-tight">{m.label}</span>
              </button>
            ))}
          </div>

          {/* 결제수단 */}
          <p className="font-bold text-gray-800 text-lg mb-4">결제수단</p>
          <div className="grid grid-cols-2 gap-4">
            {PAYMENT_METHODS.map((m) => (
              <button
                key={m.id}
                onClick={() => handleSelect(m.id)}
                className="rounded-2xl border border-gray-200 py-5 px-4 flex items-center gap-4 active:brightness-95 transition"
              >
                <div
                  className="w-14 h-14 rounded-full flex items-center justify-center shrink-0"
                  style={{ backgroundColor: m.bg === "#fff" ? "#f3f4f6" : m.bg, color: m.accent }}
                >
                  {m.icon}
                </div>
                <span className="text-base font-semibold text-gray-700">{m.label}</span>
              </button>
            ))}
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
