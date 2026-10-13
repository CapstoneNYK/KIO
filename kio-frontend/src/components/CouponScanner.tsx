import { useState } from "react";
import { useZxing } from "react-zxing";
import { LuX } from "react-icons/lu";
import { useMenuStore } from "../store/menuStore";
import { useCartStore } from "../store/cartStore";
import { useCouponStore } from "../store/couponStore";

interface CouponResult {
  code: string;
  type: "product" | "amount" | "discount";
  menu?: string;
  balance?: number;
  rate?: number;
  description: string;
}

interface CouponScannerProps {
  onClose: () => void;
  onGuideToVoucher?: () => void;
}

export const CouponScanner = ({ onClose, onGuideToVoucher }: CouponScannerProps) => {
  const [result, setResult] = useState<CouponResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scanned, setScanned] = useState(false);
  const addItem = useCartStore((s) => s.addItem);
  const addCoupon = useCouponStore((s) => s.addCoupon);
  const menus = useMenuStore((s) => s.menus);

  const { ref } = useZxing({
    onDecodeResult: async (res) => {
      if (scanned) return;
      setScanned(true);
      const code = res.rawValue;
      try {
        const resp = await fetch(
          `${import.meta.env.VITE_API_URL}/api/coupon/scan?code=${encodeURIComponent(code)}`
        );
        if (!resp.ok) {
          setError("유효하지 않은 쿠폰입니다.");
          return;
        }
        const data: CouponResult = await resp.json();
        setResult(data);
      } catch {
        setError("스캔 처리 중 오류가 발생했습니다.");
      }
    },
  });

  const handleUseProductCoupon = () => {
    if (!result || result.type !== "product" || !result.menu) return;
    const menuItem = menus.find((m) => m.title === result.menu);
    if (menuItem) addItem(menuItem, 1, "ICE", [], true, true);
    onClose();
  };

  const handleUseAmountCoupon = () => {
    if (!result || result.type !== "amount") return;
    addCoupon({ code: result.code, type: "amount", balance: result.balance!, description: result.description });
    onClose();
  };

  const handleUseDiscountCoupon = () => {
    if (!result || result.type !== "discount") return;
    addCoupon({ code: result.code, type: "discount", menu: result.menu!, rate: result.rate!, description: result.description });
    onClose();
  };

  const handleRetry = () => {
    setError(null);
    setScanned(false);
  };

  return (
    <div className="fixed inset-0 z-9997 bg-black/70 flex items-center justify-center">
      <div className="relative bg-white rounded-2xl w-[90%] max-w-md overflow-hidden shadow-2xl">
        {/* 헤더 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <p className="font-bold text-gray-800">쿠폰 스캔</p>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <LuX className="w-5 h-5" />
          </button>
        </div>

        {/* 카메라 뷰 */}
        {!result && !error && (
          <>
            <div
              className="relative mx-5 mt-5 mb-3 rounded-xl overflow-hidden bg-black"
              style={{ aspectRatio: "5 / 2" }}
            >
              <video ref={ref} className="w-full h-full object-cover" style={{ transform: "scaleX(-1)" }} autoPlay muted playsInline />
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="w-4/5 h-3/4 border-2 border-white/80 rounded-xl" />
              </div>
            </div>
            <p className="text-center text-sm text-gray-400 pb-5">바코드를 사각형 안에 맞춰주세요</p>
          </>
        )}

        {/* 음료 상품권 결과 */}
        {result?.type === "product" && (
          <div className="px-5 py-6 flex flex-col items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center text-3xl">🎉</div>
            <div className="text-center">
              <p className="font-bold text-gray-800 text-base">{result.description}</p>
              <p className="text-sm text-gray-500 mt-1">{result.menu}을(를) 무료로 받을 수 있어요!</p>
            </div>
            <div className="flex gap-2 w-full">
              <button
                onClick={onClose}
                className="flex-1 py-3 rounded-xl font-semibold text-gray-600 border border-gray-200 text-sm"
              >
                취소
              </button>
              <button
                onClick={handleUseProductCoupon}
                className="flex-1 py-3 rounded-xl font-bold text-white text-sm"
                style={{ backgroundColor: "#FFB900" }}
              >
                장바구니에 담기
              </button>
            </div>
          </div>
        )}

        {/* 멤버십 % 할인 결과 */}
        {result?.type === "discount" && (
          <div className="px-5 py-6 flex flex-col gap-4">
            <div>
              <p className="text-xs text-gray-400 mb-1">할인 종류</p>
              <p className="font-bold text-gray-800 text-base">{result.description}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400 mb-1">할인율</p>
              <p className="font-bold text-orange-500 text-base">{result.menu} {Math.round((result.rate ?? 0) * 100)}% 할인</p>
            </div>
            <p className="text-xs text-gray-400">장바구니에 {result.menu}가 있을 때만 할인이 적용됩니다</p>
            <div className="flex gap-2 w-full">
              <button
                onClick={onClose}
                className="flex-1 py-3 rounded-xl font-semibold text-gray-600 border border-gray-200 text-sm"
              >
                취소
              </button>
              <button
                onClick={handleUseDiscountCoupon}
                className="flex-1 py-3 rounded-xl font-bold text-white text-sm"
                style={{ backgroundColor: "#FFB900" }}
              >
                할인 적용
              </button>
            </div>
          </div>
        )}

        {/* 금액 상품권 결과 */}
        {result?.type === "amount" && (
          <div className="px-5 py-6 flex flex-col gap-4">
            <div>
              <p className="text-xs text-gray-400 mb-1">쿠폰 종류</p>
              <p className="font-bold text-gray-800 text-base">{result.description}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400 mb-1">잔액</p>
              <p className="font-bold text-orange-500 text-base">{result.balance?.toLocaleString()}원</p>
            </div>
            {onGuideToVoucher ? (
              <>
                <p className="text-xs text-gray-500 text-center">
                  결제 수단에서 모바일 상품권을 선택하면 사용할 수 있어요
                </p>
                <button
                  onClick={onGuideToVoucher}
                  className="w-full py-3 rounded-xl font-bold text-white text-sm"
                  style={{ backgroundColor: "#FFB900" }}
                >
                  모바일 상품권으로 결제하기
                </button>
              </>
            ) : (
              <div className="flex gap-2 w-full">
                <button
                  onClick={onClose}
                  className="flex-1 py-3 rounded-xl font-semibold text-gray-600 border border-gray-200 text-sm"
                >
                  닫기
                </button>
                <button
                  onClick={handleUseAmountCoupon}
                  className="flex-1 py-3 rounded-xl font-bold text-white text-sm"
                  style={{ backgroundColor: "#FFB900" }}
                >
                  결제에 사용
                </button>
              </div>
            )}
          </div>
        )}

        {/* 오류 */}
        {error && (
          <div className="px-5 py-6 flex flex-col items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center text-3xl">❌</div>
            <p className="font-bold text-gray-800 text-base">{error}</p>
            <button
              onClick={handleRetry}
              className="w-full py-3 rounded-xl font-bold text-white text-sm"
              style={{ backgroundColor: "#FFB900" }}
            >
              다시 시도
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
