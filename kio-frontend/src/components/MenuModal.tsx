import { useState } from "react";
import { LuX } from "react-icons/lu";
import type { MenuItem, MenuOption, Temperature } from "../types/menu";
import { OptionCounter } from "./OptionCounter";
import { useCartStore } from "../store/cartStore";

interface MenuModalProps {
  item: MenuItem;
  onClose: () => void;
  onOrder: (item: MenuItem, quantity: number, temperature: Temperature, options: MenuOption[], isPackaging: boolean) => void;
}

const COFFEE_OPTIONS: MenuOption[] = [
  { name: "텀블러 할인", count: 0 },
  { name: "샷추가", count: 0 },
  { name: "연하게", count: 0 },
  { name: "빨대 / 스틱 필요", count: 0 },
  { name: "캐리어 / 봉투 필요", count: 0 },
];

const NON_COFFEE_OPTIONS: MenuOption[] = [
  { name: "텀블러 할인", count: 0 },
  { name: "빨대 / 스틱 필요", count: 0 },
  { name: "캐리어 / 봉투 필요", count: 0 },
];

const COFFEE_CATEGORIES = ["커피", "디카페인"];

export const MenuModal = ({ item, onClose, onOrder }: MenuModalProps) => {
  const isCoffee = COFFEE_CATEGORIES.includes(item.category ?? "");
  const [quantity, setQuantity] = useState(1);
  const [temperature, setTemperature] = useState<Temperature>("HOT");
  const [options, setOptions] = useState<MenuOption[]>(
    (isCoffee ? COFFEE_OPTIONS : NON_COFFEE_OPTIONS).map((o) => ({ ...o }))
  );
  const addItem = useCartStore((s) => s.addItem);

  const updateOption = (index: number, delta: number) => {
    setOptions((prev) =>
      prev.map((opt, i) =>
        i === index ? { ...opt, count: Math.max(0, opt.count + delta) } : opt
      )
    );
  };

  const handleOrder = (isPackaging: boolean) => {
    addItem(item, quantity, temperature, options, isPackaging);
    onOrder(item, quantity, temperature, options, isPackaging);
    onClose();
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
        {/* 닫기 버튼 */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 text-gray-400 hover:text-gray-600 active:scale-90 transition z-10"
        >
          <LuX className="w-5 h-5" />
        </button>

        {/* 스크롤 가능한 본문 */}
        <div className="overflow-y-auto flex-1 px-8 pt-14 pb-3">
          {/* 아이템 정보 */}
          <div className="flex items-center gap-5 mb-8">
            <img
              src={item.img}
              alt={item.title}
              className="w-32 h-32 object-contain rounded-lg shrink-0"
            />
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-gray-900 text-2xl mb-3">{item.title}</p>
              <OptionCounter
                count={quantity}
                onDecrement={() => setQuantity((q) => Math.max(1, q - 1))}
                onIncrement={() => setQuantity((q) => q + 1)}
                min={1}
              />
            </div>
            <p className="text-orange-500 font-bold text-2xl shrink-0">
              {(item.price * quantity).toLocaleString()}원
            </p>
          </div>

          {/* 온도 선택 (커피류만) */}
          {isCoffee && <div className="flex gap-4 mb-14">
            <button
              onClick={() => setTemperature("HOT")}
              className={`flex-1 py-5 rounded-lg border-2 text-xl font-bold transition
                ${temperature === "HOT"
                  ? "border-red-400 text-red-500"
                  : "border-gray-200 text-gray-400"
                }`}
            >
              HOT
            </button>
            <button
              onClick={() => setTemperature("ICE")}
              className={`flex-1 py-5 rounded-lg border-2 text-xl font-bold transition
                ${temperature === "ICE"
                  ? "border-blue-400 text-blue-500"
                  : "border-gray-200 text-gray-400"
                }`}
            >
              ICE
            </button>
          </div>}

          {/* 선택옵션 */}
          <p className="font-bold text-gray-800 text-xl mb-4">선택옵션</p>
          <div className="flex flex-col gap-8 pl-4">
            {options.map((opt, idx) => (
              <div key={opt.name} className="flex items-center gap-4">
                <span className="flex-1 text-gray-700 text-xl">{opt.name}</span>
                <OptionCounter
                  count={opt.count}
                  onDecrement={() => updateOption(idx, -1)}
                  onIncrement={() => updateOption(idx, 1)}
                />
              </div>
            ))}
          </div>
        </div>

        {/* 주문 버튼 */}
        <div className="flex gap-4 px-8 py-6">
          <button
            onClick={() => handleOrder(false)}
            className="flex-1 text-white rounded-xl py-5 text-lg font-bold active:brightness-95 transition" style={{ backgroundColor: '#FFB900' }}
          >
            먹고가기
            <br />
            <span className="text-sm font-normal">(다회용컵)</span>
          </button>
          <button
            onClick={() => handleOrder(true)}
            className="flex-1 text-white rounded-xl py-5 text-lg font-bold active:brightness-95 transition" style={{ backgroundColor: '#FFB900' }}
          >
            포장하기
            <br />
            <span className="text-sm font-normal">(일회용컵)</span>
          </button>
        </div>
      </div>
    </div>
  );
};
