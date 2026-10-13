import { useState } from "react";
import { LuX } from "react-icons/lu";
import { useNavigate } from "react-router-dom";
import { useCartStore } from "../store/cartStore";
import { useLearningStore } from "../store/learningStore";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

interface PaymentCompleteModalProps {
  onClose: () => void;
  /** 방금 저장된 주문의 멱등키. 없으면(학습 모드 등) 주문 취소 버튼을 보여주지 않는다. */
  requestId?: string | null;
}

export const PaymentCompleteModal = ({ onClose, requestId }: PaymentCompleteModalProps) => {
  const navigate = useNavigate();
  const clear = useCartStore((s) => s.clear);
  const setGuideScreen = useLearningStore((s) => s.setGuideScreen);
  const setHighlightPaymentMethod = useLearningStore((s) => s.setHighlightPaymentMethod);

  const [cancelling, setCancelling] = useState(false);
  const [cancelMessage, setCancelMessage] = useState("");
  const [cancelled, setCancelled] = useState(false);

  // 결제 후 일정 시간(서버 설정, 기본 3분) 이내에만 서버가 취소를 허용한다. 그 외에는 사유를 그대로 안내한다.
  const cancelOrder = async () => {
    if (!requestId) return;
    setCancelling(true);
    setCancelMessage("");
    try {
      const res = await fetch(`${API_URL}/api/orders/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_id: requestId }),
      });
      if (res.ok) {
        setCancelled(true);
      } else {
        const data = await res.json().catch(() => null);
        setCancelMessage(typeof data?.detail === "string" ? data.detail : "취소하지 못했어요. 카운터에 문의해 주세요.");
      }
    } catch {
      setCancelMessage("네트워크 문제로 취소하지 못했어요. 카운터에 문의해 주세요.");
    } finally {
      setCancelling(false);
    }
  };

  const finish = () => {
    clear();
    setGuideScreen(null);
    setHighlightPaymentMethod(null);
    navigate("/");
  };

  return (
    <div className="fixed inset-0 z-70 flex items-center justify-center" style={{ backgroundColor: "#d4d4d4" }}>
      <div className="relative bg-white rounded-2xl w-[65%] flex flex-col overflow-hidden shadow-xl px-12 py-14">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition"
        >
          <LuX className="w-5 h-5" />
        </button>

        {cancelled ? (
          <>
            <p className="text-center text-gray-900 font-semibold text-lg mb-10 mt-2">
              주문이 취소되었습니다. 결제 금액은 환불 처리됩니다.
            </p>
            <button
              onClick={finish}
              className="w-full py-4 rounded-xl font-bold text-white text-base active:brightness-95 transition"
              style={{ backgroundColor: "#FFB900" }}
            >
              처음으로
            </button>
          </>
        ) : (
          <>
            <p className="text-center text-gray-900 font-semibold text-lg mb-10 mt-2">
              결제가 완료되었습니다. 영수증을 출력하시겠습니까?
            </p>

            <div className="flex gap-4">
              <button
                onClick={finish}
                className="flex-1 py-4 rounded-xl font-bold text-white text-base active:brightness-95 transition"
                style={{ backgroundColor: "#888" }}
              >
                미출력
              </button>
              <button
                onClick={finish}
                className="flex-1 py-4 rounded-xl font-bold text-white text-base active:brightness-95 transition"
                style={{ backgroundColor: "#FFB900" }}
              >
                출력
              </button>
            </div>

            {requestId && (
              <div className="mt-6 text-center">
                <button
                  onClick={cancelOrder}
                  disabled={cancelling}
                  className="text-sm text-gray-500 underline underline-offset-4 disabled:opacity-50"
                >
                  {cancelling ? "취소 중..." : "주문 취소"}
                </button>
                {cancelMessage && <p className="mt-2 text-sm text-red-500">{cancelMessage}</p>}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
