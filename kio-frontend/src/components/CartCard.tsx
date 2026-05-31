export interface CartCardProps {
  img: string;
  title: string;
  price: number;
  quantity: number;

  onIncrease: () => void;
  onDecrease: () => void;
  onRemove: () => void;
}

export const CartCard = ({
  img,
  title,
  price,
  quantity,
  onIncrease,
  onDecrease,
  onRemove,
}: CartCardProps) => {
  return (
    <div className="flex gap-4 rounded-xl bg-white p-4 shadow">
      <img
        src={img}
        alt={title}
        className="h-24 w-24 rounded-lg object-contain"
      />

      <div className="flex flex-col justify-between flex-1">
        <div className="flex justify-between items-start">
          <p className="text-lg font-semibold">{title}</p>

          {/* 삭제 버튼 */}
          <button
            onClick={onRemove}
            className="text-gray-400 hover:text-red-500 text-xl"
          >
            x
          </button>
        </div>

        <div className="flex items-center justify-between">
          {/* 수량 조절 */}
          <div className="flex items-center gap-3">
            <button
              onClick={onDecrease}
              disabled={quantity <= 1}
              className="h-8 w-8 rounded-full border text-lg disabled:opacity-40"
            >
              -
            </button>

            <span className="text-lg font-medium">{quantity}</span>

            <button
              onClick={onIncrease}
              className="h-8 w-8 rounded-full border text-lg"
            >
              +
            </button>
          </div>

          {/* 가격 */}
          <p className="text-lg font-bold text-[#E17100]">
            {(price * quantity).toLocaleString()}원
          </p>
        </div>
      </div>
    </div>
  );
};
