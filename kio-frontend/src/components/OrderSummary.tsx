import { IoCartOutline } from "react-icons/io5";
import { CartCard } from "./CartCard";
import { coffee1 } from "../assets";
import { useState } from "react";

interface CartItem {
  id: number;
  img: string;
  title: string;
  price: number;
  quantity: number;
}

export const OrderSummary = () => {
  const [cartItems, setCartItems] = useState<CartItem[]>([
    {
      id: 1,
      img: coffee1,
      title: "아메리카노",
      price: 4000,
      quantity: 1,
    },
    {
      id: 2,
      img: coffee1,
      title: "아메리카노",
      price: 4000,
      quantity: 1,
    },
  ]);

  const increaseQuantity = (id: number) => {
    setCartItems((items) =>
      items.map((item) =>
        item.id === id ? { ...item, quantity: item.quantity + 1 } : item
      )
    );
  };

  const decreaseQuantity = (id: number) => {
    setCartItems((items) =>
      items.map((item) =>
        item.id === id && item.quantity > 1
          ? { ...item, quantity: item.quantity - 1 }
          : item
      )
    );
  };

  const removeItem = (id: number) => {
    setCartItems((items) => items.filter((item) => item.id !== id));
  };

  // 총 개수
  const totalCount = cartItems.reduce((sum, item) => sum + item.quantity, 0);

  // 총 금액
  const totalPrice = cartItems.reduce(
    (sum, item) => sum + item.price * item.quantity,
    0
  );

  return (
    <div className="bg-white rounded-t-2xl p-4 shadow">
      {/* 헤더 */}
      <div className="flex items-center gap-2 mb-4">
        <IoCartOutline size={22} />
        <p className="font-semibold">담은 메뉴</p>
        <p className="text-gray-500">({cartItems.length}개)</p>
      </div>

      {/* 카드 리스트 */}
      <div className="flex flex-col gap-3">
        {cartItems.map((item) => (
          <CartCard
            key={item.id}
            img={item.img}
            title={item.title}
            price={item.price}
            quantity={item.quantity}
            onIncrease={() => increaseQuantity(item.id)}
            onDecrease={() => decreaseQuantity(item.id)}
            onRemove={() => removeItem(item.id)}
          />
        ))}
      </div>

      <div className="mt-4 border-t border-[#FEF3C6] pt-4">
        <div className="flex justify-between text-sm mb-2">
          <p>총 {totalCount}개</p>
          <div className="flex gap-2">
            <p>결제금액</p>
            <p className="font-semibold">{totalPrice.toLocaleString()}원</p>
          </div>
        </div>

        <button className="w-full bg-yellow-400 py-3 rounded-lg font-semibold">
          주문하기
        </button>
      </div>
    </div>
  );
};
