import { useEffect, useRef, useState } from "react";
import { PiShoppingCartSimple } from "react-icons/pi";
import { LuX, LuChevronLeft, LuChevronRight } from "react-icons/lu";
import { useCartStore } from "../store/cartStore";
import { useCouponStore, calcDiscount } from "../store/couponStore";
import { useLearningStore } from "../store/learningStore";
import { OptionCounter } from "./OptionCounter";
import { OrderConfirmModal } from "./OrderConfirmModal";

const CONFIRM_SCREENS = ["order_confirm", "payment", "payment_card", "payment_complete"];

export const CartBar = () => {
  const { items, removeItem, updateQuantity, clear } = useCartStore();
  const coupons = useCouponStore((s) => s.coupons);
  const clearCoupons = useCouponStore((s) => s.clearCoupons);
  const learningScreen = useLearningStore((s) => s.learningScreen);

  useEffect(() => {
    if (items.length === 0) clearCoupons();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items.length]);
  const guideScreen = useLearningStore((s) => s.guideScreen);
  const setGuideScreen = useLearningStore((s) => s.setGuideScreen);
  const orderOverlayOpen = useLearningStore((s) => s.orderOverlayOpen);
  const setOrderOverlayOpen = useLearningStore((s) => s.setOrderOverlayOpen);

  // 담은 메뉴 목록 가로 슬라이드: 마우스 드래그 / 휠 / 좌우 버튼 (터치는 기본 스크롤)
  // (전역 CSS가 스크롤바를 숨기고 있어서, 마우스로는 따로 지원하지 않으면 넘길 방법이 없다)
  const listRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef({ down: false, startX: 0, startScroll: 0, moved: false });
  const [canLeft, setCanLeft] = useState(false);
  const [canRight, setCanRight] = useState(false);

  const updateArrows = () => {
    const el = listRef.current;
    if (!el) return;
    setCanLeft(el.scrollLeft > 4);
    setCanRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  };
  useEffect(() => {
    updateArrows();
    window.addEventListener("resize", updateArrows);
    return () => window.removeEventListener("resize", updateArrows);
  }, [items.length]);

  const slide = (dir: -1 | 1) =>
    listRef.current?.scrollBy({ left: dir * 240, behavior: "smooth" });

  const showConfirm = orderOverlayOpen
    || CONFIRM_SCREENS.includes(learningScreen ?? "")
    || CONFIRM_SCREENS.includes(guideScreen ?? "");

  if (items.length === 0) return null;

  const totalQty = items.reduce((sum, i) => sum + i.quantity, 0);
  const totalPrice = items.reduce((sum, i) => sum + i.item.price * i.quantity, 0);
  const freeDiscount = items.reduce((sum, i) => i.isFree ? sum + i.item.price : sum, 0);
  const couponDiscount = calcDiscount(coupons, totalPrice - freeDiscount, items);
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
      <div className="relative">
      {canLeft && (
        <button
          onClick={() => slide(-1)}
          className="absolute left-0 top-1/2 z-10 -translate-y-1/2 flex h-8 w-8 items-center justify-center rounded-full bg-white shadow-md border border-gray-200 text-gray-600 active:bg-gray-100"
        >
          <LuChevronLeft className="w-5 h-5" />
        </button>
      )}
      {canRight && (
        <button
          onClick={() => slide(1)}
          className="absolute right-0 top-1/2 z-10 -translate-y-1/2 flex h-8 w-8 items-center justify-center rounded-full bg-white shadow-md border border-gray-200 text-gray-600 active:bg-gray-100"
        >
          <LuChevronRight className="w-5 h-5" />
        </button>
      )}
      <div
        ref={listRef}
        onScroll={updateArrows}
        onWheel={(e) => {
          if (listRef.current && Math.abs(e.deltaY) > Math.abs(e.deltaX)) listRef.current.scrollLeft += e.deltaY;
        }}
        onMouseDown={(e) => {
          if (!listRef.current) return;
          dragRef.current = { down: true, startX: e.clientX, startScroll: listRef.current.scrollLeft, moved: false };
        }}
        onMouseMove={(e) => {
          const d = dragRef.current;
          if (!d.down || !listRef.current) return;
          const dx = e.clientX - d.startX;
          if (Math.abs(dx) > 5) d.moved = true;
          listRef.current.scrollLeft = d.startScroll - dx;
        }}
        onMouseUp={() => { dragRef.current.down = false; }}
        onMouseLeave={() => { dragRef.current.down = false; }}
        // 드래그로 넘긴 직후에 버튼(수량·삭제)이 눌리지 않게 막는다
        onClickCapture={(e) => {
          if (dragRef.current.moved) {
            e.stopPropagation();
            e.preventDefault();
            dragRef.current.moved = false;
          }
        }}
        className="flex gap-2 overflow-x-auto pb-2 mb-3 select-none cursor-grab active:cursor-grabbing"
      >
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
        onClick={() => setOrderOverlayOpen(true)}
        className="w-full py-4 rounded-xl text-white font-bold text-base active:brightness-95 transition"
        style={{ backgroundColor: "#FFB900" }}
      >
        주문하기
      </button>

      {showConfirm && (
        <OrderConfirmModal
          onClose={() => { setOrderOverlayOpen(false); setGuideScreen(null); }}
          onCancelAll={() => { clear(); setOrderOverlayOpen(false); setGuideScreen(null); }}
          onNext={() => { setOrderOverlayOpen(false); setGuideScreen(null); }}
        />
      )}
    </div>
  );
};
