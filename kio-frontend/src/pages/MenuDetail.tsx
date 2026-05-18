import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { OptionCounter } from "../components/OptionCounter";
import { TopBar } from "../components/TopBar";
import type { MenuItem, MenuOption, Temperature } from "../types/menu";

const DEFAULT_OPTIONS: MenuOption[] = [
  { name: "텀블러 할인", count: 0 },
  { name: "샷추가", count: 0 },
  { name: "연하게", count: 0 },
  { name: "빨대 / 스틱 필요", count: 0 },
  { name: "캐리어 / 봉투 필요", count: 0 },
];

export const MenuDetail = () => {
  const navigate = useNavigate();
  const { state } = useLocation() as { state: { item: MenuItem } };
  const item = state?.item;

  const [quantity, setQuantity] = useState(1);
  const [temperature, setTemperature] = useState<Temperature>("HOT");
  const [options, setOptions] = useState<MenuOption[]>(
    DEFAULT_OPTIONS.map((o) => ({ ...o }))
  );

  const updateOption = (index: number, delta: number) => {
    setOptions((prev) =>
      prev.map((opt, i) =>
        i === index ? { ...opt, count: Math.max(0, opt.count + delta) } : opt
      )
    );
  };

  if (!item) {
    navigate("/home");
    return null;
  }

  return (
    <div className="flex flex-col h-screen bg-[#FFEFCE]">
      <TopBar />

      <div className="flex-1 bg-white mx-4 mt-3 rounded-t-2xl shadow-sm flex flex-col min-h-0">
        {/* 페이지 타이틀 */}
        <p className="text-center text-orange-400 font-semibold pt-4 pb-2 shrink-0">결제수단 선택</p>

        {/* 스크롤 영역 */}
        <div className="flex-1 overflow-y-auto px-5">
          {/* 아이템 정보 */}
          <div className="flex items-center gap-4 mb-5">
            <img
              src={item.img}
              alt={item.title}
              className="w-20 h-20 object-contain rounded-xl shrink-0"
            />
            <div className="flex-1">
              <p className="font-semibold text-gray-900 text-lg">{item.title}</p>
              <OptionCounter
                count={quantity}
                onDecrement={() => setQuantity((q) => Math.max(1, q - 1))}
                onIncrement={() => setQuantity((q) => q + 1)}
                min={1}
              />
            </div>
            <p className="text-orange-500 font-bold text-lg shrink-0">
              {(item.price * quantity).toLocaleString()}원
            </p>
          </div>

          {/* 온도 선택 */}
          <div className="flex gap-3 mb-6">
            <button
              onClick={() => setTemperature("HOT")}
              className={`flex-1 py-3 rounded-xl border-2 font-bold transition
                ${temperature === "HOT"
                  ? "border-red-400 text-red-500"
                  : "border-gray-200 text-red-300"
                }`}
            >
              HOT
            </button>
            <button
              onClick={() => setTemperature("ICE")}
              className={`flex-1 py-3 rounded-xl border-2 font-bold transition
                ${temperature === "ICE"
                  ? "border-blue-400 text-blue-500"
                  : "border-gray-200 text-blue-300"
                }`}
            >
              ICE
            </button>
          </div>

          {/* 선택옵션 */}
          <p className="text-sm font-semibold text-gray-700 mb-3">선택옵션</p>
          <div className="flex flex-col gap-4 pb-4">
            {options.map((opt, idx) => (
              <div key={opt.name} className="flex items-center justify-between">
                <span className="text-sm text-gray-700">{opt.name}</span>
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
        <div className="flex gap-3 px-5 py-4 shrink-0">
          <button
            onClick={() => navigate(-1)}
            className="flex-1 bg-yellow-400 text-white rounded-2xl py-4 font-bold active:brightness-95 transition"
          >
            먹고가기
            <br />
            <span className="text-xs font-normal">(다회용컵)</span>
          </button>
          <button
            onClick={() => navigate(-1)}
            className="flex-1 bg-yellow-400 text-white rounded-2xl py-4 font-bold active:brightness-95 transition"
          >
            포장하기
            <br />
            <span className="text-xs font-normal">(일회용컵)</span>
          </button>
        </div>
      </div>
    </div>
  );
};
