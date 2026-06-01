import { useState, useEffect } from "react";
import { LuX } from "react-icons/lu";
import { useCartStore } from "../store/cartStore";
import { useLearningStore } from "../store/learningStore";
import { imgCardPayment, imgAppCard, imgBarcode, iconKakao, iconNaver } from "../assets";
import { PaymentCompleteModal } from "./PaymentCompleteModal";

interface PaymentDetailModalProps {
  method: string;
  onClose: () => void;
  onCancel: () => void;
  onComplete: () => void;
}

// 숫자패드 컴포넌트
const NumPad = ({ onPress }: { onPress: (val: string) => void }) => {
  const keys = ["1","2","3","4","5","6","7","8","9","0","00","000"];
  return (
    <div className="grid grid-cols-3 gap-2">
      <button
        onClick={() => onPress("clear")}
        className="col-span-2 py-3 rounded-lg bg-gray-100 text-gray-700 font-semibold text-sm active:bg-gray-200"
      >
        clear
      </button>
      <button
        onClick={() => onPress("back")}
        className="py-3 rounded-lg bg-gray-100 text-gray-700 font-semibold text-sm active:bg-gray-200"
      >
        ←
      </button>
      {keys.map((k) => (
        <button
          key={k}
          onClick={() => onPress(k)}
          className="py-3 rounded-lg bg-gray-100 text-gray-700 font-semibold text-sm active:bg-gray-200"
        >
          {k}
        </button>
      ))}
    </div>
  );
};

// 카드결제 / 앱카드 공통
const CardPayment = ({
  description,
  image,
  onCancel,
  onApprove,
}: {
  description: string;
  image: string;
  onCancel: () => void;
  onApprove: () => void;
}) => {
  const totalPrice = useCartStore((s) =>
    s.items.reduce((sum, i) => sum + i.item.price * i.quantity, 0)
  );
  const [cardNumber, setCardNumber] = useState("");

  return (
    <>
      <div className="flex flex-col mb-5 rounded-xl overflow-hidden border border-gray-100">
        <div className="flex justify-between items-center py-3 px-4 bg-gray-50">
          <span className="text-gray-600">총 결제금액</span>
          <span className="font-bold text-orange-500">{totalPrice.toLocaleString()}원</span>
        </div>
        <div className="flex justify-between items-center py-3 px-4 bg-white">
          <span className="text-gray-600">할부개월</span>
          <span className="text-gray-700">일시불</span>
        </div>
        <div className="py-3 px-4 bg-gray-50">
          <input
            type="text"
            value={cardNumber}
            onChange={(e) => setCardNumber(e.target.value)}
            placeholder="카드번호"
            className="w-full text-gray-700 outline-none placeholder-gray-400 text-sm bg-transparent"
          />
        </div>
      </div>

      <div className="flex gap-3 mb-5">
        <button
          onClick={onCancel}
          className="flex-1 py-3 rounded-xl font-bold text-white active:brightness-95"
          style={{ backgroundColor: "#555" }}
        >
          취소
        </button>
        <button
          onClick={onApprove}
          className="flex-1 py-3 rounded-xl font-bold text-white active:brightness-95"
          style={{ backgroundColor: "#FFB900" }}
        >
          승인 요청
        </button>
      </div>

      <p className="text-center text-sm text-gray-500 mb-4 leading-relaxed">{description}</p>

      <img src={image} alt="리더기" className="w-full rounded-xl object-contain" />
    </>
  );
};

// 모바일 상품권
const VoucherPayment = ({ onCancel }: { onCancel: () => void }) => {
  const totalPrice = useCartStore((s) =>
    s.items.reduce((sum, i) => sum + i.item.price * i.quantity, 0)
  );
  const [coupon, setCoupon] = useState("");

  const handleNumPress = (val: string) => {
    if (val === "clear") { setCoupon(""); return; }
    if (val === "back") { setCoupon((p) => p.slice(0, -1)); return; }
    setCoupon((p) => p + val);
  };

  return (
    <>
      <div className="flex gap-4 mb-5">
        {/* 왼쪽 입력 */}
        <div className="flex-1 flex flex-col gap-3">
          <div className="py-3 border-b border-gray-100">
            <input
              type="text"
              value={coupon}
              readOnly
              placeholder="쿠폰번호"
              className="w-full text-gray-700 outline-none placeholder-gray-400 text-sm"
            />
          </div>
          <div className="flex justify-between items-center py-3 border-b border-gray-100">
            <span className="text-gray-600 text-sm">받음금액</span>
            <span className="font-bold text-orange-500 text-sm">{totalPrice.toLocaleString()}원</span>
          </div>
          <div className="flex justify-between items-center py-3 border-b border-gray-100">
            <span className="text-gray-600 text-sm">결제금액</span>
            <span className="text-gray-700 text-sm"></span>
          </div>
        </div>
        {/* 오른쪽 숫자패드 */}
        <div className="w-40 shrink-0">
          <NumPad onPress={handleNumPress} />
        </div>
      </div>

      <div className="flex gap-3 mb-4">
        <button
          onClick={onCancel}
          className="flex-1 py-3 rounded-xl font-bold text-white active:brightness-95"
          style={{ backgroundColor: "#555" }}
        >
          조회
        </button>
        <button
          className="flex-1 py-3 rounded-xl font-bold text-white active:brightness-95"
          style={{ backgroundColor: "#FFB900" }}
        >
          사용
        </button>
      </div>

      <p className="text-center text-sm text-gray-500 mb-4 leading-relaxed">
        스캔이 되지 않을 경우 위에 키패드로 번호를 직접 입력해주세요.
      </p>

      <img src={imgBarcode} alt="바코드 리더기" className="w-full rounded-xl object-contain" />
    </>
  );
};

// 제휴멤버십 (CJ ONE 등)
const MembershipPayment = ({
  affiliateName,
  onCancel,
}: {
  affiliateName: string;
  onCancel: () => void;
}) => {
  const [phoneNumber, setPhoneNumber] = useState("");
  const [customerName, setCustomerName] = useState("");

  const handleNumPress = (val: string) => {
    if (val === "clear") { setPhoneNumber(""); return; }
    if (val === "back") { setPhoneNumber((p) => p.slice(0, -1)); return; }
    setPhoneNumber((p) => p + val);
  };

  return (
    <>
      <div className="flex gap-4 mb-5">
        {/* 왼쪽 입력 */}
        <div className="flex-1 flex flex-col rounded-xl overflow-hidden border border-gray-100">
          <div className="flex justify-between items-center py-3 px-3 bg-gray-50">
            <span className="text-gray-600 text-sm">제휴명</span>
            <span className="font-semibold text-gray-700 text-sm">{affiliateName}</span>
          </div>
          <div className="py-3 px-3 bg-white">
            <input
              type="text"
              value={phoneNumber}
              readOnly
              placeholder="카드/휴대폰번호"
              className="w-full text-gray-700 outline-none placeholder-gray-400 text-sm bg-transparent"
            />
          </div>
          <div className="py-3 px-3 bg-gray-50">
            <input
              type="text"
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              placeholder="고객명"
              className="w-full text-gray-700 outline-none placeholder-gray-400 text-sm bg-transparent"
            />
          </div>
        </div>
        {/* 오른쪽 숫자패드 */}
        <div className="w-40 shrink-0">
          <NumPad onPress={handleNumPress} />
        </div>
      </div>

      <div className="flex gap-3 mb-4">
        <button
          onClick={onCancel}
          className="flex-1 py-3 rounded-xl font-bold text-white active:brightness-95"
          style={{ backgroundColor: "#555" }}
        >
          조회
        </button>
        <button
          className="flex-1 py-3 rounded-xl font-bold text-white active:brightness-95"
          style={{ backgroundColor: "#FFB900" }}
        >
          적립
        </button>
      </div>

      <p className="text-center text-sm text-red-400 leading-relaxed">
        스캔이 되지 않을 경우 위에 키패드로 카드/휴대폰번호 직접 입력 후 조회/적립을 눌러주세요.
      </p>

      <img src={imgBarcode} alt="바코드 리더기" className="w-full rounded-xl object-contain mt-4" />
    </>
  );
};

// 카카오페이 / 네이버페이 공통 바코드 결제
const AppBarcodePayment = ({
  brand,
  accentColor,
  textColor,
  logoIcon,
  onApprove,
}: {
  brand: string;
  accentColor: string;
  textColor: string;
  logoIcon: string;
  onApprove: () => void;
}) => {
  const totalPrice = useCartStore((s) =>
    s.items.reduce((sum, i) => sum + i.item.price * i.quantity, 0)
  );
  const [remaining, setRemaining] = useState(5);

  useEffect(() => {
    if (remaining <= 0) { onApprove(); return; }
    const timer = setTimeout(() => setRemaining((r) => r - 1), 1000);
    return () => clearTimeout(timer);
  }, [remaining]);

  return (
    <>
      {/* 브랜드 헤더 */}
      <div
        className="flex items-center gap-3 mb-5 px-4 py-3 rounded-2xl"
        style={{ backgroundColor: accentColor }}
      >
        <img src={logoIcon} alt={brand} className="w-8 h-8 object-contain rounded-lg" />
        <span className="font-bold text-lg" style={{ color: textColor }}>{brand}</span>
      </div>

      {/* 결제 금액 */}
      <div className="flex justify-between items-center py-3 border-b border-gray-100 mb-5">
        <span className="text-gray-600">총 결제금액</span>
        <span className="font-bold text-orange-500">{totalPrice.toLocaleString()}원</span>
      </div>

      <p className="text-center text-sm text-gray-500 mb-2 leading-relaxed">
        {brand} 앱에서 바코드를 화면에 표시하고{"\n"}스캐너에 가까이 대주세요.
      </p>
      <p className="text-center text-xs text-gray-400 mb-4">{remaining}초 후 자동 처리됩니다</p>

      <img src={imgBarcode} alt="바코드 리더기" className="w-full rounded-xl object-contain" />
    </>
  );
};

// 제목 매핑
const TITLES: Record<string, string> = {
  card: "카드결제",
  appcard: "앱카드결제",
  kakao: "카카오페이",
  naver: "네이버페이",
  voucher: "모바일 상품권",
  giftcard: "기프트카드",
  cjone: "제휴멤버십",
  kt: "제휴멤버십",
  tmembership: "제휴멤버십",
  uzu: "제휴멤버십",
};

const AFFILIATE_NAMES: Record<string, string> = {
  cjone: "CJ ONE",
  kt: "KT VIP",
  tmembership: "T 멤버십",
  uzu: "T우주",
};

export const PaymentDetailModal = ({ method, onClose, onCancel }: PaymentDetailModalProps) => {
  const title = TITLES[method] ?? "결제";
  const [isProcessing, setIsProcessing] = useState(false);
  const [showComplete, setShowComplete] = useState(false);
  const learningScreen = useLearningStore((s) => s.learningScreen);

  const guideScreen = useLearningStore((s) => s.guideScreen);

  useEffect(() => {
    setShowComplete(learningScreen === "payment_complete");
  }, [learningScreen]);

  useEffect(() => {
    if (guideScreen === "payment_complete") setShowComplete(true);
  }, [guideScreen]);

  const handleApprove = () => {
    setIsProcessing(true);
    setTimeout(() => {
      setIsProcessing(false);
      setShowComplete(true);
    }, 3000);
  };

  const renderContent = () => {
    if (method === "card") {
      return (
        <CardPayment
          description={"카드를 카드리더기에 넣어주세요.\n결제가 완료될 때까지 카드를 빼지 마세요."}
          image={imgCardPayment}
          onCancel={onCancel}
          onApprove={handleApprove}
        />
      );
    }
    if (method === "appcard") {
      return (
        <CardPayment
          description={"휴대폰을 카드리더기에 가까이 대주세요.\n결제가 완료될 때까지 휴대폰을 떼지 마세요."}
          image={imgAppCard}
          onCancel={onCancel}
          onApprove={handleApprove}
        />
      );
    }
    if (method === "kakao") {
      return (
        <AppBarcodePayment
          brand="카카오페이"
          accentColor="#FEE500"
          textColor="#3A1D1D"
          logoIcon={iconKakao}
          onApprove={handleApprove}
        />
      );
    }
    if (method === "naver") {
      return (
        <AppBarcodePayment
          brand="네이버페이"
          accentColor="#03C75A"
          textColor="#ffffff"
          logoIcon={iconNaver}
          onApprove={handleApprove}
        />
      );
    }
    if (method === "voucher" || method === "giftcard") {
      return <VoucherPayment onCancel={onCancel} />;
    }
    if (["cjone","kt","tmembership","uzu"].includes(method)) {
      return (
        <MembershipPayment
          affiliateName={AFFILIATE_NAMES[method] ?? ""}
          onCancel={onCancel}
        />
      );
    }
    return <p className="text-gray-500 text-sm">준비 중입니다.</p>;
  };

  return (
    <div
      className="fixed inset-0 z-60 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="relative bg-white rounded-2xl w-[80%] h-[88vh] flex flex-col overflow-hidden shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-center py-4 px-6 shrink-0">
          <h2 className="text-lg font-bold text-gray-900">{title}</h2>
          <button
            onClick={onClose}
            className="absolute right-4 text-gray-400 hover:text-gray-600 active:scale-90 transition"
          >
            <LuX className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 pb-6">
          {renderContent()}
        </div>

        {/* 결제 처리 중 오버레이 */}
        {isProcessing && (
          <div className="absolute inset-0 bg-white/90 flex flex-col items-center justify-center gap-5 z-10">
            <div className="w-14 h-14 border-4 border-gray-200 rounded-full animate-spin" style={{ borderTopColor: "#FFB900" }} />
            <p className="text-gray-700 font-semibold text-lg">결제 처리 중입니다...</p>
            <p className="text-gray-400 text-sm">카드를 빼지 마세요</p>
          </div>
        )}
      </div>

      {showComplete && (
        <PaymentCompleteModal onClose={() => setShowComplete(false)} />
      )}
    </div>
  );
};
