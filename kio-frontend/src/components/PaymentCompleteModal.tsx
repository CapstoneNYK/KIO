import { LuX } from "react-icons/lu";
import { useNavigate } from "react-router-dom";
import { useCartStore } from "../store/cartStore";
import { useLearningStore } from "../store/learningStore";

interface PaymentCompleteModalProps {
  onClose: () => void;
}

export const PaymentCompleteModal = ({ onClose }: PaymentCompleteModalProps) => {
  const navigate = useNavigate();
  const clear = useCartStore((s) => s.clear);
  const setGuideScreen = useLearningStore((s) => s.setGuideScreen);
  const setHighlightPaymentMethod = useLearningStore((s) => s.setHighlightPaymentMethod);

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
      </div>
    </div>
  );
};
