import { useChatPrefs } from "../store/chatPrefsStore";
import { LuX } from "react-icons/lu";
import { useNavigate } from "react-router-dom";
import { useCartStore } from "../store/cartStore";
import { useLearningStore } from "../store/learningStore";

interface PaymentCompleteModalProps {
  onClose: () => void;
  /** (사용 안 함) 결제 후 취소는 직원이 관리자 화면에서만 한다. 호출부 호환용으로만 남겨 둠. */
  requestId?: string | null;
}

export const PaymentCompleteModal = ({ onClose }: PaymentCompleteModalProps) => {
  const navigate = useNavigate();
  const clear = useCartStore((s) => s.clear);
  const setGuideScreen = useLearningStore((s) => s.setGuideScreen);
  const setHighlightPaymentMethod = useLearningStore((s) => s.setHighlightPaymentMethod);

  const finish = () => {
    clear();
    useChatPrefs.getState().resetChat();
    setGuideScreen(null);
    setHighlightPaymentMethod(null);
    navigate("/");
  };

  return (
    <div className="fixed inset-0 z-70 flex items-center justify-center" style={{ backgroundColor: "#d4d4d4" }}>
      <div className="relative bg-white rounded-lg w-[65%] flex flex-col overflow-hidden px-12 py-14">
        <button
          onClick={() => {
            finish();
            onClose();
          }}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition"
        >
          <LuX className="w-5 h-5" />
        </button>

        <p className="text-center text-gray-900 font-semibold text-lg mb-10 mt-2">
          결제가 완료되었습니다. 영수증을 출력하시겠습니까?
        </p>

        <div className="flex gap-4">
          <button
            onClick={finish}
            className="flex-1 py-4 rounded-md font-bold text-white text-base active:brightness-95 transition"
            style={{ backgroundColor: "#888" }}
          >
            미출력
          </button>
          <button
            onClick={finish}
            className="flex-1 py-4 rounded-md font-bold text-white text-base active:brightness-95 transition"
            style={{ backgroundColor: "#1C1917" }}
          >
            출력
          </button>
        </div>
      </div>
    </div>
  );
};
