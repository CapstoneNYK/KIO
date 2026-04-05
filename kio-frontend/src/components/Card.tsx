export interface CardProps {
  img: string;
  title: string;
  price: number;
  onClick?: () => void;
}

export const Card = ({ img, title, price, onClick }: CardProps) => {
  return (
    <button
      onClick={onClick}
      className="
          w-full rounded-2xl bg-white p-4
          shadow-sm transition
          active:scale-95
          focus:outline-none
        "
    >
      <img
        src={img}
        alt={title}
        className="h-40 w-full rounded-xl object-contain"
      />

      <div className="mt-3 text-left">
        <p className="text-base font-semibold text-gray-900">{title}</p>
        <p className="mt-1 text-sm font-bold text-orange-500">
          {price.toLocaleString()}원
        </p>
      </div>
    </button>
  );
};
