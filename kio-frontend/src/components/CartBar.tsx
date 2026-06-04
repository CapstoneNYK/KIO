import { useState } from "react";
import { PiShoppingCartSimple } from "react-icons/pi";
import { LuX } from "react-icons/lu";
import { useCartStore } from "../store/cartStore";
import { useCouponStore, calcDiscount } from "../store/couponStore";
import { OptionCounter } from "./OptionCounter";
import { OrderConfirmModal } from "./OrderConfirmModal";

export const CartBar = () => {
  const { items, removeItem, updateQuantity, clear } = useCartStore();
  const coupons = useCouponStore((s) => s.coupons);
  const [showConfirm, setShowConfirm] = useState(false);

  if (items.length === 0) return null;

  const totalQty = items.reduce((sum, i) => sum + i.quantity, 0);
  const totalPrice = items.reduce((sum, i) => sum + i.item.price * i.quantity, 0);
  const freeDiscount = items.reduce((sum, i) => i.isFree ? sum + i.item.price : sum, 0);
  const couponDiscount = calcDiscount(coupons, totalPrice - freeDiscount);
  const totalDiscount = freeDiscount + couponDiscount;
  const finalPrice = totalPrice - totalDiscount;

  return (
    <div className="border-t border-gray-200 bg-white px-4 pt-3 pb-4 shrink-0">
      {/* 헤더 */}
      <div className="flex items-center gap-1 mb-2">
        <PiShoppingCartSimple className="w-5 h-5" style={{ color: "#E17100" }} />
        <span className="text-sm font-semibold text-gray-700">
          담은 메뉴 ({totalQty}개)
        </span>
      </div>

      {/* 아이템 목록 - 가로 스크롤 */}
      <div className="flex gap-2 overflow-x-auto pb-2 mb-3">
        {items.map((cartItem) => (
          <div
            key={cartItem.cartId}
            className="relative shrink-0 flex items-center gap-2 rounded-xl p-2 pr-6"
            style={{ backgroundColor: "#FFFBEB", border: "1.5px solid #FEE685" }}
          >
            {/* X 버튼 - 카드 안 우상단 */}
            <button
              onClick={() => removeItem(cartItem.cartId)}
              className="absolute top-1.5 right-1.5 text-gray-400 active:text-gray-600"
            >
              <LuX className="w-3 h-3" />
            </button>

            <img
              src={cartItem.item.img}
              alt={cartItem.item.title}
              className="w-12 h-12 object-contain shrink-0"
            />
            <div>
              <p className="text-sm font-semibold text-gray-900 whitespace-nowrap">
                {cartItem.item.title}
              </p>
              <p className="text-sm font-bold text-orange-500 mb-1">
                {(cartItem.item.price * cartItem.quantity).toLocaleString()}원
              </p>
              <OptionCounter
                count={cartItem.quantity}
                min={1}
                onDecrement={() => updateQuantity(cartItem.cartId, cartItem.quantity - 1)}
                onIncrement={() => updateQuantity(cartItem.cartId, cartItem.quantity + 1)}
              />
            </div>
          </div>
        ))}
      </div>

      {/* 구분선 */}
      <div className="mb-3" style={{ borderTop: "1.5px solid #FEF3C6" }} />

      {/* 합계 + 주문 버튼 */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-gray-600">총 {totalQty}개</span>
        <div className="flex flex-col items-end gap-0.5">
          {totalDiscount > 0 && (
            <p className="text-xs text-green-600 font-semibold">
              쿠폰 할인 -{totalDiscount.toLocaleString()}원
            </p>
          )}
          <div className="flex items-center gap-2">
            <p className="text-xs text-gray-400">결제 금액</p>
            <p className="text-base font-bold text-orange-500">
              {finalPrice.toLocaleString()}원
            </p>
          </div>
        </div>
      </div>

      <button
        onClick={() => setShowConfirm(true)}
        className="w-full py-4 rounded-xl text-white font-bold text-base active:brightness-95 transition"
        style={{ backgroundColor: "#FFB900" }}
      >
        주문하기
      </button>

      {showConfirm && (
        <OrderConfirmModal
          onClose={() => setShowConfirm(false)}
          onCancelAll={() => { clear(); setShowConfirm(false); }}
          onNext={() => setShowConfirm(false)}
        />
      )}
    </div>
  );
};
